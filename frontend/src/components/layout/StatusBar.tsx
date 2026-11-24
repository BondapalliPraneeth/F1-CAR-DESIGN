import { AlertOctagon, Loader2 } from "lucide-react";
import { fmt, signed } from "@/lib/utils";
import { useStore } from "@/store";

function Stat({ label, value, delta, testId }: { label: string; value: string; delta?: string; testId?: string }) {
  return (
    <div className="min-w-[92px] px-3 py-2" data-testid={testId}>
      <div className="text-[10px] uppercase tracking-wide text-ink-3">{label}</div>
      <div className="font-mono text-sm text-ink">
        {value}
        {delta && <span className="ml-1 text-[11px] text-ink-2">{delta}</span>}
      </div>
    </div>
  );
}

export function StatusBar() {
  const r = useStore((s) => s.result);
  const b = useStore((s) => s.baseline);
  const simulating = useStore((s) => s.simulating);
  if (!r) return <div className="h-[52px] border-b border-line bg-panel" />;
  const dLap = b ? r.performance.lap_time_s - b.performance.lap_time_s : undefined;
  return (
    <div className="flex items-stretch overflow-x-auto border-b border-line bg-panel" aria-live="polite">
      <Stat label="Overall health" value={`${fmt(r.overall_health_pct, 1)}%`} testId="stat-health" />
      <Stat label="Performance index" value={`${fmt(r.performance_index_pct, 1)}%`} testId="stat-performance" />
      <Stat label="Lap time" value={`${fmt(r.performance.lap_time_s, 3)} s`} delta={dLap !== undefined ? `${signed(dLap, 3)}` : undefined} testId="stat-lap" />
      <Stat label="Top speed" value={`${fmt(r.performance.top_speed_kmh, 1)} km/h`} />
      <Stat label={`Downforce @${r.aero.reference_speed_kmh}`} value={`${fmt(r.aero.downforce_n, 0)} N`} testId="stat-downforce" />
      <Stat label={`Drag @${r.aero.reference_speed_kmh}`} value={`${fmt(r.aero.drag_n, 0)} N`} />
      <Stat label="Front balance" value={`${fmt(r.aero.front_balance_pct, 1)}%`} />
      <Stat label="Structural" value={`${fmt(r.structural_integrity_pct, 1)}%`} />
      <div className="ml-auto flex items-center gap-2 px-3">
        {r.retire_recommended && (
          <span className="flex items-center gap-1 rounded border border-sev-critical/50 bg-sev-critical/10 px-2 py-1 text-[11px] font-medium text-ink" data-testid="retire-flag">
            <AlertOctagon className="size-3.5 text-sev-critical" aria-hidden /> Retirement recommended
          </span>
        )}
        {simulating && <Loader2 className="size-4 animate-spin text-accent" aria-label="Simulating" />}
        <span className="whitespace-nowrap rounded border border-line px-1.5 py-0.5 text-[10px] font-semibold tracking-wider text-ink-2" title={r.label}>
          MODEL-ESTIMATED
        </span>
      </div>
    </div>
  );
}
