import { Eye, EyeOff, Focus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { classifySeverity, LEVEL_COLOR, LEVEL_LABEL } from "@/lib/severity";
import { cn } from "@/lib/utils";
import { useStore } from "@/store";
import { componentIcon } from "./componentIcons";

const CATEGORY_ORDER = ["aerodynamic", "structural", "thermal", "powertrain", "mechanical"];

export function ComponentNav() {
  const components = useStore((s) => s.components);
  const damage = useStore((s) => s.damage);
  const selectedId = useStore((s) => s.selectedId);
  const hoveredId = useStore((s) => s.hoveredId);
  const hidden = useStore((s) => s.hidden);
  const isolatedId = useStore((s) => s.isolatedId);
  const { select, hover, toggleHidden, isolate, showAll } = useStore.getState();
  const [q, setQ] = useState("");

  const groups = useMemo(() => {
    const filtered = components.filter((c) => c.name.toLowerCase().includes(q.toLowerCase()));
    const map = new Map<string, typeof components>();
    for (const c of filtered) map.set(c.category, [...(map.get(c.category) ?? []), c]);
    return [...map.entries()].sort((a, b) => {
      const ia = CATEGORY_ORDER.indexOf(a[0]);
      const ib = CATEGORY_ORDER.indexOf(b[0]);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
  }, [components, q]);

  const anyHidden = Object.values(hidden).some(Boolean) || isolatedId !== null;

  return (
    <nav className="flex h-full flex-col" aria-label="Components">
      <div className="border-b border-line p-3">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">
            Car Components <span className="font-normal text-ink-3">({components.length})</span>
          </h2>
          {anyHidden && (
            <button className="text-[11px] text-accent hover:underline" onClick={showAll}>
              Show all
            </button>
          )}
        </div>
        <label className="flex items-center gap-2 rounded-md border border-line bg-panel2 px-2 py-1.5">
          <Search className="size-3.5 text-ink-3" aria-hidden />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Filter components"
            className="w-full bg-transparent text-xs text-ink placeholder:text-ink-3 focus:outline-none"
            aria-label="Filter components"
          />
        </label>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {groups.map(([cat, list]) => (
          <div key={cat} className="mb-2">
            <div className="px-2 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-ink-3">{cat}</div>
            <ul>
              {list.map((c) => {
                const sev = damage[c.id]?.severity ?? 0;
                const level = classifySeverity(sev);
                const isHidden = !!hidden[c.id] || (isolatedId !== null && isolatedId !== c.id);
                const Icon = componentIcon(c.id, c.category);
                const sel = selectedId === c.id;
                return (
                  <li key={c.id} className="mb-0.5">
                    <div
                      className={cn(
                        "group flex items-center gap-2 rounded-lg border px-2 py-1.5 text-xs transition-colors",
                        sel
                          ? "border-accent/60 bg-gradient-to-r from-accent/35 via-accent/10 to-transparent text-ink shadow-[inset_3px_0_0_#ef3b2d]"
                          : hoveredId === c.id
                            ? "border-line bg-panel2 text-ink"
                            : "border-transparent text-ink-2 hover:bg-panel2",
                      )}
                      onMouseEnter={() => hover(c.id)}
                      onMouseLeave={() => hover(null)}
                    >
                      <span className={cn("grid size-7 shrink-0 place-items-center rounded-md border", sel ? "border-accent/50 bg-accent/20 text-white" : "border-line bg-panel2 text-ink-3")} aria-hidden>
                        <Icon className="size-3.5" />
                      </span>
                      <span
                        className="size-2 shrink-0 rounded-full"
                        style={{ background: LEVEL_COLOR[level] }}
                        title={`${LEVEL_LABEL[level]}${sev ? ` (${sev}%)` : ""}`}
                        aria-hidden
                      />
                      <button className={cn("flex-1 truncate text-left", isHidden && "opacity-50")} onClick={() => select(c.id)} data-testid={`nav-${c.id}`}>
                        {c.name}
                        <span className="sr-only">, {LEVEL_LABEL[level]}</span>
                      </button>
                      {sev > 0 && <span className="font-mono text-[10px] text-ink-2">{sev}%</span>}
                      <button
                        className="rounded p-0.5 text-ink-3 opacity-0 hover:text-ink focus:opacity-100 group-hover:opacity-100"
                        onClick={() => (isolatedId === c.id ? showAll() : isolate(c.id))}
                        aria-label={isolatedId === c.id ? `Exit isolate ${c.name}` : `Isolate ${c.name}`}
                        title="Isolate"
                      >
                        <Focus className="size-3.5" />
                      </button>
                      <button
                        className={cn("rounded p-0.5 text-ink-3 hover:text-ink focus:opacity-100", hidden[c.id] ? "opacity-100" : "opacity-0 group-hover:opacity-100")}
                        onClick={() => toggleHidden(c.id)}
                        aria-label={hidden[c.id] ? `Show ${c.name}` : `Hide ${c.name}`}
                        title={hidden[c.id] ? "Show" : "Hide"}
                      >
                        {hidden[c.id] ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}
