import { useGLTF } from "@react-three/drei";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { componentOf, computeDamageVisuals, explodeOffset, heatColor, type DamageVisuals, type Vec3 } from "@/lib/damageVisual";
import { damageList, useStore } from "@/store";

interface Part {
  mesh: THREE.Mesh;
  node: string;
  comp: string;
  basePos: THREE.Vector3;
  baseRot: THREE.Euler;
  baseScale: THREE.Vector3;
  mat: THREE.MeshStandardMaterial;
  baseColor: THREE.Color;
  baseEmissive: THREE.Color;
  baseEmissiveIntensity: number;
  baseOpacity: number;
  baseTransparent: boolean;
}

const ACCENT = new THREE.Color("#ff4a3d");
const tmpColor = new THREE.Color();
const tmpVec = new THREE.Vector3();
const hsl = { h: 0, s: 0, l: 0 };
const LIVERY_RED = new THREE.Color("#d42a1e");
const LIVERY_BODY = new THREE.Color("#1a1c22");

/** Showroom livery: the GLB's teal accents become red and its navy bodywork becomes graphite. */
function applyLivery(c: THREE.Color) {
  c.getHSL(hsl);
  if (hsl.s < 0.25) return;
  const deg = hsl.h * 360;
  if (deg >= 150 && deg < 200) c.copy(LIVERY_RED);
  else if (deg >= 200 && deg < 260) c.copy(LIVERY_BODY);
}

export interface HoverInfo {
  component: string;
  x: number;
  y: number;
}

export function CarModel({ url, onHover }: { url: string; onHover: (h: HoverInfo | null) => void }) {
  const gltf = useGLTF(url);
  const scene = useMemo(() => gltf.scene.clone(true), [gltf.scene]);

  const parts = useMemo(() => {
    const list: Part[] = [];
    scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const comp = componentOf(mesh.name);
      if (!comp) return;
      const src = mesh.material as THREE.MeshStandardMaterial;
      const mat = src.clone();
      applyLivery(mat.color);
      mesh.material = mat;
      mesh.castShadow = true;
      mesh.receiveShadow = true;
      list.push({
        mesh,
        node: mesh.name,
        comp,
        basePos: mesh.position.clone(),
        baseRot: mesh.rotation.clone(),
        baseScale: mesh.scale.clone(),
        mat,
        baseColor: mat.color.clone(),
        baseEmissive: mat.emissive.clone(),
        baseEmissiveIntensity: mat.emissiveIntensity,
        baseOpacity: mat.opacity,
        baseTransparent: mat.transparent,
      });
    });
    return list;
  }, [scene]);

  useEffect(() => () => parts.forEach((p) => p.mat.dispose()), [parts]);

  const pivots = useMemo(() => {
    const m = new Map<string, Vec3>();
    for (const p of parts) m.set(p.node, [p.basePos.x, p.basePos.y, p.basePos.z]);
    return m;
  }, [parts]);

  const damage = useStore((s) => s.damage);
  const visuals = useRef<DamageVisuals>({ nodes: {}, tint: {} });
  useEffect(() => {
    visuals.current = computeDamageVisuals(damageList(damage), (n) => pivots.get(n));
  }, [damage, pivots]);

  const explodeNow = useRef(0);

  useFrame((_, dt) => {
    const s = useStore.getState();
    const k = 1 - Math.exp(-dt * 9); // frame-rate independent smoothing
    explodeNow.current += (s.explode - explodeNow.current) * k;
    const v = visuals.current;
    const t = performance.now() / 1000;

    for (const p of parts) {
      const fx = v.nodes[p.node];
      const ex = explodeOffset(p.comp, p.node, explodeNow.current);

      // Transform
      tmpVec.set(p.basePos.x + ex[0] + (fx?.dp[0] ?? 0), p.basePos.y + ex[1] + (fx?.dp[1] ?? 0), p.basePos.z + ex[2] + (fx?.dp[2] ?? 0));
      p.mesh.position.lerp(tmpVec, k);
      p.mesh.rotation.x += (p.baseRot.x + (fx?.dr[0] ?? 0) - p.mesh.rotation.x) * k;
      p.mesh.rotation.y += (p.baseRot.y + (fx?.dr[1] ?? 0) - p.mesh.rotation.y) * k;
      p.mesh.rotation.z += (p.baseRot.z + (fx?.dr[2] ?? 0) - p.mesh.rotation.z) * k;
      tmpVec.set(p.baseScale.x * (fx?.s[0] ?? 1), p.baseScale.y * (fx?.s[1] ?? 1), p.baseScale.z * (fx?.s[2] ?? 1));
      p.mesh.scale.lerp(tmpVec, k);

      // Visibility
      const userHidden = !!s.hidden[p.comp];
      const isolatedOut = s.isolatedId !== null && s.isolatedId !== p.comp;
      p.mesh.visible = !userHidden && !isolatedOut && !fx?.hidden;

      // Colour: damage tint
      const tint = v.tint[p.comp];
      p.mat.color.copy(p.baseColor);
      if (tint) p.mat.color.lerp(tmpColor.set(tint.color), tint.amount);

      // Emissive: heat glow > selection > hover > base
      const selected = s.selectedId === p.comp;
      const hovered = s.hoveredId === p.comp;
      if (fx && fx.glow > 0) {
        p.mat.emissive.set(heatColor(fx.glow));
        p.mat.emissiveIntensity = 0.4 + 1.6 * fx.glow * (0.92 + 0.08 * Math.sin(t * 3));
      } else if (selected) {
        p.mat.emissive.copy(ACCENT);
        p.mat.emissiveIntensity = 0.28 + 0.06 * Math.sin(t * 2.5);
      } else if (hovered) {
        p.mat.emissive.copy(ACCENT);
        p.mat.emissiveIntensity = 0.16;
      } else {
        p.mat.emissive.copy(p.baseEmissive);
        p.mat.emissiveIntensity = p.baseEmissiveIntensity;
      }

      // X-ray: ghost everything except the selection so internals are visible.
      const ghost = s.xray && !selected;
      const wantTransparent = ghost || p.baseTransparent;
      if (p.mat.transparent !== wantTransparent) {
        p.mat.transparent = wantTransparent;
        p.mat.needsUpdate = true;
      }
      p.mat.opacity = ghost ? 0.14 : p.baseOpacity;
      p.mat.depthWrite = !ghost;
      p.mesh.castShadow = !ghost;
    }
  });

  const pick = (e: ThreeEvent<PointerEvent | MouseEvent>) => {
    const comp = componentOf(e.object.name);
    return comp;
  };

  return (
    <primitive
      object={scene}
      onPointerMove={(e: ThreeEvent<PointerEvent>) => {
        e.stopPropagation();
        const comp = pick(e);
        if (!comp) return;
        if (useStore.getState().hoveredId !== comp) useStore.getState().hover(comp);
        onHover({ component: comp, x: e.nativeEvent.offsetX, y: e.nativeEvent.offsetY });
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        useStore.getState().hover(null);
        onHover(null);
        document.body.style.cursor = "";
      }}
      onClick={(e: ThreeEvent<MouseEvent>) => {
        e.stopPropagation();
        const comp = pick(e);
        if (comp) useStore.getState().select(comp);
      }}
    />
  );
}
