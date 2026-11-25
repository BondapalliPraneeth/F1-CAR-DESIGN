import { ContactShadows, Environment, Grid, Lightformer, OrbitControls, useProgress } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Box, Camera, Expand, Eye, Layers, Maximize, Maximize2, Minimize, MousePointer2, RotateCcw, RotateCw, ScanEye } from "lucide-react";
import { Component, Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { Button } from "@/components/ui/button";
import { Slider } from "@/components/ui/slider";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { classifySeverity } from "@/lib/severity";
import { cn } from "@/lib/utils";
import { useStore, type CameraPreset } from "@/store";
import { CarModel, type HoverInfo } from "./CarModel";

// The car faces +x with y up, so its right-hand side is +z.
export const CAMERA_PRESETS: Record<CameraPreset, { pos: [number, number, number]; label: string }> = {
  iso: { pos: [6.4, 3.1, 7.0], label: "Perspective" },
  front: { pos: [7, 1.2, 0], label: "Front" },
  rear: { pos: [-7, 1.5, 0], label: "Rear" },
  left: { pos: [0, 1.2, -7], label: "Left" },
  right: { pos: [0, 1.2, 7], label: "Right" },
  top: { pos: [0, 8, 0.01], label: "Top" },
};
const TARGET = new THREE.Vector3(0, 0.4, 0);

function CameraRig() {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as OrbitControlsImpl | null;
  const nonce = useStore((s) => s.camera.nonce);
  const preset = useStore((s) => s.camera.preset);
  const anim = useRef<{ from: THREE.Vector3; to: THREE.Vector3; fromT: THREE.Vector3; t: number } | null>(null);

  useEffect(() => {
    if (nonce === 0) return;
    anim.current = {
      from: camera.position.clone(),
      to: new THREE.Vector3(...CAMERA_PRESETS[preset].pos),
      fromT: controls ? controls.target.clone() : TARGET.clone(),
      t: 0,
    };
  }, [nonce, preset, camera, controls]);

  useFrame((_, dt) => {
    const a = anim.current;
    if (!a) return;
    a.t = Math.min(1, a.t + dt / 0.7);
    const e = 1 - Math.pow(1 - a.t, 3);
    camera.position.lerpVectors(a.from, a.to, e);
    if (controls) {
      controls.target.lerpVectors(a.fromT, TARGET, e);
      controls.update();
    } else camera.lookAt(TARGET);
    if (a.t >= 1) anim.current = null;
  });
  return null;
}

/** Turns the car towards the mouse cursor (anywhere on the page) with smoothed yaw and a slight pitch.
 *  Paused while a mouse button is held so it never fights an orbit drag. */
function CursorFollow({ children }: { children: ReactNode }) {
  const group = useRef<THREE.Group>(null);
  const target = useRef({ x: 0, y: 0 });
  const enabled = useStore((s) => s.followCursor);
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      if (e.buttons !== 0) return;
      target.current.x = (e.clientX / window.innerWidth) * 2 - 1;
      target.current.y = (e.clientY / window.innerHeight) * 2 - 1;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);
  useFrame((_, dt) => {
    const g = group.current;
    if (!g) return;
    const k = 1 - Math.exp(-dt * 3.5);
    const yaw = enabled ? target.current.x * 0.4 : 0;
    const pitch = enabled ? target.current.y * 0.06 : 0;
    g.rotation.y += (yaw - g.rotation.y) * k;
    g.rotation.z += (pitch - g.rotation.z) * k;
  });
  return <group ref={group}>{children}</group>;
}

/** True when WebGL is backed by a software rasteriser (no GPU acceleration). Such browsers get a cheaper scene. */
let softwareGL: boolean | null = null;
function isSoftwareGL(): boolean {
  if (softwareGL !== null) return softwareGL;
  softwareGL = false;
  try {
    const gl = document.createElement("canvas").getContext("webgl");
    if (gl) {
      const ext = gl.getExtension("WEBGL_debug_renderer_info");
      const name = String(gl.getParameter(ext ? ext.UNMASKED_RENDERER_WEBGL : gl.RENDERER));
      softwareGL = /swiftshader|llvmpipe|softpipe|software|basic render/i.test(name);
      gl.getExtension("WEBGL_lose_context")?.loseContext();
    }
  } catch {
    /* keep full quality */
  }
  return softwareGL;
}

