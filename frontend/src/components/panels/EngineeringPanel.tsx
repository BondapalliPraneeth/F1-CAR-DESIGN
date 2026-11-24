import { AlertTriangle, Eye, EyeOff, Focus, Info, RotateCcw, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SeverityBadge } from "@/components/ui/severity-badge";
import { Slider } from "@/components/ui/slider";
import { api } from "@/lib/api";
import { classifySeverity, LEVEL_COLOR } from "@/lib/severity";
import type { ComponentDetail } from "@/lib/types";
import { cn, fmt } from "@/lib/utils";
import { useStore } from "@/store";
import { AnalysisPanel } from "./AnalysisPanel";

const detailCache = new Map<string, ComponentDetail>();

const QUICK_LEVELS = [
  { label: "Healthy", value: 0 },
  { label: "Minor", value: 15 },
  { label: "Moderate", value: 35 },
  { label: "Severe", value: 60 },
  { label: "Critical", value: 90 },
];

function useComponentDetail(id: string | null) {
  const [detail, setDetail] = useState<ComponentDetail | null>(id ? (detailCache.get(id) ?? null) : null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!id) {
      setDetail(null);
      return;
    }
    const cached = detailCache.get(id);
    if (cached) {
      setDetail(cached);
      return;
    }
    let live = true;
    setDetail(null);
    setError(null);
    api
      .component(id)
      .then((d) => {
        detailCache.set(id, d);
        if (live) setDetail(d);
      })
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [id]);
  return { detail, error };
}

export function EngineeringPanel() {
  const selectedId = useStore((s) => s.selectedId);
  if (!selectedId) return <CarOverview />;
  return <ComponentPanel id={selectedId} />;
}

