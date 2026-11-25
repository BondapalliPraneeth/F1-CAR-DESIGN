import { Hammer, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { Slider } from "@/components/ui/slider";
import { classifySeverity, LEVEL_COLOR } from "@/lib/severity";
import type { Curves } from "@/lib/types";
import { fmt, signed } from "@/lib/utils";
import { useStore } from "@/store";

function interp(xs: number[], ys: number[], x: number): number | null {
  if (!xs.length) return null;
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) {
    if (x <= xs[i]) {
      const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1] || 1);
      return ys[i - 1] + t * (ys[i] - ys[i - 1]);
    }
  }
  return ys[ys.length - 1];
}

/** Quick damage tool: pick a component, damage type and level, then apply it to the simulation. */
export function DamageCard() {
  const components = useStore((s) => s.components);
  const selectedId = useStore((s) => s.selectedId);
  const damage = useStore((s) => s.damage);
  const result = useStore((s) => s.result);
  const simulating = useStore((s) => s.simulating);
  const { setDamage, select } = useStore.getState();

  const [target, setTarget] = useState<string>(selectedId ?? components[0]?.id ?? "");
  useEffect(() => {
    if (selectedId) setTarget(selectedId);
  }, [selectedId]);
  const comp = components.find((c) => c.id === target);
  const applied = damage[target];
  const [type, setType] = useState<string>("");
  const [level, setLevel] = useState(0);
  useEffect(() => {
    setType(applied?.damage_type ?? comp?.damage_types[0]?.id ?? "");
    setLevel(applied?.severity ?? 40);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [target]);

  if (!comp) return null;
  const sev = classifySeverity(level);
  const curves = result?.curves as Curves | undefined;

  // Estimate before applying: only from the backend's own severity sweep for this exact component + damage type.
  const sw = curves && "severity_sweep" in curves ? curves.severity_sweep : null;
  const sweepEst = sw && sw.component_id === target && sw.damage_type === type ? interp(sw.severity, sw.delta_lap_s, level) : null;
  const appliedImpact = curves && "lap_time_impact" in curves ? curves.lap_time_impact.by_damage.find((d) => d.component_id === target) : undefined;
  const isApplied = !!applied && applied.damage_type === type && applied.severity === level;

  return (
    <section id="damage-sim" className="flex h-full scroll-mt-28 flex-col rounded-xl border border-accent/60 bg-gradient-to-b from-accent/10 to-panel p-3 shadow-[0_0_24px_rgba(239,59,45,0.12)]" aria-label="Simulate damage">
      <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-ink">
        <Hammer className="size-4 text-accent" aria-hidden /> Simulate Damage
      </h3>
      <label className="mb-1.5 block text-[11px] text-ink-3">
        Component
        <select
          className="mt-0.5 h-8 w-full rounded-md border border-line bg-panel2 px-2 text-xs text-ink focus:outline-none focus:ring-2 focus:ring-accent"
          value={target}
          onChange={(e) => setTarget(e.target.value)}
          aria-label="Component to damage"
          data-testid="damage-card-component"
        >
          {components.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </label>
      <label className="mb-2 block text-[11px] text-ink-3">
        Damage type
        <select
          className="mt-0.5 h-8 w-full rounded-md border border-line bg-panel2 px-2 text-xs text-ink focus:outline-none focus:ring-2 focus:ring-accent"
          value={type}
          onChange={(e) => setType(e.target.value)}
          aria-label="Damage type to apply"
        >
          {comp.damage_types.map((d) => (
            <option key={d.id} value={d.id}>
              {d.label}
            </option>
          ))}
        </select>
      </label>
      <div className="mb-1 flex items-center justify-between text-[11px] text-ink-3">
        <span>Damage level</span>
        <span className="flex items-center gap-1.5">
          <span className="font-mono text-xs text-ink" data-testid="damage-card-level">
            {level}%
          </span>
          <SeverityBadge level={sev} />
        </span>
      </div>
      <Slider value={[level]} min={0} max={100} step={1} onValueChange={([v]) => setLevel(v)} aria-label="Damage level" rangeColor={LEVEL_COLOR[sev]} />
      <div className="mt-2 rounded-md border border-line bg-panel/80 px-2 py-1.5 text-[11px]">
        <div className="text-ink-3">Estimated lap time impact</div>
        <div className="font-mono text-sm text-ink" data-testid="damage-card-impact">
          {isApplied && appliedImpact ? (
            <>
              {signed(appliedImpact.delta_lap_s, 3)} s <span className="text-[10px] font-sans text-ink-3">(applied, simulated)</span>
            </>
          ) : sweepEst !== null ? (
            <>
              ≈ {signed(sweepEst, 3)} s <span className="text-[10px] font-sans text-ink-3">(from severity sweep)</span>
            </>
          ) : (
            <span className="font-sans text-xs text-ink-2">Apply to compute with the backend model</span>
          )}
        </div>
      </div>
      <div className="mt-auto flex gap-1.5 pt-2">
        <Button
          size="sm"
          className="flex-1"
          disabled={!type || simulating || isApplied}
          onClick={() => {
            setDamage(target, level > 0 ? { damage_type: type, severity: level } : null);
            select(target);
          }}
          data-testid="apply-damage"
        >
          <Hammer /> Apply Damage
        </Button>
        {applied && applied.severity > 0 && (
          <Button size="sm" variant="outline" onClick={() => setDamage(target, null)} title={`Repair ${comp.name}`} aria-label={`Repair ${comp.name}`}>
            <RotateCcw />
          </Button>
        )}
      </div>
      {appliedImpact && !isApplied && <p className="mt-1 text-[10px] text-ink-3">Currently applied: {fmt(applied?.severity ?? 0, 0)}% → {signed(appliedImpact.delta_lap_s, 3)} s</p>}
    </section>
  );
}
