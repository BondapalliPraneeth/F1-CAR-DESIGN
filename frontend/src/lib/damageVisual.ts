/**
 * Pure mapping from simulated damage to kinematic visual effects on GLB nodes.
 *
 * This is a VISUAL REPRESENTATION ONLY: parts are rotated, translated, scaled,
 * tinted or hidden to show where damage is and roughly how bad it is. There is
 * no structural deformation or fracture model behind it.
 *
 * Coordinates follow the GLB: +X forward, +Y up, +Z left. Node names are
 * `<component>__<part>`, with each node's origin at its own pivot.
 */
import type { DamageInput } from "./types";

export type Vec3 = [number, number, number];

export interface NodeEffect {
  dp: Vec3; // position offset [m]
  dr: Vec3; // euler rotation offset [rad]
  s: Vec3; // scale multiplier
  hidden: boolean; // detached at critical severity
  glow: number; // 0..1 heat glow
}

export interface DamageVisuals {
  nodes: Record<string, NodeEffect>;
  /** Per-component tint amount (0..1) and colour (hex) for damage tinting. */
  tint: Record<string, { amount: number; color: string }>;
}

export type PivotLookup = (node: string) => Vec3 | undefined;

/** Damage types that are shown only as a heat glow (no tint). */
const GLOW_ONLY = new Set(["overheating", "brake_overheating", "engine_overheating", "stuck_open"]);

export const CRITICAL_THRESHOLD = 75;

function blank(): NodeEffect {
  return { dp: [0, 0, 0], dr: [0, 0, 0], s: [1, 1, 1], hidden: false, glow: 0 };
}

/** Linear blend between amber (#f59e0b) and red (#ef4444). */
export function tintColor(d: number): string {
  const a = [0xf5, 0x9e, 0x0b];
  const b = [0xef, 0x44, 0x44];
  const t = Math.min(1, Math.max(0, d));
  const c = a.map((v, i) => Math.round(v + (b[i] - v) * t));
  return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
}

/** Heat colour map for glow: dark red -> orange -> yellow-white. */
export function heatColor(g: number): string {
  const stops: [number, number[]][] = [
    [0, [0x5a, 0x0a, 0x00]],
    [0.4, [0xd9, 0x30, 0x00]],
    [0.75, [0xff, 0x8c, 0x00]],
    [1, [0xff, 0xe8, 0xa0]],
  ];
  const t = Math.min(1, Math.max(0, g));
  for (let i = 1; i < stops.length; i++) {
    const [t1, c1] = stops[i];
    const [t0, c0] = stops[i - 1];
    if (t <= t1) {
      const k = (t - t0) / (t1 - t0);
      const c = c0.map((v, j) => Math.round(v + (c1[j] - v) * k));
      return `#${c.map((v) => v.toString(16).padStart(2, "0")).join("")}`;
    }
  }
  return "#ffe8a0";
}

/** Rotate offset vector (y,z) about +X by angle a. */
function rotX(v: Vec3, a: number): Vec3 {
  const c = Math.cos(a);
  const s = Math.sin(a);
  return [v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c];
}

