import { Bot, ChevronDown, ChevronRight, Loader2, Send, ShieldAlert, ShieldCheck, User, Wrench } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import type { AskResponse } from "@/lib/types";
import { assumptionOverrides, damageList, useStore } from "@/store";

interface Msg {
  id: number;
  role: "user" | "assistant" | "error";
  text: string;
  meta?: AskResponse;
}

const SUGGESTIONS = [
  "What is the current state of the car?",
  "Why does front wing damage cause understeer?",
  "How much lap time does the current damage cost?",
  "Compare the current car with the healthy baseline",
  "What happens at 300 km/h with DRS open?",
  "Should the car retire?",
];

/** Minimal, safe markdown: paragraphs, "- " bullets, numbered lists, **bold** and `code`. No HTML injection. */
function Markdown({ text }: { text: string }) {
  const inline = (s: string): ReactNode[] =>
    s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
      part.startsWith("**") && part.endsWith("**") ? (
        <strong key={i} className="font-semibold text-ink">
          {part.slice(2, -2)}
        </strong>
      ) : part.startsWith("`") && part.endsWith("`") ? (
        <code key={i} className="rounded bg-panel px-1 font-mono text-[11px]">
          {part.slice(1, -1)}
        </code>
      ) : (
        part
      ),
    );
  const blocks: ReactNode[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  const flush = () => {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    blocks.push(
      <Tag key={blocks.length} className={list.ordered ? "list-decimal space-y-0.5 pl-5" : "list-disc space-y-0.5 pl-5"}>
        {list.items.map((it, i) => (
          <li key={i}>{inline(it)}</li>
        ))}
      </Tag>,
    );
    list = null;
  };
  for (const raw of text.split("\n")) {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*] (.*)/.exec(line);
    const num = /^\s*\d+\. (.*)/.exec(line);
    if (bullet || num) {
      const ordered = !!num;
      if (list && list.ordered !== ordered) flush();
      list ??= { ordered, items: [] };
      list.items.push((bullet ?? num)![1]);
      continue;
    }
    flush();
    if (!line.trim()) continue;
    const h = /^#{1,4} (.*)/.exec(line);
    blocks.push(
      h ? (
        <p key={blocks.length} className="font-semibold text-ink">
          {inline(h[1])}
        </p>
      ) : (
        <p key={blocks.length}>{inline(line)}</p>
      ),
    );
  }
  flush();
  return <div className="space-y-1.5">{blocks}</div>;
}

