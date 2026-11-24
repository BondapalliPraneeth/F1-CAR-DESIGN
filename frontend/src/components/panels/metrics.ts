import type { SimulationResult } from "@/lib/types";

export interface MetricDef {
  label: string;
  unit: string;
  digits: number;
  /** true: higher is better; false: lower is better; null: neutral (balance etc.). */
  better: boolean | null;
  get: (r: SimulationResult) => number | undefined;
}

const m = (label: string, unit: string, digits: number, better: boolean | null, get: MetricDef["get"]): MetricDef => ({ label, unit, digits, better, get });

const aero = {
  downforce: m("Total downforce @ ref speed", "N", 0, true, (r) => r.aero.downforce_n),
  front: m("Front downforce", "N", 0, true, (r) => r.aero.front_downforce_n),
  rear: m("Rear downforce", "N", 0, true, (r) => r.aero.rear_downforce_n),
  drag: m("Drag @ ref speed", "N", 0, false, (r) => r.aero.drag_n),
  ld: m("Lift-to-drag ratio", "", 2, true, (r) => r.aero.lift_to_drag),
  balance: m("Front aero balance", "%", 1, null, (r) => r.aero.front_balance_pct),
  dragPower: m("Drag power @ ref speed", "kW", 0, false, (r) => r.aero.drag_power_kw),
  rideHeight: m("Effective ride height", "mm", 1, null, (r) => r.aero.effective_ride_height_mm),
  rhFactor: m("Floor ride-height factor", "", 3, true, (r) => r.aero.ride_height_factor),
};
const perf = {
  lap: m("Lap time", "s", 3, false, (r) => r.performance.lap_time_s),
  vmax: m("Top speed", "km/h", 1, true, (r) => r.performance.top_speed_kmh),
  vmaxDrs: m("Top speed (DRS)", "km/h", 1, true, (r) => r.performance.top_speed_drs_kmh),
  slow: m("Slow corner (R25)", "km/h", 1, true, (r) => r.performance.corner_speeds_kmh.slow_corner_r25),
  medium: m("Medium corner (R100)", "km/h", 1, true, (r) => r.performance.corner_speeds_kmh.medium_corner_r100),
  fast: m("Fast corner (R250)", "km/h", 1, true, (r) => r.performance.corner_speeds_kmh.fast_corner_r250),
  latG: m("Max lateral g @ 250 km/h", "g", 2, true, (r) => r.performance.max_lateral_g_at_250),
  brakeDist: m("Braking 300→100 km/h", "m", 1, false, (r) => r.performance.braking_distance_300_100_m),
};
const tyre = {
  gripF: m("Front grip factor", "", 3, true, (r) => r.performance.tyre_grip_front),
  gripR: m("Rear grip factor", "", 3, true, (r) => r.performance.tyre_grip_rear),
  tempF: m("Front tyre temp", "°C", 1, null, (r) => r.performance.tyre_temp_front_c),
  tempR: m("Rear tyre temp", "°C", 1, null, (r) => r.performance.tyre_temp_rear_c),
  pF: m("Front pressure (damaged corner)", "psi", 1, null, (r) => r.performance.tyre_pressure_front_psi),
  pR: m("Rear pressure (damaged corner)", "psi", 1, null, (r) => r.performance.tyre_pressure_rear_psi),
  wearF: m("Front wear per lap", "", 4, false, (r) => r.performance.tyre_wear_rate_front),
  wearR: m("Rear wear per lap", "", 4, false, (r) => r.performance.tyre_wear_rate_rear),
};
const brake = {
  peakF: m("Front disc peak temp", "°C", 0, false, (r) => r.performance.brake_temp_front_peak_c),
  peakR: m("Rear disc peak temp", "°C", 0, false, (r) => r.performance.brake_temp_rear_peak_c),
  meanF: m("Front disc mean temp", "°C", 0, null, (r) => r.performance.brake_temp_front_mean_c),
  meanR: m("Rear disc mean temp", "°C", 0, null, (r) => r.performance.brake_temp_rear_mean_c),
  friction: m("Brake friction factor", "", 3, true, (r) => r.performance.brake_friction_factor),
  wearF: m("Front brake wear index", "", 2, false, (r) => r.performance.brake_wear_index_front),
  wearR: m("Rear brake wear index", "", 2, false, (r) => r.performance.brake_wear_index_rear),
};
const cool = {
  peak: m("Coolant peak temp", "°C", 1, false, (r) => r.performance.coolant_temp_peak_c),
  mean: m("Coolant mean temp", "°C", 1, false, (r) => r.performance.coolant_temp_mean_c),
  derate: m("Thermal power derate factor", "", 3, true, (r) => r.performance.power_derate_factor),
  delivered: m("Delivered power factor", "", 3, true, (r) => r.performance.delivered_power_factor),
};
const health = {
  overall: m("Overall health", "%", 1, true, (r) => r.overall_health_pct),
  perf: m("Performance index", "%", 1, true, (r) => r.performance_index_pct),
  structural: m("Structural integrity", "%", 1, true, (r) => r.structural_integrity_pct),
};

export const PANEL_METRICS: Record<string, { title: string; metrics: MetricDef[] }> = {
  front_wing: { title: "Front wing aerodynamics", metrics: [aero.front, aero.downforce, aero.drag, aero.ld, aero.balance, perf.fast, perf.medium, perf.lap] },
  rear_wing: { title: "Rear wing & DRS", metrics: [aero.rear, aero.downforce, aero.drag, aero.balance, perf.vmax, perf.vmaxDrs, aero.dragPower, perf.lap] },
  floor: { title: "Underfloor & ground effect", metrics: [aero.downforce, aero.rhFactor, aero.rideHeight, aero.drag, aero.balance, perf.fast, perf.latG, perf.lap] },
  cooling: { title: "Cooling system", metrics: [cool.peak, cool.mean, cool.derate, cool.delivered, aero.drag, perf.vmax, perf.lap] },
  tyres: { title: "Tyre performance", metrics: [tyre.gripF, tyre.gripR, tyre.tempF, tyre.tempR, tyre.pF, tyre.pR, tyre.wearF, tyre.wearR, perf.slow, perf.lap] },
  brakes: { title: "Brake thermal model", metrics: [brake.peakF, brake.peakR, brake.meanF, brake.meanR, brake.friction, brake.wearF, brake.wearR, perf.brakeDist, perf.lap] },
  suspension: { title: "Suspension & mechanical grip", metrics: [aero.rideHeight, aero.rhFactor, aero.balance, tyre.gripF, tyre.gripR, perf.slow, perf.latG, perf.lap] },
  power_unit: { title: "Power unit", metrics: [cool.delivered, cool.derate, cool.peak, perf.vmax, perf.vmaxDrs, perf.lap] },
  structural: { title: "Structural status", metrics: [health.structural, health.overall, health.perf, perf.lap] },
};

export type Verdict = "better" | "worse" | "same" | "neutral";

export function verdict(def: MetricDef, base: number | undefined, cur: number | undefined): Verdict {
  if (base === undefined || cur === undefined) return "same";
  const tol = 0.5 * 10 ** -def.digits;
  if (Math.abs(cur - base) < tol) return "same";
  if (def.better === null) return "neutral";
  return (cur > base) === def.better ? "better" : "worse";
}