function CarOverview() {
  const car = useStore((s) => s.car);
  const result = useStore((s) => s.result);
  const components = useStore((s) => s.components);
  const select = useStore((s) => s.select);
  const damaged = result?.component_health.filter((h) => h.severity_pct > 0) ?? [];
  return (
    <div className="space-y-4 p-4" data-testid="car-overview">
      <div>
        <h2 className="text-base font-semibold text-ink">{car?.name ?? "ApexVision AV-1"}</h2>
        <p className="mt-1 text-xs leading-relaxed text-ink-2">{car?.description}</p>
      </div>
      <div className="rounded-md border border-line bg-panel2 p-3 text-xs text-ink-2">
        <Info className="mb-1 size-4 text-accent" aria-hidden />
        Select any of the {components.length} components in the 3D view or the list to see its engineering data and to apply damage. Every number shown is
        <strong className="text-ink"> model-estimated</strong> from the simplified physics described in the methodology docs; nothing here is CFD or real-car data.
      </div>
      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-2">Damaged components</h3>
        {damaged.length === 0 ? (
          <p className="text-xs text-ink-3">None. The car is in its healthy baseline state.</p>
        ) : (
          <ul className="space-y-1">
            {damaged.map((h) => (
              <li key={h.component_id}>
                <button className="flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs hover:bg-panel2" onClick={() => select(h.component_id)}>
                  <span className="text-ink">{h.name}</span>
                  <span className="flex items-center gap-2">
                    <span className="font-mono text-ink-2">{fmt(h.severity_pct, 0)}%</span>
                    <SeverityBadge level={h.level} />
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {result && result.warnings.length > 0 && <Warnings warnings={result.warnings} />}
    </div>
  );
}

function Warnings({ warnings }: { warnings: string[] }) {
  return (
    <div className="space-y-1.5" data-testid="warnings">
      {warnings.map((w) => (
        <div key={w} className="flex gap-2 rounded-md border border-sev-severe/40 bg-sev-severe/10 px-2.5 py-2 text-xs text-ink">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-sev-severe" aria-hidden />
          <span>{w}</span>
        </div>
      ))}
    </div>
  );
}

function ComponentPanel({ id }: { id: string }) {
  const summary = useStore((s) => s.components.find((c) => c.id === id));
  const entry = useStore((s) => s.damage[id]);
  const result = useStore((s) => s.result);
  const baseline = useStore((s) => s.baseline);
  const hidden = useStore((s) => !!s.hidden[id]);
  const isolatedId = useStore((s) => s.isolatedId);
  const { select, setDamage, setSeverity, toggleHidden, isolate, showAll } = useStore.getState();
  const { detail, error } = useComponentDetail(id);
  if (!summary) return null;

  const damageType = entry?.damage_type ?? summary.damage_types[0]?.id;
  const severity = entry?.severity ?? 0;
  const level = classifySeverity(severity);
  const dtInfo = summary.damage_types.find((d) => d.id === damageType);
  const mechanism = result?.mechanisms.find((m) => m.component_id === id);
  const health = result?.component_health.find((h) => h.component_id === id);

  return (
    <div className="space-y-4 p-4" data-testid="component-panel">
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-ink" data-testid="component-name">
            {summary.name}
          </h2>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <Badge className="capitalize">{summary.category}</Badge>
            <Badge>Susceptibility: {summary.damage_susceptibility}</Badge>
            {health && <Badge>Health {fmt(health.health_pct, 0)}%</Badge>}
          </div>
        </div>
        <Button size="icon" variant="ghost" onClick={() => select(null)} aria-label="Close component panel">
          <X />
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <Button size="sm" variant="outline" onClick={() => toggleHidden(id)} aria-pressed={hidden}>
          {hidden ? <Eye /> : <EyeOff />} {hidden ? "Show" : "Hide"}
        </Button>
        {isolatedId === id ? (
          <Button size="sm" variant="outline" active onClick={showAll}>
            <Focus /> Exit isolate
          </Button>
        ) : (
          <Button size="sm" variant="outline" onClick={() => isolate(id)}>
            <Focus /> Isolate
          </Button>
        )}
      </div>

      {/* Damage controls */}
      <section className="rounded-lg border border-line bg-panel2 p-3" aria-label="Damage simulation">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-2">Damage simulation</h3>
          <SeverityBadge level={level} />
        </div>
        {summary.damage_types.length > 1 && (
          <div className="mb-3 flex flex-wrap gap-1" role="radiogroup" aria-label="Damage type">
            {summary.damage_types.map((d) => (
              <Button
                key={d.id}
                size="sm"
                variant="outline"
                role="radio"
                aria-checked={d.id === damageType}
                active={d.id === damageType}
                onClick={() => setDamage(id, { damage_type: d.id, severity })}
              >
                {d.label}
              </Button>
            ))}
          </div>
        )}
        {summary.damage_types.length === 1 && <p className="mb-2 text-xs text-ink">{dtInfo?.label}</p>}
        <div className="flex items-center gap-3">
          <Slider
            value={[severity]}
            min={0}
            max={100}
            step={1}
            onValueChange={([v]) => setSeverity(id, v)}
            aria-label="Damage severity"
            rangeColor={LEVEL_COLOR[level]}
            className="flex-1"
            data-testid="severity-slider"
          />
          <span className="w-12 text-right font-mono text-sm text-ink" data-testid="severity-value">
            {severity}%
          </span>
        </div>
        <div className="mt-1 grid grid-cols-5 text-center text-[10px] text-ink-3" aria-hidden>
          <span>0</span>
          <span>≤20</span>
          <span>≤45</span>
          <span>≤75</span>
          <span>≤100</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {QUICK_LEVELS.map((q) => (
            <Button key={q.label} size="sm" variant="ghost" className={cn("h-7 px-2", classifySeverity(severity) === classifySeverity(q.value) && "text-ink")} onClick={() => setSeverity(id, q.value)}>
              {q.label}
            </Button>
          ))}
          {severity > 0 && (
            <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => setDamage(id, null)}>
              <RotateCcw /> Repair
            </Button>
          )}
        </div>
        {dtInfo && (
          <div className="mt-3 space-y-1 text-xs text-ink-2">
            <p>{dtInfo.description}</p>
            <p className="text-ink-3">
              <span className="text-ink-2">3D representation:</span> {dtInfo.visual} Visual only; there is no structural deformation or fracture model.
            </p>
          </div>
        )}
        {mechanism && (
          <p className="mt-2 rounded border border-line bg-panel p-2 text-xs text-ink-2" data-testid="mechanism">
            <span className="font-medium text-ink">Model mechanism: </span>
            {mechanism.explanation}
          </p>
        )}
      </section>

      <AnalysisPanel panel={summary.analysis_panel} componentId={id} result={result} baseline={baseline} />

      {/* Engineering data */}
      {error && <p className="text-xs text-sev-critical">Could not load component details: {error}</p>}
      {!detail && !error && <p className="text-xs text-ink-3">Loading engineering data…</p>}
      {detail && (
        <section className="space-y-3 text-xs" aria-label="Engineering data">
          <Field label="Position" value={detail.position} />
          <Field label="Purpose" value={detail.purpose} />
          <Field label="Primary function" value={detail.primary_function} />
          <Field label="Construction" value={detail.construction} />
          <Field label="Performance contribution" value={detail.performance_contribution} />
          <Field label="Engineering explanation" value={detail.engineering_explanation} />
          <div>
            <div className="mb-1 font-medium text-ink-2">Failure modes</div>
            <ul className="list-disc space-y-0.5 pl-4 text-ink">
              {detail.failure_modes.map((f) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
            <p className="mt-1 text-ink-3">{detail.susceptibility_note}</p>
          </div>
          {detail.parameters.length > 0 && (
            <div>
              <div className="mb-1 font-medium text-ink-2">Model parameters</div>
              <table className="w-full">
                <tbody>
                  {detail.parameters.map((p) => (
                    <tr key={p.name} className="border-t border-line/60">
                      <td className="py-1 pr-2 text-ink-2">{p.name}</td>
                      <td className="py-1 text-right font-mono text-ink">
                        {typeof p.value === "number" ? fmt(p.value, Number.isInteger(p.value) ? 0 : 3) : String(p.value)} {p.unit}
                      </td>
                      <td className="py-1 pl-2 text-right text-[10px] text-ink-3">{p.source}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {detail.related.length > 0 && (
            <div>
              <div className="mb-1 font-medium text-ink-2">Related components</div>
              <div className="flex flex-wrap gap-1">
                {detail.related.map((r) => (
                  <Button key={r} size="sm" variant="outline" className="h-7" onClick={() => select(r)}>
                    {useStore.getState().components.find((c) => c.id === r)?.name ?? r}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="mb-0.5 font-medium text-ink-2">{label}</div>
      <p className="leading-relaxed text-ink">{value}</p>
    </div>
  );
}
