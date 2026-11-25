import { AlertOctagon, Gauge, Loader2 } from "lucide-react";
import { cn, fmt, signed } from "@/lib/utils";
import { useStore } from "@/store";

function Stat({ label, value, delta, worse, testId }: { label: string; value: string; delta?: string; worse?: boolean; testId?: string }) {
  return (
    <div className="rounded-lg border border-line/70 bg-panel2/60 px-2.5 py-2" data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wide text-ink-3">{label}</div>
      <div className="font-mono text-sm font-semibold text-ink">
        {value}
        {delta && <span className={cn("ml-1 text-[11px] font-normal", worse ? "text-accent" : "text-ink-2")}>{delta}</span>}
      </div>
    </div>
  );
}

/** Vehicle performance card: every value comes from the latest backend simulation. */
export function StatusBar() {
  const r = useStore((s) => s.result);
  const b = useStore((s) => s.baseline);
  const simulating = useStore((s) => s.simulating);
  return (
    <section className="flex h-full flex-col rounded-xl border border-line bg-panel p-3" aria-live="polite" aria-label="Vehicle performance">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
          <Gauge className="size-4 text-accent" aria-hidden /> Vehicle Performance
        </h3>
        <div className="flex items-center gap-1.5">
          {simulating && <Loader2 className="size-3.5 animate-spin text-accent" aria-label="Simulating" />}
          <span className="whitespace-nowrap rounded border border-line px-1.5 py-0.5 text-[9px] font-semibold tracking-wider text-ink-2" title={r?.label}>
            MODEL-ESTIMATED
          </span>
        </div>
      </div>
      {!r ? (
        <p className="text-xs text-ink-3">Waiting for the first simulation…</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-1.5">
            <Stat label="Lap time" value={`${fmt(r.performance.lap_time_s, 3)} s`} delta={b ? signed(r.performance.lap_time_s - b.performance.lap_time_s, 3) : undefined} worse={!!b && r.performance.lap_time_s - b.performance.lap_time_s > 0.0005} testId="stat-lap" />
            <Stat label="Top speed" value={`${fmt(r.performance.top_speed_kmh, 1)} km/h`} />
            <Stat label={`Downforce @${r.aero.reference_speed_kmh}`} value={`${fmt(r.aero.downforce_n, 0)} N`} testId="stat-downforce" />
            <Stat label={`Drag @${r.aero.reference_speed_kmh}`} value={`${fmt(r.aero.drag_n, 0)} N`} />
            <Stat label="Overall health" value={`${fmt(r.overall_health_pct, 1)}%`} testId="stat-health" />
            <Stat label="Performance index" value={`${fmt(r.performance_index_pct, 1)}%`} testId="stat-performance" />
            <Stat label="Front balance" value={`${fmt(r.aero.front_balance_pct, 1)}%`} />
            <Stat label="Structural" value={`${fmt(r.structural_integrity_pct, 1)}%`} />
          </div>
          {r.retire_recommended && (
            <span className="mt-2 flex items-center gap-1 rounded border border-sev-critical/50 bg-sev-critical/10 px-2 py-1 text-[11px] font-medium text-ink" data-testid="retire-flag">
              <AlertOctagon className="size-3.5 text-sev-critical" aria-hidden /> Retirement recommended
            </span>
          )}
        </>
      )}
    </section>
  );
}
