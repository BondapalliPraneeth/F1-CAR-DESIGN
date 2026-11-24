import { FileText, RefreshCw } from "lucide-react";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useStore } from "@/store";

export function HistoryPanel() {
  const history = useStore((s) => s.history);
  const loadHistory = useStore((s) => s.loadHistory);
  useEffect(() => {
    void loadHistory();
  }, [loadHistory]);

  return (
    <div className="p-4" data-testid="history">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs text-ink-2">Simulations saved in this browser session. Use “Save & report” to add the current state.</p>
        <Button size="sm" variant="ghost" onClick={() => void loadHistory()}>
          <RefreshCw /> Refresh
        </Button>
      </div>
      {history.length === 0 ? (
        <p className="text-xs text-ink-3">Nothing saved yet.</p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-ink-3">
              <th className="py-1 font-medium">When</th>
              <th className="py-1 font-medium">Summary</th>
              <th className="py-1 text-right font-medium">Report</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id} className="border-t border-line/60">
                <td className="whitespace-nowrap py-1.5 pr-3 font-mono text-ink-2">{new Date(h.created_at).toLocaleString()}</td>
                <td className="py-1.5 pr-3 text-ink">{h.summary}</td>
                <td className="py-1.5 text-right">
                  {h.report_id ? (
                    <span className="inline-flex gap-1">
                      <a className="inline-flex items-center gap-1 text-accent hover:underline" href={api.reportUrl(h.report_id, "md")}>
                        <FileText className="size-3.5" /> MD
                      </a>
                      <a className="text-accent hover:underline" href={api.reportUrl(h.report_id, "html")} target="_blank" rel="noreferrer">
                        HTML
                      </a>
                    </span>
                  ) : (
                    <span className="text-ink-3">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
