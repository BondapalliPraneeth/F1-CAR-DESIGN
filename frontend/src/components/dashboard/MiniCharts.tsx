import { useMemo } from "react";
import type { Curves } from "@/lib/types";
import { useStore } from "@/store";
import { PlotlyChart, SERIES, type Trace } from "./PlotlyChart";

const COMPACT = { margin: { l: 40, r: 8, t: 4, b: 24 }, hovermode: "x unified" as const };

const ln = (name: string, x: number[], y: number[], color: string, dash = false, unit = ""): Trace => ({
  type: "scatter",
  mode: "lines",
  name,
  x,
  y,
  line: { color, width: 2, dash: dash ? "dash" : "solid", shape: "spline", smoothing: 0.3 },
  hovertemplate: `${name}: %{y:,.1f}${unit}<extra></extra>`,
});

/** Three compact charts for the overview row. Same backend curves as the full dashboard. */
export default function MiniCharts() {
  const result = useStore((s) => s.result);
  const c = result?.curves as Curves | undefined;
  const has = !!c && "aero_vs_speed" in c;

  const t = useMemo(() => {
    if (!has || !c) return null;
    const av = c.aero_vs_speed;
    const td = c.tyre_degradation.current;
    const lt = c.lap_trace;
    const km = lt.distance_m.map((d) => d / 1000);
    return {
      downforce: [ln("Healthy", av.baseline.speed_kmh, av.baseline.downforce_n, SERIES.baseline, true, " N"), ln("Current", av.current.speed_kmh, av.current.downforce_n, SERIES.current, false, " N")],
      tyres: [ln("Front", td.lap, td.grip_front, SERIES.baseline), ln("Rear", td.lap, td.grip_rear, SERIES.current)],
      brakes: [ln("Front", km, lt.brake_front_current_c, SERIES.baseline, false, " °C"), ln("Rear", km, lt.brake_rear_current_c, SERIES.current, false, " °C")],
    };
  }, [c, has]);

  if (!t) return <div className="col-span-3 grid place-items-center rounded-xl border border-dashed border-line text-xs text-ink-3">Waiting for simulation curves…</div>;
  return (
    <>
      <PlotlyChart title="Downforce vs Speed" subtitle="Downforce [N] vs speed [km/h], healthy (dashed) vs current" traces={t.downforce} xTitle="" yTitle="" layout={COMPACT} height={170} testId="mini-downforce" digits={0} />
      <PlotlyChart title="Tyre Grip over Stint" subtitle="Grip factor vs lap, current car" traces={t.tyres} xTitle="" yTitle="" layout={COMPACT} height={170} testId="mini-tyres" digits={3} />
      <PlotlyChart title="Brake Temperature" subtitle="Disc temperature [°C] vs distance [km], one lap" traces={t.brakes} xTitle="" yTitle="" layout={COMPACT} height={170} testId="mini-brakes" digits={0} />
    </>
  );
}
