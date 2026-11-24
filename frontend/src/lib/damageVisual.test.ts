import { describe, expect, it } from "vitest";
import {
  componentOf,
  computeDamageVisuals,
  explodeOffset,
  heatColor,
  sideSign,
  tintColor,
  type Vec3,
} from "./damageVisual";
import { classifySeverity } from "./severity";

const pivots: Record<string, Vec3> = {
  front_tyres__tyre_l: [1.8, 0.36, 0.8],
  front_tyres__rim_l: [1.8, 0.36, 0.8],
  front_brakes__caliper_l: [1.74, 0.51, 0.725],
  front_suspension__upright_l: [1.8, 0.36, 0.7],
};
const pivot = (n: string) => pivots[n];

describe("computeDamageVisuals", () => {
  it("returns nothing for a healthy car", () => {
    const v = computeDamageVisuals([], pivot);
    expect(v.nodes).toEqual({});
    expect(v.tint).toEqual({});
  });

  it("ignores zero severity", () => {
    const v = computeDamageVisuals([{ component_id: "front_wing", damage_type: "endplate_damage", severity: 0 }], pivot);
    expect(Object.keys(v.nodes)).toHaveLength(0);
  });

  it("detaches the endplate only above the critical threshold", () => {
    const severe = computeDamageVisuals([{ component_id: "front_wing", damage_type: "endplate_damage", severity: 70 }], pivot);
    expect(severe.nodes.front_wing__endplate_l.hidden).toBe(false);
    expect(severe.nodes.front_wing__endplate_l.dr[0]).toBeLessThan(0);
    const crit = computeDamageVisuals([{ component_id: "front_wing", damage_type: "endplate_damage", severity: 90 }], pivot);
    expect(crit.nodes.front_wing__endplate_l.hidden).toBe(true);
  });

  it("flattens a punctured tyre and keeps it on the ground", () => {
    const v = computeDamageVisuals([{ component_id: "front_tyres", damage_type: "puncture", severity: 100 }], pivot);
    const t = v.nodes.front_tyres__tyre_l;
    expect(t.s[1]).toBeCloseTo(0.82, 5);
    // Bottom of tyre = pivot.y + dp.y - 0.36 * sy  -> 0
    expect(0.36 + t.dp[1] - 0.36 * t.s[1]).toBeCloseTo(0, 5);
  });

  it("scales effects with severity", () => {
    const lo = computeDamageVisuals([{ component_id: "drs", damage_type: "stuck_open", severity: 20 }], pivot);
    const hi = computeDamageVisuals([{ component_id: "drs", damage_type: "stuck_open", severity: 80 }], pivot);
    expect(hi.nodes.drs__flap.dr[2]).toBeGreaterThan(lo.nodes.drs__flap.dr[2]);
  });

  it("uses glow, not tint, for thermal damage", () => {
    const v = computeDamageVisuals([{ component_id: "front_brakes", damage_type: "brake_overheating", severity: 60 }], pivot);
    expect(v.nodes.front_brakes__disc_l.glow).toBeCloseTo(0.6);
    expect(v.nodes.front_brakes__disc_r.glow).toBeCloseTo(0.6);
    expect(v.tint.front_brakes).toBeUndefined();
  });

  it("tints by severity for structural damage", () => {
    const v = computeDamageVisuals([{ component_id: "monocoque", damage_type: "structural_damage", severity: 50 }], pivot);
    expect(v.tint.monocoque.amount).toBeCloseTo(0.5);
    expect(Object.keys(v.nodes)).toHaveLength(0);
  });

  it("cambers the suspension corner rigidly about the hub", () => {
    const v = computeDamageVisuals([{ component_id: "front_suspension", damage_type: "suspension_damage", severity: 100 }], pivot);
    const tyre = v.nodes.front_tyres__tyre_l;
    expect(tyre.dp[1]).toBeCloseTo(-0.06, 5); // tyre pivot is the hub: only the drop
    expect(tyre.dr[0]).toBeCloseTo(-0.14, 5);
    const caliper = v.nodes.front_brakes__caliper_l;
    expect(caliper.dp[2]).not.toBeCloseTo(0, 3); // off-hub parts swing
  });

  it("combines several damages", () => {
    const v = computeDamageVisuals(
      [
        { component_id: "front_tyres", damage_type: "puncture", severity: 50 },
        { component_id: "front_suspension", damage_type: "suspension_damage", severity: 50 },
      ],
      pivot,
    );
    expect(v.nodes.front_tyres__tyre_l.dp[1]).toBeLessThan(-0.06 * 0.5);
  });
});

describe("helpers", () => {
  it("colour ramps", () => {
    expect(tintColor(0)).toBe("#f59e0b");
    expect(tintColor(1)).toBe("#ef4444");
    expect(heatColor(1)).toBe("#ffe8a0");
    expect(heatColor(0)).toBe("#5a0a00");
  });
  it("side and component parsing", () => {
    expect(sideSign("front_tyres__tyre_l")).toBe(1);
    expect(sideSign("venturi_tunnels__fence_r2")).toBe(-1);
    expect(sideSign("halo__pillar")).toBe(0);
    expect(componentOf("front_tyres__tyre_l")).toBe("front_tyres");
    expect(componentOf("apexvision_av1")).toBeNull();
  });
  it("explode offsets mirror right side parts", () => {
    expect(explodeOffset("front_tyres", "front_tyres__tyre_r", 1)).toEqual([0.3, 0, -0.7]);
    expect(explodeOffset("front_tyres", "front_tyres__tyre_l", 0.5)).toEqual([0.15, 0, 0.35]);
  });
  it("severity levels mirror the backend", () => {
    expect(classifySeverity(0)).toBe("healthy");
    expect(classifySeverity(20)).toBe("minor");
    expect(classifySeverity(21)).toBe("moderate");
    expect(classifySeverity(75)).toBe("severe");
    expect(classifySeverity(76)).toBe("critical");
  });
});
