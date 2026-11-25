import Plotly from "plotly.js-dist-min";
import { Table2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cn, fmt } from "@/lib/utils";

/** Validated chart palette for the dark surface (#0e1016). Text never wears series colours. */
export const SERIES = {
  baseline: "#3987e5",
  current: "#d95926",
  third: "#199e70",
  limit: "#6b7a90",
};

export type Trace = Partial<Plotly.PlotData> & { name?: string; x?: (number | string)[]; y?: (number | string)[] };

const baseLayout = (xTitle: string, yTitle: string): Partial<Plotly.Layout> => ({
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "Inter, system-ui, sans-serif", size: 11, color: "#a3b0c2" },
  margin: { l: 56, r: 12, t: 8, b: 40 },
  xaxis: { title: { text: xTitle, standoff: 6 }, gridcolor: "#1b2433", zerolinecolor: "#232e40", linecolor: "#232e40", tickcolor: "#232e40" },
  yaxis: { title: { text: yTitle, standoff: 6 }, gridcolor: "#1b2433", zerolinecolor: "#2c3a50", linecolor: "#232e40", tickcolor: "#232e40" },
  legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { color: "#e6ebf2", size: 11 }, bgcolor: "rgba(0,0,0,0)" },
  hoverlabel: { bgcolor: "#151d2b", bordercolor: "#232e40", font: { color: "#e6ebf2", family: "Inter, system-ui, sans-serif", size: 11 } },
  showlegend: true,
});

export function PlotlyChart({
  title,
  subtitle,
  traces,
  xTitle,
  yTitle,
  layout,
  height = 240,
  testId,
  digits = 1,
}: {
  title: string;
  subtitle?: string;
  traces: Trace[];
  xTitle: string;
  yTitle: string;
  layout?: Partial<Plotly.Layout>;
  height?: number;
  testId?: string;
  digits?: number;
}) {
  const el = useRef<HTMLDivElement>(null);
  const fig = useRef<HTMLElement>(null);
  const drawn = useRef(false);
  const [showTable, setShowTable] = useState(false);
  // Off-screen charts draw once, then defer redraws until they scroll into view (Plotly layout is expensive).
  const [onScreen, setOnScreen] = useState(true);
  useEffect(() => {
    const f = fig.current;
    if (!f || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([e]) => setOnScreen(e.isIntersecting), { rootMargin: "200px" });
    io.observe(f);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const div = el.current;
    if (!div || showTable) return;
    if (drawn.current && !onScreen && div.childElementCount > 0) return; // redraw later, when visible
    drawn.current = true;
    const base = baseLayout(xTitle, yTitle);
    const merged: Partial<Plotly.Layout> = {
      ...base,
      ...layout,
      xaxis: { ...base.xaxis, ...layout?.xaxis },
      yaxis: { ...base.yaxis, ...layout?.yaxis },
      height,
      autosize: true,
      showlegend: traces.length > 1 && (layout?.showlegend ?? true),
    };
    void Plotly.react(div, traces as Plotly.Data[], merged, { displayModeBar: false, responsive: true });
  }, [traces, xTitle, yTitle, layout, height, showTable, onScreen]);

  useEffect(() => {
    const div = el.current;
    return () => {
      if (div) Plotly.purge(div);
    };
  }, []);

  return (
    <figure ref={fig} className="rounded-lg border border-line bg-panel p-3" data-testid={testId}>
      <figcaption className="mb-1 flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-medium text-ink">{title}</div>
          {subtitle && <div className="text-[11px] text-ink-3">{subtitle}</div>}
        </div>
        <button
          className={cn("flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] text-ink-3 hover:bg-panel2 hover:text-ink", showTable && "text-accent")}
          onClick={() => setShowTable((v) => !v)}
          aria-pressed={showTable}
          title="Toggle data table"
        >
          <Table2 className="size-3.5" /> Data
        </button>
      </figcaption>
      {showTable ? <DataTable traces={traces} xTitle={xTitle} yTitle={yTitle} height={height} digits={digits} /> : <div ref={el} style={{ height }} />}
    </figure>
  );
}

function DataTable({ traces, xTitle, yTitle, height, digits }: { traces: Trace[]; xTitle: string; yTitle: string; height: number; digits: number }) {
  const horizontal = traces[0]?.orientation === "h";
  const keyAxis = (t: Trace) => ((horizontal ? t.y : t.x) ?? []) as (number | string)[];
  const valAxis = (t: Trace) => ((horizontal ? t.x : t.y) ?? []) as (number | string)[];
  const keys = keyAxis(traces[0] ?? {});
  const step = Math.max(1, Math.ceil(keys.length / 60));
  const cell = (v: number | string | undefined) => (typeof v === "number" ? fmt(v, digits) : (v ?? "-"));
  return (
    <div className="overflow-auto" style={{ maxHeight: height }}>
      <table className="w-full text-[11px]">
        <thead className="sticky top-0 bg-panel">
          <tr className="text-left text-ink-3">
            <th className="py-1 pr-2 font-medium">{horizontal ? yTitle : xTitle}</th>
            {traces.map((t, i) => (
              <th key={i} className="py-1 pr-2 text-right font-medium">
                {t.name ?? (horizontal ? xTitle : yTitle)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {keys
            .map((k, i) => [k, i] as const)
            .filter(([, i]) => i % step === 0)
            .map(([k, i]) => (
              <tr key={String(k) + i} className="border-t border-line/60">
                <td className="py-0.5 pr-2 font-mono text-ink-2">{cell(k)}</td>
                {traces.map((t, j) => (
                  <td key={j} className="py-0.5 pr-2 text-right font-mono text-ink">
                    {cell(valAxis(t)[i])}
                  </td>
                ))}
              </tr>
            ))}
        </tbody>
      </table>
      {step > 1 && <p className="mt-1 text-[10px] text-ink-3">Every {step}th sample shown; the CSV export contains all samples.</p>}
    </div>
  );
}
