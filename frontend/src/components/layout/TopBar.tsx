import { Bot, Box, Download, Expand, FileJson, FileText, Gauge, Loader2, Printer, RotateCcw, Save, Table2, Wrench } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api, downloadBlob } from "@/lib/api";
import { cn } from "@/lib/utils";
import { assumptionOverrides, damageList, useStore } from "@/store";

function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** Original ApexVision mark: a stylised apex chevron. Not derived from any real brand. */
function Logo() {
  return (
    <svg viewBox="0 0 40 40" className="size-9" aria-hidden>
      <defs>
        <linearGradient id="av-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff5a4a" />
          <stop offset="1" stopColor="#b51d14" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="10" fill="#14161c" stroke="#2a2e39" />
      <path d="M7 27 L18 11 L23 11 L33 27 L27 27 L20.5 17 L13 27 Z" fill="url(#av-g)" />
      <path d="M13 30 H27" stroke="#eceef2" strokeWidth="2.2" strokeLinecap="round" />
    </svg>
  );
}

type NavId = "viewer" | "performance" | "damage" | "explode" | "ai";

export function TopBar() {
  const car = useStore((s) => s.car);
  const scenarioId = useStore((s) => s.scenarioId);
  const saving = useStore((s) => s.saving);
  const saved = useStore((s) => s.saved);
  const saveError = useStore((s) => s.saveError);
  const simError = useStore((s) => s.simError);
  const simulating = useStore((s) => s.simulating);
  const explode = useStore((s) => s.explode);
  const bottomTab = useStore((s) => s.bottomTab);
  const hasDamage = useStore((s) => Object.values(s.damage).some((d) => d.severity > 0));
  const { applyScenario, resetDamage, save, setExplode, setBottomTab } = useStore.getState();
  const [csvBusy, setCsvBusy] = useState(false);
  const [csvError, setCsvError] = useState<string | null>(null);
  const [nav, setNav] = useState<NavId>("viewer");

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

  const items: { id: NavId; label: string; icon: JSX.Element; run: () => void; active: boolean }[] = [
    { id: "viewer", label: "3D Viewer", icon: <Box />, run: () => scrollToId("viewer"), active: nav === "viewer" },
    {
      id: "performance",
      label: "Performance",
      icon: <Gauge />,
      run: () => {
        setBottomTab("dashboard");
        scrollToId("overview");
      },
      active: nav === "performance",
    },
    { id: "damage", label: "Damage Simulator", icon: <Wrench />, run: () => scrollToId("damage-sim"), active: nav === "damage" },
    {
      id: "explode",
      label: "Exploded View",
      icon: <Expand />,
      run: () => {
        setExplode(explode > 0 ? 0 : 0.7);
        scrollToId("viewer");
      },
      active: explode > 0,
    },
    {
      id: "ai",
      label: "AI Engineer",
      icon: <Bot />,
      run: () => {
        setBottomTab("assistant");
        scrollToId("analysis");
      },
      active: nav === "ai" && bottomTab === "assistant",
    },
  ];

  const online = !simError;

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/95">
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5">
        <div className="flex items-center gap-3">
          <Logo />
          <div className="leading-tight">
            <div className="text-lg font-bold tracking-tight text-ink">
              ApexVision <span className="text-accent">3D</span>
            </div>
            <div className="text-[11px] text-ink-3">F1-style Car Engineering &amp; Damage Simulator</div>
          </div>
        </div>

        <nav className="order-3 flex w-full flex-wrap items-center gap-1 rounded-full border border-line bg-panel p-1 lg:order-2 lg:mx-auto lg:w-auto" aria-label="Sections">
          {items.map((it) => (
            <button
              key={it.id}
              onClick={() => {
                setNav(it.id);
                it.run();
              }}
              aria-pressed={it.active}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3.5 py-1.5 text-xs font-medium transition-colors [&_svg]:size-3.5",
                it.active ? "bg-gradient-to-r from-accent to-accent-strong text-white shadow-[0_0_18px_rgba(239,59,45,0.35)]" : "text-ink-2 hover:bg-panel2 hover:text-ink",
              )}
            >
              {it.icon}
              {it.label}
            </button>
          ))}
        </nav>

        <div className="order-2 ml-auto flex items-center gap-2 lg:order-3 lg:ml-0" role="status" aria-live="polite">
          <span className={cn("relative flex size-2.5")}>
            <span className={cn("relative inline-flex size-2.5 rounded-full", online ? "bg-sev-healthy shadow-[0_0_8px_2px_rgba(34,197,94,0.55)]" : "bg-sev-critical")} />
          </span>
          <span className="text-xs text-ink-2">{online ? (simulating ? "Simulating…" : "System Online") : "Backend error"}</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-line/60 px-4 py-1.5">
        <span className="text-[11px] text-ink-3">{car ? `${car.name}` : ""}</span>
        <div className="flex flex-1 flex-wrap items-center justify-end gap-2">
          <label className="flex items-center gap-2 text-xs text-ink-2">
            Scenario
            <select
              className="h-8 rounded-full border border-line bg-panel2 px-3 text-xs text-ink focus:outline-none focus:ring-2 focus:ring-accent"
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
          <Button size="sm" variant="outline" className="rounded-full" onClick={resetDamage} disabled={!hasDamage} title="Repair all components">
            <RotateCcw /> Reset
          </Button>
          <Button size="sm" variant="outline" className="rounded-full" onClick={exportCsv} disabled={csvBusy || !car} title="Download lap trace and degradation data as CSV">
            {csvBusy ? <Loader2 className="animate-spin" /> : <Table2 />} CSV
          </Button>
          <Button size="sm" className="rounded-full" onClick={() => void save()} disabled={saving || !car} data-testid="save-button">
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
      </div>
    </header>
  );
}