/** Drives a demand-mode canvas at a fixed, low frame rate (software rendering), leaving CPU for the rest of the page. */
function FrameCap({ fps }: { fps: number }) {
  const invalidate = useThree((s) => s.invalidate);
  useEffect(() => {
    const id = setInterval(() => invalidate(), 1000 / fps);
    return () => clearInterval(id);
  }, [fps, invalidate]);
  return null;
}

/** Display turntable under the car: dark disc with a glowing red rim. */
function Platform() {
  return (
    <group position={[0, 0.002, 0]}>
      <mesh rotation-x={-Math.PI / 2} receiveShadow>
        <circleGeometry args={[3.7, 96]} />
        <meshStandardMaterial color="#0b0c10" metalness={0.55} roughness={0.45} />
      </mesh>
      <mesh rotation-x={-Math.PI / 2} position-y={0.003}>
        <ringGeometry args={[3.62, 3.72, 160]} />
        <meshBasicMaterial color="#ff3b2f" toneMapped={false} />
      </mesh>
      <mesh rotation-x={-Math.PI / 2} position-y={0.002}>
        <ringGeometry args={[3.72, 4.6, 160]} />
        <meshBasicMaterial color="#ff3b2f" transparent opacity={0.1} depthWrite={false} toneMapped={false} />
      </mesh>
      <mesh rotation-x={-Math.PI / 2} position-y={0.003}>
        <ringGeometry args={[2.9, 2.93, 160]} />
        <meshBasicMaterial color="#ff3b2f" transparent opacity={0.35} toneMapped={false} />
      </mesh>
    </group>
  );
}

function useFullscreen(ref: React.RefObject<HTMLElement>) {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const f = () => setOn(document.fullscreenElement === ref.current);
    document.addEventListener("fullscreenchange", f);
    return () => document.removeEventListener("fullscreenchange", f);
  }, [ref]);
  const toggle = () => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void ref.current?.requestFullscreen?.();
  };
  return { on, toggle, supported: typeof document !== "undefined" && !!document.fullscreenEnabled };
}

function Screenshotter() {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const nonce = useStore((s) => s.screenshotNonce);
  useEffect(() => {
    if (nonce === 0) return;
    gl.render(scene, camera);
    const a = document.createElement("a");
    a.href = gl.domElement.toDataURL("image/png");
    a.download = `apexvision-av1-${new Date().toISOString().replace(/[:.]/g, "-")}.png`;
    a.click();
  }, [nonce, gl, scene, camera]);
  return null;
}

function Loader() {
  const { progress, active } = useProgress();
  if (!active) return null;
  return (
    <div className="pointer-events-none absolute inset-0 grid place-items-center">
      <div className="rounded-md border border-line bg-panel/90 px-4 py-2 text-sm text-ink-2">Loading 3D model… {progress.toFixed(0)}%</div>
    </div>
  );
}

class ViewerBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(e: Error) {
    return { error: e.message };
  }
  render() {
    if (this.state.error)
      return (
        <div className="grid h-full place-items-center p-6 text-center text-sm text-ink-2">
          <div>
            <p className="font-medium text-ink">The 3D viewer could not start.</p>
            <p className="mt-1">{this.state.error}</p>
            <p className="mt-1">WebGL may be disabled in this browser. The engineering panels and dashboard still work.</p>
          </div>
        </div>
      );
    return this.props.children;
  }
}

