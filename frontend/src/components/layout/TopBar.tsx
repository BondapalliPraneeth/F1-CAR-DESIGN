import { Download, FileJson, FileText, Loader2, Printer, RotateCcw, Save, Table2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api, downloadBlob } from "@/lib/api";
import { assumptionOverrides, damageList, useStore } from "@/store";

export function TopBar() {
  const car = useStore((s) => s.car);
  const scenarioId = useStore((s) => s.scenarioId);
  const saving = useStore((s) => s.saving);
  const saved = useStore((s) => s.saved);
  const saveError = useStore((s) => s.saveError);
  const hasDamage = useStore((s) => Object.values(s.damage).some((d) => d.severity > 0));
  const { applyScenario, resetDamage, save } = useStore.getState();
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvError, setCsvError] = useState<string | null>(null);

  const exportCsv = async () => {
    const s = useStore.getState();
    setCsvBusy(true);
    setCsvError(null);
    try {
      const blob = await api.exportCsv({ damages: damageList(s.damage), assumptions: assumptionOverrides(s.car, s.assumptions) });
      downloadBlob(blob, "apexvision_performance.csv");
    } catch (e) {
      setCsvError((e as Error).message);
    } finally {
      setCsvBusy(false);
    }
  };

  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-line bg-panel px-4 py-2">
      <div className="flex items-center gap-2">
        <svg viewBox="0 0 32 32" className="size-7" aria-hidden>
          <rect width="32" height="32" rx="7" fill="#0f1520" />
          <path d="M5 21 L14 9 L18 9 L27 21 L22 21 L16 13 L10 21 Z" fill="#16c7bd" />
          <rect x="11" y="22.5" width="10" height="2" rx="1" fill="#e6ebf2" />
        </svg>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-ink">ApexVision 3D</div>
          <div className="text-[11px] text-ink-3">{car ? `${car.name} · engineering & damage simulator` : "Engineering & damage simulator"}</div>
        </div>
      </div>

      <div className="flex flex-1 flex-wrap items-center justify-end gap-2">
        <label className="flex items-center gap-2 text-xs text-ink-2">
          Scenario
          <select
            className="h-8 rounded-md border border-line bg-panel2 px-2 text-xs text-ink focus:outline-none focus:ring-2 focus:ring-accent"
            value={scenarioId ?? ""}
            onChange={(e) => (e.target.value ? applyScenario(e.target.value) : resetDamage())}
            aria-label="Damage scenario"
            data-testid="scenario-select"
          >
            <option value="">{hasDamage && !scenarioId ? "Custom damage" : "Healthy baseline"}</option>
            {car?.scenarios.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <Button size="sm" variant="outline" onClick={resetDamage} disabled={!hasDamage} title="Repair all components">
          <RotateCcw /> Reset
        </Button>
        <Button size="sm" variant="outline" onClick={exportCsv} disabled={csvBusy || !car} title="Download lap trace and degradation data as CSV">
          {csvBusy ? <Loader2 className="animate-spin" /> : <Table2 />} CSV
        </Button>
        <Button size="sm" onClick={() => void save()} disabled={saving || !car} data-testid="save-button">
          {saving ? <Loader2 className="animate-spin" /> : <Save />} Save & report
        </Button>
        {saved?.report_id && (
          <div className="flex items-center gap-1" data-testid="report-links">
            <span className="text-[11px] text-ink-3">Report:</span>
            <Button asChild size="sm" variant="ghost">
              <a href={api.reportUrl(saved.report_id, "md")} download>
                <FileText /> MD
              </a>
            </Button>
            <Button asChild size="sm" variant="ghost">
              <a href={api.reportUrl(saved.report_id, "html")} target="_blank" rel="noreferrer">
                <Printer /> HTML/PDF
              </a>
            </Button>
            <Button asChild size="sm" variant="ghost">
              <a href={api.reportUrl(saved.report_id, "json")} target="_blank" rel="noreferrer">
                <FileJson /> JSON
              </a>
            </Button>
          </div>
        )}
        {saved && !saved.report_id && (
          <span className="flex items-center gap-1 text-[11px] text-ink-2">
            <Download className="size-3.5" /> Saved {saved.simulation_id.slice(0, 8)}
          </span>
        )}
      </div>
      {(saveError || csvError) && (
        <div className="w-full text-right text-[11px] text-sev-critical" role="alert">
          {saveError ?? csvError}
        </div>
      )}
    </header>
  );
}
