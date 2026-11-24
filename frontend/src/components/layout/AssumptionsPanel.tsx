import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useStore } from "@/store";

/** Exposes every model assumption so users can see and change what the numbers rest on. */
export function AssumptionsPanel() {
  const car = useStore((s) => s.car);
  const values = useStore((s) => s.assumptions);
  const { setAssumption, resetAssumptions } = useStore.getState();
  if (!car) return null;
  const changed = car.assumptions.filter((m) => values[m.key] !== m.default).length;

  return (
    <div className="p-4" data-testid="assumptions">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="max-w-3xl text-xs text-ink-2">
          These are the model inputs behind every result. They are <strong className="text-ink">generic assumptions</strong> for an invented car, not specifications of any real vehicle. Changes re-run
          the simulation; invalid values are rejected by the server.
        </p>
        <Button size="sm" variant="outline" onClick={resetAssumptions} disabled={changed === 0}>
          <RotateCcw /> Reset {changed > 0 ? `(${changed})` : ""}
        </Button>
      </div>
      <div className="grid gap-x-6 gap-y-2 md:grid-cols-2 xl:grid-cols-3">
        {car.assumptions.map((m) => {
          const v = values[m.key];
          const isChanged = v !== m.default;
          return (
            <label key={m.key} className="flex items-center justify-between gap-3 border-b border-line/60 py-1.5 text-xs">
              <span className="min-w-0">
                <span className={isChanged ? "text-ink" : "text-ink-2"}>{m.description}</span>
                <span className="block font-mono text-[10px] text-ink-3">
                  {m.key}
                  {isChanged && ` · default ${String(m.default)}`}
                </span>
              </span>
              {typeof m.default === "boolean" ? (
                <input type="checkbox" checked={Boolean(v)} onChange={(e) => setAssumption(m.key, e.target.checked)} className="size-4 accent-[#16c7bd]" />
              ) : (
                <input
                  type="number"
                  step="any"
                  defaultValue={String(v)}
                  key={`${m.key}-${String(v === m.default)}`}
                  onBlur={(e) => {
                    const n = Number(e.target.value);
                    if (e.target.value.trim() !== "" && Number.isFinite(n) && n !== v) setAssumption(m.key, Number.isInteger(m.default) && m.key === "stint_laps" ? Math.round(n) : n);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") (e.target as HTMLInputElement).blur();
                  }}
                  className="h-7 w-24 shrink-0 rounded border border-line bg-panel2 px-2 text-right font-mono text-ink focus:outline-none focus:ring-2 focus:ring-accent"
                  aria-label={m.description}
                />
              )}
            </label>
          );
        })}
      </div>
    </div>
  );
}