function ToolCalls({ meta }: { meta: AskResponse }) {
  const [open, setOpen] = useState(false);
  if (!meta.tool_calls.length) return null;
  return (
    <div className="mt-2">
      <button className="flex items-center gap-1 text-[11px] text-ink-3 hover:text-ink" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        {open ? <ChevronDown className="size-3" /> : <ChevronRight className="size-3" />}
        <Wrench className="size-3" /> {meta.tool_calls.length} tool call{meta.tool_calls.length > 1 ? "s" : ""}: {meta.tool_calls.map((t) => t.tool).join(", ")}
      </button>
      {open && (
        <div className="mt-1 space-y-1">
          {meta.tool_calls.map((t, i) => (
            <details key={i} className="rounded border border-line bg-panel p-2">
              <summary className="cursor-pointer font-mono text-[11px] text-ink">
                {t.tool}({Object.keys(t.args).length ? JSON.stringify(t.args) : ""})
              </summary>
              <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap font-mono text-[10px] text-ink-2">{JSON.stringify(t.result, null, 2)}</pre>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

export function AssistantPanel() {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const selectedId = useStore((s) => s.selectedId);
  const selectedName = useStore((s) => s.components.find((c) => c.id === s.selectedId)?.name);
  const endRef = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }), [msgs, busy]);

  const ask = async (question: string) => {
    const q = question.trim();
    if (q.length < 2 || busy) return;
    const s = useStore.getState();
    setMsgs((m) => [...m, { id: nextId.current++, role: "user", text: q }]);
    setInput("");
    setBusy(true);
    try {
      const r = await api.ask({
        session_id: s.sessionId,
        question: q.slice(0, 600),
        selected_component: s.selectedId,
        damages: damageList(s.damage),
        assumptions: assumptionOverrides(s.car, s.assumptions),
      });
      setMsgs((m) => [...m, { id: nextId.current++, role: "assistant", text: r.answer, meta: r }]);
    } catch (e) {
      const msg = e instanceof ApiError && e.status === 429 ? "Rate limit reached. Please wait a minute before asking again." : (e as Error).message;
      setMsgs((m) => [...m, { id: nextId.current++, role: "error", text: msg }]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex h-full min-h-[420px] flex-col" data-testid="assistant">
      <div className="flex-1 space-y-3 overflow-y-auto p-4">
        {msgs.length === 0 && (
          <div className="space-y-3">
            <div className="flex gap-2 text-xs text-ink-2">
              <Bot className="mt-0.5 size-4 shrink-0 text-accent" aria-hidden />
              <p>
                Ask about the car, a component or the current damage. Answers are built from calls to the simulation tools, and every number in an answer is checked against the tool results. The
                public demo runs without any API key; if the server has an LLM key configured it is used, otherwise a rule-based engine answers.
              </p>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {SUGGESTIONS.map((s) => (
                <Button key={s} size="sm" variant="outline" className="h-auto whitespace-normal py-1.5 text-left text-xs" onClick={() => void ask(s)}>
                  {s}
                </Button>
              ))}
            </div>
          </div>
        )}
        {msgs.map((m) => (
          <div key={m.id} className="flex gap-2">
            {m.role === "user" ? (
              <User className="mt-0.5 size-4 shrink-0 text-ink-3" aria-hidden />
            ) : (
              <Bot className={m.role === "error" ? "mt-0.5 size-4 shrink-0 text-sev-critical" : "mt-0.5 size-4 shrink-0 text-accent"} aria-hidden />
            )}
            <div className={m.role === "user" ? "text-sm text-ink" : "min-w-0 flex-1 rounded-lg border border-line bg-panel2 p-3 text-xs leading-relaxed text-ink-2"}>
              {m.role === "assistant" ? <Markdown text={m.text} /> : m.role === "error" ? <p className="text-sev-critical">{m.text}</p> : m.text}
              {m.meta && (
                <>
                  <div className="mt-2 flex flex-wrap items-center gap-1.5" data-testid="assistant-meta">
                    <Badge>{m.meta.mode === "llm_tool_calling" ? `LLM: ${m.meta.provider}` : "Rule-based engine"}</Badge>
                    {m.meta.numeric_claims_verified ? (
                      <Badge className="border-sev-healthy/40">
                        <ShieldCheck className="size-3 text-sev-healthy" aria-hidden /> All numbers traced to tool results
                      </Badge>
                    ) : (
                      <Badge className="border-sev-severe/50">
                        <ShieldAlert className="size-3 text-sev-severe" aria-hidden /> Unverified: {m.meta.unverified_values.join(", ")}
                      </Badge>
                    )}
                  </div>
                  {m.meta.notice && <p className="mt-1 text-[11px] text-ink-3">{m.meta.notice}</p>}
                  <ToolCalls meta={m.meta} />
                </>
              )}
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2 text-xs text-ink-3">
            <Loader2 className="size-4 animate-spin text-accent" /> Running simulation tools…
          </div>
        )}
        <div ref={endRef} />
      </div>
      <form
        className="flex items-center gap-2 border-t border-line p-3"
        onSubmit={(e) => {
          e.preventDefault();
          void ask(input);
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          maxLength={600}
          placeholder={selectedName ? `Ask about the ${selectedName} or the car…` : "Ask about the car or a component…"}
          className="h-9 flex-1 rounded-md border border-line bg-panel2 px-3 text-sm text-ink placeholder:text-ink-3 focus:outline-none focus:ring-2 focus:ring-accent"
          aria-label="Question for the engineering assistant"
          data-testid="assistant-input"
        />
        {selectedId && <Badge className="hidden sm:inline-flex">Context: {selectedName}</Badge>}
        <Button type="submit" disabled={busy || input.trim().length < 2} aria-label="Send question">
          <Send />
        </Button>
      </form>
    </div>
  );
}
