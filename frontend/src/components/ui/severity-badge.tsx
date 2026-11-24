import { AlertOctagon, AlertTriangle, CheckCircle2, CircleAlert, Info } from "lucide-react";
import { LEVEL_COLOR, LEVEL_LABEL } from "@/lib/severity";
import type { Level } from "@/lib/types";
import { cn } from "@/lib/utils";

const ICON = { healthy: CheckCircle2, minor: Info, moderate: CircleAlert, severe: AlertTriangle, critical: AlertOctagon } as const;

/** Status always ships with an icon and a text label, never colour alone. */
export function SeverityBadge({ level, className }: { level: Level; className?: string }) {
  const Icon = ICON[level];
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs font-medium text-ink", className)}>
      <Icon className="size-3.5" style={{ color: LEVEL_COLOR[level] }} aria-hidden />
      {LEVEL_LABEL[level]}
    </span>
  );
}