export function computeDamageVisuals(damages: DamageInput[], pivot: PivotLookup): DamageVisuals {
  const nodes: Record<string, NodeEffect> = {};
  const tint: DamageVisuals["tint"] = {};

  const fx = (node: string): NodeEffect => (nodes[node] ??= blank());
  const move = (node: string, x: number, y: number, z: number) => {
    const e = fx(node);
    e.dp = [e.dp[0] + x, e.dp[1] + y, e.dp[2] + z];
  };
  const rot = (node: string, x: number, y: number, z: number) => {
    const e = fx(node);
    e.dr = [e.dr[0] + x, e.dr[1] + y, e.dr[2] + z];
  };
  const scale = (node: string, x: number, y: number, z: number) => {
    const e = fx(node);
    e.s = [e.s[0] * x, e.s[1] * y, e.s[2] * z];
  };
  const glow = (node: string, g: number) => {
    const e = fx(node);
    e.glow = Math.max(e.glow, g);
  };
  const hide = (node: string) => {
    fx(node).hidden = true;
  };

  /** Rigidly rotate a set of nodes about hub point h by camber angle a (about +X). */
  const camberAbout = (list: string[], h: Vec3, a: number) => {
    for (const n of list) {
      const p = pivot(n);
      if (!p) continue;
      const rel: Vec3 = [p[0] - h[0], p[1] - h[1], p[2] - h[2]];
      const r = rotX(rel, a);
      move(n, r[0] - rel[0], r[1] - rel[1], r[2] - rel[2]);
      rot(n, a, 0, 0);
    }
  };

  const corner = (axle: "front" | "rear") => [
    `${axle}_tyres__tyre_l`,
    `${axle}_tyres__rim_l`,
    `${axle}_tyres__face_l`,
    `${axle}_tyres__nut_l`,
    `${axle}_brakes__disc_l`,
    `${axle}_brakes__caliper_l`,
    `${axle}_suspension__upright_l`,
  ];

  for (const dmg of damages) {
    const sev = Math.min(100, Math.max(0, dmg.severity));
    if (sev <= 0) continue;
    const d = sev / 100;
    const critical = sev > CRITICAL_THRESHOLD;
    const c = dmg.component_id;
    const t = dmg.damage_type;

    if (!GLOW_ONLY.has(t)) {
      const prev = tint[c]?.amount ?? 0;
      const amount = 0.25 + 0.5 * d;
      if (amount > prev) tint[c] = { amount, color: tintColor(d) };
    }

    switch (`${c}:${t}`) {
      case "front_wing:endplate_damage": {
        // Pivot at the top edge; negative x-rotation swings the bottom outward (+Z).
        const n = "front_wing__endplate_l";
        if (critical) hide(n);
        else {
          rot(n, -0.55 * d, 0, 0.08 * d);
          move(n, 0, -0.06 * d, 0.03 * d);
        }
        break;
      }
      case "front_wing:element_failure": {
        // Pivot at the leading edge; +z rotation drops the trailing edge.
        for (const side of ["l", "r"] as const) {
          const sign = side === "l" ? 1 : -1;
          rot(`front_wing__flap_1_${side}`, sign * 0.08 * d, 0, 0.25 * d);
          const n2 = `front_wing__flap_2_${side}`;
          if (critical) hide(n2);
          else rot(n2, sign * 0.15 * d, 0, 0.45 * d);
        }
        break;
      }
      case "nose_cone:nose_damage": {
        // Shell spans x 1.40..2.74 around pivot 2.07; crush from the front, keep rear attached.
        const sx = 1 - 0.18 * d;
        scale("nose_cone__shell", sx, 1, 1);
        move("nose_cone__shell", 0.67 * (1 - sx), 0, 0);
        rot("nose_cone__shell", 0, 0, -0.05 * d);
        move("nose_cone__tip", -1.34 * (1 - sx), -0.035 * d, 0);
        rot("nose_cone__tip", 0, 0, -0.05 * d);
        break;
      }
      case "front_suspension:suspension_damage":
      case "rear_suspension:suspension_damage": {
        const axle = c.startsWith("front") ? "front" : "rear";
        const hubX = axle === "front" ? 1.8 : -1.8;
        const list = corner(axle);
        // Negative x-rotation tilts the top of a left (+Z) wheel inboard: negative camber.
        camberAbout(list, [hubX, 0.36, 0.8], -0.14 * d);
        for (const n of list) move(n, 0, -0.06 * d, 0);
        break;
      }
      case "front_tyres:puncture":
      case "rear_tyres:puncture": {
        const axle = c.startsWith("front") ? "front" : "rear";
        const sy = 1 - 0.18 * d;
        scale(`${axle}_tyres__tyre_l`, 1, sy, 1);
        // Keep the contact patch on the ground: lower the corner by the lost radius.
        for (const n of corner(axle)) move(n, 0, -0.36 * (1 - sy), 0);
        break;
      }
      case "front_tyres:overheating":
      case "rear_tyres:overheating":
        glow(`${c}__tyre_l`, d);
        glow(`${c}__tyre_r`, d);
        break;
      case "front_brakes:brake_overheating":
      case "rear_brakes:brake_overheating":
        glow(`${c}__disc_l`, d);
        glow(`${c}__disc_r`, d);
        break;
      case "radiators:cooling_failure":
        glow("radiators__core_l", d);
        glow("radiators__core_r", d);
        break;
      case "power_unit:engine_overheating":
        glow("power_unit__block", d);
        break;
      case "sidepods:inlet_damage": {
        // Body spans z 0.23..0.78 around 0.505; crush the outer face inward.
        const sz = 1 - 0.25 * d;
        scale("sidepods__body_l", 1, 1 - 0.06 * d, sz);
        move("sidepods__body_l", 0, 0, -0.275 * (1 - sz));
        scale("sidepods__inlet_l", 1, 1 - 0.3 * d, sz);
        move("sidepods__inlet_l", -0.04 * d, -0.01 * d, -0.06 * d);
        rot("sidepods__inlet_l", 0.12 * d, 0, 0);
        break;
      }
      case "floor:floor_damage": {
        const n = "floor__edge_l";
        if (critical) hide(n);
        else {
          rot(n, 0.1 * d, 0, 0.06 * d);
          move(n, 0, -0.025 * d, 0.01 * d);
        }
        break;
      }
      case "venturi_tunnels:tunnel_damage":
        for (const i of [1, 2, 3]) {
          const n = `venturi_tunnels__fence_l${i}`;
          rot(n, 0.3 * d * (i % 2 ? 1 : -1), 0.12 * d, 0.18 * d);
          move(n, 0, -0.015 * d, 0);
        }
        break;
      case "diffuser:diffuser_damage":
        rot("diffuser__ramp", 0.04 * d, 0, 0.16 * d);
        for (const n of ["diffuser__strake_l1", "diffuser__strake_l2"]) rot(n, 0.25 * d, 0, 0.1 * d);
        break;
      case "rear_wing:wing_damage":
        rot("rear_wing__mainplane", 0.1 * d, 0, 0.12 * d);
        // Pivot at the bottom of the right (−Z) endplate; negative x-rotation tilts its top outward.
        rot("rear_wing__endplate_r", -0.35 * d, 0, 0);
        break;
      case "drs:stuck_open":
        // Pivot at the trailing edge; +z rotation lifts the leading edge (flap opens).
        rot("drs__flap", 0, 0, 0.5 * d);
        break;
      case "rear_crash_structure:structural_damage": {
        // Structure spans x -2.45..-1.85 around -2.15; crush from the rear.
        const sx = 1 - 0.3 * d;
        scale("rear_crash_structure__structure", sx, 1, 1);
        move("rear_crash_structure__structure", 0.3 * (1 - sx), 0, 0);
        move("rear_crash_structure__rain_light", 0.6 * (1 - sx), 0, 0);
        break;
      }
      default:
        // Remaining types (structural damage, DRS stuck closed, power loss) are tint-only.
        break;
    }
  }
  return { nodes, tint };
}

