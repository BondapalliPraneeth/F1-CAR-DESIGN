import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { LEVEL_COLOR, LEVEL_LABEL } from "@/lib/severity";
import type { Curves } from "@/lib/types";
import { useStore } from "@/store";
import { PlotlyChart, SERIES, type Trace } from "./PlotlyChart";

const line = (name: string, x: number[], y: number[], color: string, dashed = false, unit = ""): Trace => ({
  type: "scatter",
  mode: "lines",
  name,
  x,
  y,
  line: { color, width: 2, dash: dashed ? "dash" : "solid", shape: "spline", smoothing: 0.3 },
  hovertemplate: `${name}: %{y:,.1f}${unit}<extra></extra>`,
});

function AxleToggle({ value, onChange }: { value: "front" | "rear"; onChange: (v: "front" | "rear") => void }) {
  return (
    <div className="flex gap-1" role="radiogroup" aria-label="Axle">
      {(["front", "rear"] as const).map((a) => (
        <Button key={a} size="sm" variant="ghost" className="h-6 px-2 text-[11px] capitalize" active={value === a} role="radio" aria-checked={value === a} onClick={() => onChange(a)}>
          {a}
        </Button>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const result = useStore((s) => s.result);
  const components = useStore((s) => s.components);
  const simError = useStore((s) => s.simError);
  const [brakeAxle, setBrakeAxle] = useState<"front" | "rear">("front");
  const [tyreAxle, setTyreAxle] = useState<"front" | "rear">("front");

  const c = result?.curves as Curves | undefined;
  const hasCurves = !!c && "aero_vs_speed" in c;

  const charts = useMemo(() => {
    if (!hasCurves || !c) return null;
    const av = c.aero_vs_speed;
    const lt = c.lap_trace;
    const km = lt.distance_m.map((d) => d / 1000);
    const nameOf = (id: string) => components.find((x) => x.id === id)?.name ?? id;

    const downforce = [
      line("Baseline", av.baseline.speed_kmh, av.baseline.downforce_n, SERIES.baseline, true, " N"),
      line("Current", av.current.speed_kmh, av.current.downforce_n, SERIES.current, false, " N"),
    ];
    const drag = [
      line("Baseline", av.baseline.speed_kmh, av.baseline.drag_n, SERIES.baseline, true, " N"),
      line("Current", av.current.speed_kmh, av.current.drag_n, SERIES.current, false, " N"),
    ];
    const balance: Trace[] = [
      {
        type: "bar",
        name: "Baseline",
        x: ["Front axle", "Rear axle"],
        y: [c.balance.baseline.front_pct, c.balance.baseline.rear_pct],
        marker: { color: SERIES.baseline, line: { color: "#0e1016", width: 2 } },
        hovertemplate: "Baseline %{x}: %{y:.1f}%<extra></extra>",
      },
      {
        type: "bar",
        name: "Current",
        x: ["Front axle", "Rear axle"],
        y: [c.balance.current.front_pct, c.balance.current.rear_pct],
        marker: { color: SERIES.current, line: { color: "#0e1016", width: 2 } },
        hovertemplate: "Current %{x}: %{y:.1f}%<extra></extra>",
      },
    ];
    const speed = [
      line("Baseline", km, lt.speed_baseline_kmh, SERIES.baseline, true, " km/h"),
      line("Current", km, lt.speed_current_kmh, SERIES.current, false, " km/h"),
    ];
    const brakeBase = brakeAxle === "front" ? lt.brake_front_baseline_c : lt.brake_rear_baseline_c;
    const brakeCur = brakeAxle === "front" ? lt.brake_front_current_c : lt.brake_rear_current_c;
    const brakes = [line("Baseline", km, brakeBase, SERIES.baseline, true, " °C"), line("Current", km, brakeCur, SERIES.current, false, " °C")];

    const cl = c.coolant_by_lap;
    const coolant = [
      line("Baseline mean", cl.lap, cl.baseline_mean_c, SERIES.baseline, true, " °C"),
      line("Current mean", cl.lap, cl.current_mean_c, SERIES.current, false, " °C"),
      line("Current peak", cl.lap, cl.current_peak_c, SERIES.third, false, " °C"),
    ];
    const coolantLayout: Partial<Plotly.Layout> = {
      shapes: [{ type: "line", xref: "paper", x0: 0, x1: 1, y0: cl.limit_c, y1: cl.limit_c, line: { color: SERIES.limit, width: 1, dash: "dot" } }],
      annotations: [
        { xref: "paper", x: 1, xanchor: "right", y: cl.limit_c, yanchor: "bottom", text: `Derate limit ${cl.limit_c} °C`, showarrow: false, font: { size: 10, color: "#a3b0c2" } },
      ],
    };

    const td = c.tyre_degradation;
    const gripBase = tyreAxle === "front" ? td.baseline.grip_front : td.baseline.grip_rear;
    const gripCur = tyreAxle === "front" ? td.current.grip_front : td.current.grip_rear;
    const tyres = [line("Baseline", td.baseline.lap, gripBase, SERIES.baseline, true), line("Current", td.current.lap, gripCur, SERIES.current, false)];
    const stintLap = [line("Baseline", td.baseline.lap, td.baseline.lap_time_s, SERIES.baseline, true, " s"), line("Current", td.current.lap, td.current.lap_time_s, SERIES.current, false, " s")];

    const impact = c.lap_time_impact.by_damage;
    const impactTrace: Trace[] = [
      {
        type: "bar",
        orientation: "h",
        name: "Lap time loss",
        x: impact.map((d) => d.delta_lap_s),
        y: impact.map((d) => `${nameOf(d.component_id)} (${d.severity}%)`),
        marker: { color: SERIES.current, line: { color: "#0e1016", width: 2 } },
        hovertemplate: "%{y}: %{x:+.3f} s<extra></extra>",
      },
    ];

    const sw = c.severity_sweep;
    const sweepLap = sw ? [line("Lap time loss", sw.severity, sw.delta_lap_s, SERIES.current, false, " s")] : null;
    const sweepAero = sw
      ? [line("Downforce change", sw.severity, sw.downforce_change_pct, SERIES.current, false, " %"), line("Drag change", sw.severity, sw.drag_change_pct, SERIES.third, false, " %")]
      : null;

    const health = [...(result?.component_health ?? [])].sort((a, b) => a.health_pct - b.health_pct);
    const healthTrace: Trace[] = [
      {
        type: "bar",
        orientation: "h",
        name: "Health",
        x: health.map((h) => h.health_pct),
        y: health.map((h) => h.name),
        marker: { color: health.map((h) => LEVEL_COLOR[h.level]), line: { color: "#0e1016", width: 1 } },
        customdata: health.map((h) => LEVEL_LABEL[h.level]),
        hovertemplate: "%{y}: %{x:.0f}% health (%{customdata})<extra></extra>",
      },
    ];
    return { downforce, drag, balance, speed, brakes, coolant, coolantLayout, tyres, stintLap, impactTrace, sweepLap, sweepAero, sw, healthTrace, nHealth: health.length, nameOf, impact };
  }, [c, hasCurves, brakeAxle, tyreAxle, components, result?.component_health]);

  if (simError && !result) return <p className="p-6 text-sm text-sev-critical">No data: {simError}</p>;
  if (!result || !charts) return <p className="p-6 text-sm text-ink-3">Waiting for simulation results…</p>;

  const ref = result.aero.reference_speed_kmh;
  return (
    <div className="space-y-3 p-3" data-testid="dashboard">
      <p className="px-1 text-[11px] text-ink-3">{result.label}. Baseline = healthy car under the same assumptions (dashed); Current = with the applied damage (solid).</p>
      <div className="grid gap-3 lg:grid-cols-2 2xl:grid-cols-3">
        <PlotlyChart title="Downforce vs speed" subtitle="F = ½ρv²·ClA" traces={charts.downforce} xTitle="Speed [km/h]" yTitle="Downforce [N]" testId="chart-downforce" digits={0} />
        <PlotlyChart title="Drag vs speed" subtitle="F = ½ρv²·CdA" traces={charts.drag} xTitle="Speed [km/h]" yTitle="Drag [N]" testId="chart-drag" digits={0} />
        <PlotlyChart
          title="Aerodynamic balance"
          subtitle={`Share of downforce per axle @ ${ref} km/h`}
          traces={charts.balance}
          xTitle=""
          yTitle="Share of downforce [%]"
          layout={{ barmode: "group", bargap: 0.35, bargroupgap: 0.08, yaxis: { range: [0, 100] } }}
          testId="chart-balance"
        />
        <PlotlyChart title="Lap speed trace" subtitle="Quasi-steady lap simulation on the reference circuit" traces={charts.speed} xTitle="Distance [km]" yTitle="Speed [km/h]" layout={{ hovermode: "x unified" }} testId="chart-speed" />
        <div className="relative">
          <div className="absolute right-16 top-2.5 z-10">
            <AxleToggle value={brakeAxle} onChange={setBrakeAxle} />
          </div>
          <PlotlyChart title={`${brakeAxle === "front" ? "Front" : "Rear"} brake disc temperature`} subtitle="Lumped thermal model over one lap" traces={charts.brakes} xTitle="Distance [km]" yTitle="Disc temperature [°C]" layout={{ hovermode: "x unified" }} testId="chart-brakes" digits={0} />
        </div>
        <PlotlyChart title="Coolant temperature by lap" subtitle="Power derates above the limit" traces={charts.coolant} xTitle="Lap" yTitle="Coolant temperature [°C]" layout={{ ...charts.coolantLayout, hovermode: "x unified" }} testId="chart-coolant" />
        <div className="relative">
          <div className="absolute right-16 top-2.5 z-10">
            <AxleToggle value={tyreAxle} onChange={setTyreAxle} />
          </div>
          <PlotlyChart title={`${tyreAxle === "front" ? "Front" : "Rear"} tyre grip over a stint`} subtitle="Grip factor from wear and temperature window" traces={charts.tyres} xTitle="Lap" yTitle="Grip factor [-]" layout={{ hovermode: "x unified" }} testId="chart-tyres" digits={3} />
        </div>
        <PlotlyChart title="Lap time over a stint" subtitle="Includes tyre degradation" traces={charts.stintLap} xTitle="Lap" yTitle="Lap time [s]" layout={{ hovermode: "x unified" }} testId="chart-stint" digits={3} />
        {charts.impact.length > 0 ? (
          <PlotlyChart
            title="Lap time impact by damage"
            subtitle={`Each damage evaluated alone; combined ${result.curves && "lap_time_impact" in result.curves ? `+${(result.curves as Curves).lap_time_impact.combined_delta_s.toFixed(3)} s` : ""}`}
            traces={charts.impactTrace}
            xTitle="Lap time loss [s]"
            yTitle=""
            layout={{ margin: { l: 170, r: 12, t: 8, b: 40 }, showlegend: false }}
            height={Math.max(160, 60 + charts.impact.length * 34)}
            testId="chart-impact"
            digits={3}
          />
        ) : (
          <EmptyChart title="Lap time impact by damage" text="Apply damage to a component to see its lap time cost." />
        )}
        {charts.sweepLap && charts.sw ? (
          <>
            <PlotlyChart
              title={`Severity sweep: ${charts.nameOf(charts.sw.component_id)}`}
              subtitle={`Lap time loss vs severity (${charts.sw.damage_type.replace(/_/g, " ")})`}
              traces={charts.sweepLap}
              xTitle="Severity [%]"
              yTitle="Lap time loss [s]"
              layout={{ hovermode: "x unified", showlegend: false }}
              testId="chart-sweep"
              digits={3}
            />
            <PlotlyChart
              title="Severity sweep: aero change"
              subtitle="Change vs healthy car at the reference speed"
              traces={charts.sweepAero ?? []}
              xTitle="Severity [%]"
              yTitle="Change [%]"
              layout={{ hovermode: "x unified" }}
              testId="chart-sweep-aero"
            />
          </>
        ) : (
          <EmptyChart title="Severity sweep" text="Select a damaged component to see how its effect scales from 0 to 100% severity." />
        )}
        <PlotlyChart
          title="Component health"
          subtitle="Colour = severity level (see tooltip)"
          traces={charts.healthTrace}
          xTitle="Health [%]"
          yTitle=""
          layout={{ margin: { l: 150, r: 12, t: 8, b: 40 }, showlegend: false, xaxis: { range: [0, 100] }, bargap: 0.3 }}
          height={Math.max(240, 40 + charts.nHealth * 18)}
          testId="chart-health"
          digits={0}
        />
      </div>
    </div>
  );
}

function EmptyChart({ title, text }: { title: string; text: string }) {
  return (
    <div className="flex min-h-[200px] flex-col rounded-lg border border-dashed border-line bg-panel p-3">
      <div className="text-sm font-medium text-ink">{title}</div>
      <div className="grid flex-1 place-items-center px-6 text-center text-xs text-ink-3">{text}</div>
    </div>
  );
}
