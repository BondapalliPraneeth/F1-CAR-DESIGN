import { describe, expect, it } from "vitest";
import { PANEL_METRICS, verdict, type MetricDef } from "./metrics";

const def = (better: boolean | null, digits = 1): MetricDef => ({ label: "x", unit: "", digits, better, get: () => 0 });

describe("verdict", () => {
  it("higher-is-better metrics", () => {
    expect(verdict(def(true), 10, 12)).toBe("better");
    expect(verdict(def(true), 10, 8)).toBe("worse");
  });
  it("lower-is-better metrics", () => {
    expect(verdict(def(false), 74, 75)).toBe("worse");
    expect(verdict(def(false), 74, 73)).toBe("better");
  });
  it("treats sub-resolution changes as unchanged", () => {
    expect(verdict(def(true, 1), 10, 10.04)).toBe("same");
    expect(verdict(def(null), 46.6, 50)).toBe("neutral");
  });
  it("defines every backend analysis panel", () => {
    for (const p of ["front_wing", "rear_wing", "floor", "cooling", "tyres", "brakes", "suspension", "power_unit", "structural"]) {
      expect(PANEL_METRICS[p]?.metrics.length).toBeGreaterThan(3);
    }
  });
});