/** Component-level explode offsets [m] at explode = 1. Lateral (z) flips for right-side nodes. */
export const EXPLODE_OFFSETS: Record<string, Vec3> = {
  front_wing: [0.9, -0.05, 0],
  nose_cone: [0.5, 0.3, 0],
  front_suspension: [0.2, 0.25, 0.3],
  front_tyres: [0.3, 0, 0.7],
  front_brakes: [0.3, 0.15, 0.45],
  monocoque: [0, 0, 0],
  halo: [0, 0.6, 0],
  cockpit: [0.05, 0.95, 0],
  sidepods: [0, 0.1, 0.6],
  radiators: [0, 0.45, 0.35],
  floor: [0, -0.45, 0],
  venturi_tunnels: [0, -0.75, 0.15],
  diffuser: [-0.6, -0.4, 0],
  rear_suspension: [-0.2, 0.25, 0.3],
  rear_tyres: [-0.3, 0, 0.75],
  rear_brakes: [-0.3, 0.15, 0.5],
  rear_wing: [-0.8, 0.45, 0],
  drs: [-0.9, 0.85, 0],
  power_unit: [-0.35, 0.55, 0],
  rear_crash_structure: [-0.8, -0.05, 0],
};

/** Side sign for a node: +1 for left parts, -1 for right parts, 0 for centreline parts. */
export function sideSign(node: string): number {
  const m = /_(l|r)\d*$/.exec(node);
  if (!m) return 0;
  return m[1] === "l" ? 1 : -1;
}

export function explodeOffset(component: string, node: string, amount: number): Vec3 {
  const o = EXPLODE_OFFSETS[component] ?? [0, 0, 0];
  const side = sideSign(node);
  return [o[0] * amount, o[1] * amount, o[2] * side * amount];
}

export function componentOf(node: string): string | null {
  const i = node.indexOf("__");
  return i > 0 ? node.slice(0, i) : null;
}
