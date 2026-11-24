import type { Level } from "./types";

/** Mirrors backend app/simulation/damage.py classify_severity. */
export function classifySeverity(severity: number): Level {
  if (severity <= 0) return "healthy";
  if (severity <= 20) return "minor";
  if (severity <= 45) return "moderate";
  if (severity <= 75) return "severe";
  return "critical";
}

export const LEVEL_COLOR: Record<Level, string> = {
  healthy: "#22c55e",
  minor: "#facc15",
  moderate: "#f59e0b",
  severe: "#f97316",
  critical: "#ef4444",
};

export const LEVEL_LABEL: Record<Level, string> = {
  healthy: "Healthy",
  minor: "Minor",
  moderate: "Moderate",
  severe: "Severe",
  critical: "Critical",
};
