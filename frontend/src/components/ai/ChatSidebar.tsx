import { Bot, MessageSquare, X } from "lucide-react";
import { useEffect } from "react";
import { AssistantPanel } from "@/components/ai/AssistantPanel";
import { cn } from "@/lib/utils";
import { useStore } from "@/store";

/**
 * AI Assistant as a right-hand sidebar, so people can chat while looking at the car.
 * It stays mounted when closed, so the conversation is kept until the page is reloaded.
 */
export function ChatSidebar() {
  const open = useStore((s) => s.chatOpen);
  const setOpen = useStore((s) => s.setChatOpen);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  return (
    <>
      <aside
        role="dialog"
        aria-label="AI Assistant"
        aria-hidden={!open}
        data-testid="chat-sidebar"
        className={cn(
          "fixed inset-y-0 right-0 z-40 flex w-full flex-col border-l border-line bg-bg shadow-[-12px_0_40px_rgba(0,0,0,0.5)] transition-[transform,visibility] duration-200 sm:w-[440px]",
          open ? "visible translate-x-0" : "invisible translate-x-full",
        )}
      >
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <Bot className="size-5 text-accent" aria-hidden />
          <div className="min-w-0 flex-1 leading-tight">
            <div className="text-sm font-semibold text-ink">AI Assistant</div>
            <div className="text-[11px] text-ink-3">Answers use the live simulation of your current car</div>
          </div>
          <button onClick={() => setOpen(false)} className="rounded-md p-1.5 text-ink-2 hover:bg-panel2 hover:text-ink" aria-label="Close AI Assistant" title="Close (Esc)">
            <X className="size-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1">
          <AssistantPanel />
        </div>
      </aside>

      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-gradient-to-r from-accent to-accent-strong px-4 py-2.5 text-sm font-medium text-white shadow-[0_0_24px_rgba(239,59,45,0.45)] hover:brightness-110"
          aria-label="Open AI Assistant"
          data-testid="chat-launcher"
        >
          <MessageSquare className="size-4" aria-hidden /> Ask AI
        </button>
      )}
    </>
  );
}