export function CarViewer({ assetUrl }: { assetUrl: string }) {
  const [hover, setHover] = useState<HoverInfo | null>(null);
  const components = useStore((s) => s.components);
  const damage = useStore((s) => s.damage);
  const explode = useStore((s) => s.explode);
  const xray = useStore((s) => s.xray);
  const autoRotate = useStore((s) => s.autoRotate);
  const followCursor = useStore((s) => s.followCursor);
  const preset = useStore((s) => s.camera.preset);
  const isolatedId = useStore((s) => s.isolatedId);
  const { setExplode, setXray, setAutoRotate, setFollowCursor, resetView, setCamera, takeScreenshot, showAll, select } = useStore.getState();
  const rootRef = useRef<HTMLDivElement>(null);
  const fs = useFullscreen(rootRef);
  const [lite] = useState(isSoftwareGL);

  const hoverComp = hover ? components.find((c) => c.id === hover.component) : undefined;
  const hoverSev = hover ? (damage[hover.component]?.severity ?? 0) : 0;

  return (
    <div ref={rootRef} className="relative h-full w-full overflow-hidden bg-bg" data-testid="car-viewer">
      <ViewerBoundary>
        <Canvas
          shadows={!lite}
          frameloop={lite ? "demand" : "always"}
          dpr={lite ? 0.5 : [1, 2]}
          gl={{ preserveDrawingBuffer: true, antialias: !lite, toneMapping: THREE.ACESFilmicToneMapping }}
          camera={{ position: CAMERA_PRESETS.iso.pos, fov: 38, near: 0.05, far: 100 }}
          onPointerMissed={() => select(null)}
        >
          <color attach="background" args={["#08090d"]} />
          <fog attach="fog" args={["#08090d", 12, 26]} />
          <ambientLight intensity={0.25} />
          <directionalLight position={[4, 8, 5]} intensity={1.6} castShadow={!lite} shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004}>
            <orthographicCamera attach="shadow-camera" args={[-5, 5, 5, -5, 0.5, 25]} />
          </directionalLight>
          <Environment resolution={lite ? 64 : 256}>
            <Lightformer form="rect" intensity={2.2} position={[0, 6, 0]} rotation-x={Math.PI / 2} scale={[10, 4, 1]} />
            <Lightformer form="rect" intensity={1.2} position={[-6, 2, 4]} rotation-y={Math.PI / 3} scale={[8, 2, 1]} />
            <Lightformer form="rect" intensity={1.2} position={[6, 2, -4]} rotation-y={-Math.PI / 3} scale={[8, 2, 1]} />
            <Lightformer form="ring" color="#ff3b2f" intensity={0.9} position={[0, 3, -8]} scale={3} />
            <Lightformer form="rect" color="#ff3b2f" intensity={0.5} position={[0, 1, 8]} scale={[10, 1, 1]} />
          </Environment>
          <CursorFollow>
            <Suspense fallback={null}>
              <CarModel url={assetUrl} onHover={setHover} />
            </Suspense>
          </CursorFollow>
          <Platform />
          <ContactShadows position={[0, 0.008, 0]} opacity={0.55} scale={9} blur={2.2} far={2} resolution={lite ? 256 : 512} frames={lite ? 1 : Infinity} />
          <Grid
            position={[0, 0, 0]}
            args={[30, 30]}
            cellSize={0.5}
            cellThickness={0.5}
            cellColor="#14161c"
            sectionSize={2.5}
            sectionThickness={1}
            sectionColor="#1d2027"
            fadeDistance={22}
            fadeStrength={1.5}
            infiniteGrid
          />
          <OrbitControls makeDefault target={TARGET} enableDamping minDistance={2.5} maxDistance={16} maxPolarAngle={Math.PI / 2 - 0.02} autoRotate={autoRotate} autoRotateSpeed={0.8} />
          <CameraRig />
          <Screenshotter />
          {lite && <FrameCap fps={6} />}
        </Canvas>
        <Loader />
      </ViewerBoundary>

      {hover && hoverComp && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-accent/50 bg-panel/95 px-2.5 py-1.5 text-xs shadow-lg"
          style={{ left: hover.x + 14, top: hover.y + 14 }}
          role="tooltip"
        >
          <div className="font-semibold text-ink">{hoverComp.name}</div>
          <div className="mt-0.5 flex items-center gap-2 text-ink-2">
            <span className="capitalize">{hoverComp.category}</span>
            <SeverityBadge level={classifySeverity(hoverSev)} />
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-1/2 bg-[radial-gradient(ellipse_at_50%_100%,rgba(239,59,45,0.16)_0%,transparent_60%)]" aria-hidden />
      <div className="absolute left-3 top-3 flex flex-wrap items-center gap-1 rounded-full border border-line bg-panel/85 p-1" role="toolbar" aria-label="Camera views">
        {(Object.keys(CAMERA_PRESETS) as CameraPreset[]).map((p) => (
          <Button key={p} size="sm" variant="ghost" className="h-7 rounded-full px-3" active={preset === p} onClick={() => setCamera(p)} aria-label={`${CAMERA_PRESETS[p].label} view`}>
            {CAMERA_PRESETS[p].label}
          </Button>
        ))}
      </div>

      <div className="absolute right-3 top-14 flex max-w-[calc(100%-1.5rem)] flex-wrap items-center justify-end gap-1 rounded-2xl border border-line bg-panel/85 p-1 xl:top-3 xl:max-w-[46%]" role="toolbar" aria-label="View options">
        <Button size="sm" variant="ghost" className="h-7 rounded-full" active={explode > 0} onClick={() => setExplode(explode > 0 ? 0 : 0.7)} aria-pressed={explode > 0} title="Toggle exploded view">
          <Expand /> Explode View
        </Button>
        <Button size="sm" variant="ghost" className="h-7 rounded-full" active={followCursor} onClick={() => setFollowCursor(!followCursor)} aria-pressed={followCursor} title="Car turns to follow the mouse cursor">
          <MousePointer2 /> Follow cursor
        </Button>
        <Button size="sm" variant="ghost" className="h-7 rounded-full" active={xray} onClick={() => setXray(!xray)} title="X-ray: ghost all but the selected component" aria-pressed={xray}>
          <ScanEye /> X-ray
        </Button>
        <Button size="sm" variant="ghost" className="h-7 rounded-full" active={autoRotate} onClick={() => setAutoRotate(!autoRotate)} title="Auto-rotate" aria-pressed={autoRotate}>
          <RotateCw /> Rotate
        </Button>
        <Button size="sm" variant="ghost" className="h-7 rounded-full" onClick={takeScreenshot} title="Download PNG screenshot">
          <Camera /> PNG
        </Button>
        <Button size="sm" variant="ghost" className="h-7 rounded-full" onClick={resetView} title="Reset camera, explode, X-ray and visibility">
          <RotateCcw /> Reset
        </Button>
        {fs.supported && (
          <Button size="sm" variant="ghost" className="h-7 rounded-full" onClick={fs.toggle} aria-pressed={fs.on} title={fs.on ? "Exit fullscreen" : "Fullscreen viewer"}>
            {fs.on ? <Minimize /> : <Maximize />} {fs.on ? "Exit" : "Fullscreen"}
          </Button>
        )}
      </div>

      <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center gap-3">
        <div className="flex min-w-[240px] flex-1 items-center gap-3 rounded-lg border border-line bg-panel/90 px-3 py-2 sm:max-w-sm">
          <Layers className="size-4 text-ink-2" aria-hidden />
          <span className="text-xs text-ink-2">Exploded view</span>
          <Slider value={[explode * 100]} min={0} max={100} step={1} onValueChange={([v]) => setExplode(v / 100)} aria-label="Exploded view amount" className="flex-1" />
          <span className="w-9 text-right font-mono text-xs text-ink">{Math.round(explode * 100)}%</span>
        </div>
        {isolatedId && (
          <div className="flex items-center gap-2 rounded-lg border border-accent/40 bg-panel/90 px-3 py-2 text-xs text-ink">
            <Eye className="size-4 text-accent" aria-hidden />
            Isolated: {components.find((c) => c.id === isolatedId)?.name}
            <Button size="sm" variant="outline" onClick={showAll}>
              <Maximize2 /> Show all
            </Button>
          </div>
        )}
        <div className={cn("ml-auto hidden items-center gap-1.5 rounded-lg border border-line bg-panel/90 px-3 py-2 text-[11px] text-ink-3 md:flex")}>
          <Box className="size-3.5" aria-hidden /> Drag to orbit · scroll to zoom · click a part to select
        </div>
      </div>
    </div>
  );
}

