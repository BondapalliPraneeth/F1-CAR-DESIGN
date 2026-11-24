import { ArrowDownRight, ArrowUpRight, Minus, MoveHorizontal } from "lucide-react";
import type { SimulationResult } from "@/lib/types";
import { fmt, signed } from "@/lib/utils";
import { PANEL_METRICS, verdict } from "./metrics";

const VERDICT_STYLE = {
  better: { Icon: ArrowUpRight, color: "#22c55e", label: "better than baseline" },
  worse: { Icon: ArrowDownRight, color: "#ef4444", label: "worse than baseline" },
  neutral: { Icon: MoveHorizontal, color: "#a3b0c2", label: "changed" },
  same: { Icon: Minus, color: "#6b7a90", label: "unchanged" },
} as const;

export function AnalysisPanel({
  panel,
  componentId,
  result,
  baseline,
}: {
  panel: string;
  componentId: string;
  result: SimulationResult | null;
  baseline: SimulationResult | null;
}) {
  const def = PANEL_METRICS[panel];
  if (!def) return null;
  if (!result || !baseline) return <p className="text-xs text-ink-3">Waiting for simulation results…</p>;

  const df = result.aero.downforce_by_component_n[componentId];
  const dfBase = baseline.aero.downforce_by_component_n[componentId];
  const dr = result.aero.drag_by_component_n[componentId];
  const drBase = baseline.aero.drag_by_component_n[componentId];

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-2">{def.title}</h4>
        <span className="text-[10px] text-ink-3">vs healthy baseline</span>
      </div>
      <table className="w-full text-xs" data-testid="analysis-table">
        <thead>
          <tr className="text-left text-[10px] uppercase tracking-wide text-ink-3">
            <th className="py-1 font-medium">Metric</th>
            <th className="py-1 text-right font-medium">Baseline</th>
            <th className="py-1 text-right font-medium">Current</th>
            <th className="py-1 text-right font-medium">Δ</th>
          </tr>
        </thead>
        <tbody>
          {df !== undefined && dfBase !== undefined && (
            <Row label="This component's downforce share" unit="N" digits={0} base={dfBase} cur={df} better={true} />
          )}
          {dr !== undefined && drBase !== undefined && <Row label="This component's drag share" unit="N" digits={0} base={drBase} cur={dr} better={false} />}
          {def.metrics.map((mdef) => (
            <Row key={mdef.label} label={mdef.label} unit={mdef.unit} digits={mdef.digits} base={mdef.get(baseline)} cur={mdef.get(result)} better={mdef.better} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Row({ label, unit, digits, base, cur, better }: { label: string; unit: string; digits: number; base?: number; cur?: number; better: boolean | null }) {
  const v = verdict({ label, unit, digits, better, get: () => 0 }, base, cur);
  const { Icon, color, label: vl } = VERDICT_STYLE[v];
  const delta = base !== undefined && cur !== undefined ? cur - base : undefined;
  return (
    <tr className="border-t border-line/60">
      <td className="py-1.5 pr-2 text-ink-2">
        {label}
        {unit && <span className="text-ink-3"> [{unit}]</span>}
      </td>
      <td className="py-1.5 text-right font-mono text-ink-2">{fmt(base, digits)}</td>
      <td className="py-1.5 text-right font-mono text-ink">{fmt(cur, digits)}</td>
      <td className="py-1.5 pl-2 text-right font-mono text-ink">
        <span className="inline-flex items-center justify-end gap-0.5" title={vl}>
          {delta === undefined ? "-" : signed(delta, digits)}
          <Icon className="size-3" style={{ color }} aria-label={vl} />
        </span>
      </td>
    </tr>
  );
}
