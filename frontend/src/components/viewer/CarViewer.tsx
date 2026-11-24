import { ContactShadows, Environment, Grid, Lightformer, OrbitControls, useProgress } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Box, Camera, Eye, Layers, Maximize2, RotateCw, ScanEye } from "lucide-react";
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

export const CAMERA_PRESETS: Record<CameraPreset, { pos: [number, number, number]; label: string }> = {
  front: { pos: [7, 1.2, 0], label: "Front" },
  rear: { pos: [-7, 1.5, 0], label: "Rear" },
  side: { pos: [0, 1.2, 7], label: "Side" },
  top: { pos: [0, 8, 0.01], label: "Top" },
  iso: { pos: [5, 3.5, 5], label: "Iso" },
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
  const preset = useStore((s) => s.camera.preset);
  const isolatedId = useStore((s) => s.isolatedId);
  const { setExplode, setXray, setAutoRotate, setCamera, takeScreenshot, showAll, select } = useStore.getState();

  const hoverComp = hover ? components.find((c) => c.id === hover.component) : undefined;
  const hoverSev = hover ? (damage[hover.component]?.severity ?? 0) : 0;

  return (
    <div className="relative h-full w-full overflow-hidden bg-[radial-gradient(ellipse_at_50%_40%,#152033_0%,#090d14_70%)]" data-testid="car-viewer">
      <ViewerBoundary>
        <Canvas
          shadows
          dpr={[1, 2]}
          gl={{ preserveDrawingBuffer: true, antialias: true, toneMapping: THREE.ACESFilmicToneMapping }}
          camera={{ position: CAMERA_PRESETS.iso.pos, fov: 38, near: 0.05, far: 100 }}
          onPointerMissed={() => select(null)}
        >
          <color attach="background" args={["#0b111b"]} />
          <fog attach="fog" args={["#0b111b", 14, 30]} />
          <ambientLight intensity={0.25} />
          <directionalLight position={[4, 8, 5]} intensity={1.6} castShadow shadow-mapSize={[2048, 2048]} shadow-bias={-0.0004}>
            <orthographicCamera attach="shadow-camera" args={[-5, 5, 5, -5, 0.5, 25]} />
          </directionalLight>
          <Environment resolution={256}>
            <Lightformer form="rect" intensity={2.2} position={[0, 6, 0]} rotation-x={Math.PI / 2} scale={[10, 4, 1]} />
            <Lightformer form="rect" intensity={1.2} position={[-6, 2, 4]} rotation-y={Math.PI / 3} scale={[8, 2, 1]} />
            <Lightformer form="rect" intensity={1.2} position={[6, 2, -4]} rotation-y={-Math.PI / 3} scale={[8, 2, 1]} />
            <Lightformer form="ring" color="#16c7bd" intensity={0.6} position={[0, 3, -8]} scale={3} />
          </Environment>
          <Suspense fallback={null}>
            <CarModel url={assetUrl} onHover={setHover} />
          </Suspense>
          <ContactShadows position={[0, 0.002, 0]} opacity={0.55} scale={9} blur={2.2} far={2} resolution={512} />
          <Grid
            position={[0, 0, 0]}
            args={[30, 30]}
            cellSize={0.5}
            cellThickness={0.5}
            cellColor="#1b2536"
            sectionSize={2.5}
            sectionThickness={1}
            sectionColor="#24324a"
            fadeDistance={22}
            fadeStrength={1.5}
            infiniteGrid
          />
          <OrbitControls makeDefault target={TARGET} enableDamping minDistance={2.5} maxDistance={16} maxPolarAngle={Math.PI / 2 - 0.02} autoRotate={autoRotate} autoRotateSpeed={0.8} />
          <CameraRig />
          <Screenshotter />
        </Canvas>
        <Loader />
      </ViewerBoundary>

      {hover && hoverComp && (
        <div
          className="pointer-events-none absolute z-10 rounded-md border border-line bg-panel/95 px-2.5 py-1.5 text-xs shadow-lg"
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
      <div className="absolute left-3 top-3 flex flex-wrap items-center gap-1 rounded-lg border border-line bg-panel/90 p-1 backdrop-blur" role="toolbar" aria-label="Camera views">
        {(Object.keys(CAMERA_PRESETS) as CameraPreset[]).map((p) => (
          <Button key={p} size="sm" variant="ghost" active={preset === p} onClick={() => setCamera(p)} aria-label={`${CAMERA_PRESETS[p].label} view`}>
            {CAMERA_PRESETS[p].label}
          </Button>
        ))}
      </div>

      <div className="absolute right-3 top-3 flex items-center gap-1 rounded-lg border border-line bg-panel/90 p-1 backdrop-blur" role="toolbar" aria-label="View options">
        <Button size="sm" variant="ghost" active={xray} onClick={() => setXray(!xray)} title="X-ray: ghost all but the selected component" aria-pressed={xray}>
          <ScanEye /> X-ray
        </Button>
        <Button size="sm" variant="ghost" active={autoRotate} onClick={() => setAutoRotate(!autoRotate)} title="Auto-rotate" aria-pressed={autoRotate}>
          <RotateCw /> Rotate
        </Button>
        <Button size="sm" variant="ghost" onClick={takeScreenshot} title="Download PNG screenshot">
          <Camera /> PNG
        </Button>
      </div>

      <div className="absolute bottom-3 left-3 right-3 flex flex-wrap items-center gap-3">
        <div className="flex min-w-[240px] flex-1 items-center gap-3 rounded-lg border border-line bg-panel/90 px-3 py-2 backdrop-blur sm:max-w-sm">
          <Layers className="size-4 text-ink-2" aria-hidden />
          <span className="text-xs text-ink-2">Exploded view</span>
          <Slider value={[explode * 100]} min={0} max={100} step={1} onValueChange={([v]) => setExplode(v / 100)} aria-label="Exploded view amount" className="flex-1" />
          <span className="w-9 text-right font-mono text-xs text-ink">{Math.round(explode * 100)}%</span>
        </div>
        {isolatedId && (
          <div className="flex items-center gap-2 rounded-lg border border-accent/40 bg-panel/90 px-3 py-2 text-xs text-ink backdrop-blur">
            <Eye className="size-4 text-accent" aria-hidden />
            Isolated: {components.find((c) => c.id === isolatedId)?.name}
            <Button size="sm" variant="outline" onClick={showAll}>
              <Maximize2 /> Show all
            </Button>
          </div>
        )}
        <div className={cn("ml-auto hidden items-center gap-1.5 rounded-lg border border-line bg-panel/90 px-3 py-2 text-[11px] text-ink-3 backdrop-blur md:flex")}>
          <Box className="size-3.5" aria-hidden /> Drag to orbit · scroll to zoom · click a part to select
        </div>
      </div>
    </div>
  );
}

