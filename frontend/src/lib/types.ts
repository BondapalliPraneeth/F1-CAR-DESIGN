export type Level = "healthy" | "minor" | "moderate" | "severe" | "critical";

export interface DamageTypeInfo {
  id: string;
  label: string;
  description: string;
  visual: string;
}

export interface ComponentSummary {
  id: string;
  name: string;
  category: string;
  analysis_panel: string;
  damage_susceptibility: "low" | "medium" | "high";
  damage_types: DamageTypeInfo[];
}

export interface ComponentParameter {
  name: string;
  value: number | string | boolean;
  unit: string;
  source: string;
}

export interface ComponentDetail extends ComponentSummary {
  position: string;
  purpose: string;
  primary_function: string;
  construction: string;
  performance_contribution: string;
  failure_modes: string[];
  susceptibility_note: string;
  engineering_explanation: string;
  related: string[];
  parameters: ComponentParameter[];
}

export interface DamageInput {
  component_id: string;
  damage_type: string;
  severity: number;
}

export interface Scenario {
  id: string;
  name: string;
  damages: DamageInput[];
}

export interface AssumptionMeta {
  key: string;
  default: number | boolean;
  description: string;
}

export interface CarInfo {
  id: string;
  name: string;
  description: string;
  asset_url: string;
  model_version: string;
  component_count: number;
  assumptions: AssumptionMeta[];
  scenarios: Scenario[];
}

export interface AeroSummary {
  reference_speed_kmh: number;
  downforce_n: number;
  drag_n: number;
  front_downforce_n: number;
  rear_downforce_n: number;
  cl: number;
  cd: number;
  cla_m2: number;
  cda_m2: number;
  lift_to_drag: number;
  front_balance_pct: number;
  drag_power_kw: number;
  effective_ride_height_mm: number;
  ride_height_factor: number;
  downforce_by_component_n: Record<string, number>;
  drag_by_component_n: Record<string, number>;
}

export interface PerformanceSummary {
  lap_time_s: number;
  top_speed_kmh: number;
  top_speed_drs_kmh: number;
  corner_speeds_kmh: Record<string, number>;
  max_lateral_g_at_250: number;
  braking_distance_300_100_m: number;
  tyre_grip_front: number;
  tyre_grip_rear: number;
  tyre_temp_front_c: number;
  tyre_temp_rear_c: number;
  tyre_pressure_front_psi: number;
  tyre_pressure_rear_psi: number;
  tyre_wear_rate_front: number;
  tyre_wear_rate_rear: number;
  brake_temp_front_peak_c: number;
  brake_temp_rear_peak_c: number;
  brake_temp_front_mean_c: number;
  brake_temp_rear_mean_c: number;
  brake_friction_factor: number;
  brake_wear_index_front: number;
  brake_wear_index_rear: number;
  coolant_temp_peak_c: number;
  coolant_temp_mean_c: number;
  power_derate_factor: number;
  delivered_power_factor: number;
}

export interface ComponentHealth {
  component_id: string;
  name: string;
  health_pct: number;
  severity_pct: number;
  level: Level;
  damage_type: string | null;
}

export interface Sweep {
  component_id: string;
  damage_type: string;
  severity: number[];
  delta_lap_s: number[];
  downforce_change_pct: number[];
  drag_change_pct: number[];
  performance_loss_pct: number[];
}

export interface Degradation {
  lap: number[];
  wear_front: number[];
  wear_rear: number[];
  grip_front: number[];
  grip_rear: number[];
  lap_time_s: number[];
}

export interface Curves {
  aero_vs_speed: Record<"baseline" | "current", { speed_kmh: number[]; downforce_n: number[]; drag_n: number[] }>;
  balance: Record<"baseline" | "current", { front_pct: number; rear_pct: number }>;
  lap_trace: {
    distance_m: number[];
    speed_baseline_kmh: number[];
    speed_current_kmh: number[];
    brake_front_baseline_c: number[];
    brake_front_current_c: number[];
    brake_rear_baseline_c: number[];
    brake_rear_current_c: number[];
    coolant_baseline_c: number[];
    coolant_current_c: number[];
  };
  coolant_by_lap: { lap: number[]; baseline_mean_c: number[]; current_mean_c: number[]; current_peak_c: number[]; limit_c: number };
  tyre_degradation: { baseline: Degradation; current: Degradation };
  lap_time_impact: {
    baseline_lap_s: number;
    combined_delta_s: number;
    by_damage: (DamageInput & { delta_lap_s: number })[];
  };
  severity_sweep?: Sweep;
}

export interface SimulationResult {
  model_version: string;
  label: string;
  damages: DamageInput[];
  aero: AeroSummary;
  performance: PerformanceSummary;
  component_health: ComponentHealth[];
  overall_health_pct: number;
  performance_index_pct: number;
  structural_integrity_pct: number;
  retire_recommended: boolean;
  warnings: string[];
  mechanisms: { component_id: string; damage_type: string; explanation: string }[];
  curves: Curves | Record<string, never>;
}

export interface SimulateResponse {
  simulation_id: string | null;
  report_id: string | null;
  persisted: boolean;
  result: SimulationResult;
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result: unknown;
}

export interface AskResponse {
  answer: string;
  provider: string;
  mode: string;
  tool_calls: ToolCall[];
  numeric_claims_verified: boolean;
  unverified_values: string[];
  notice: string | null;
  label: string;
}

export interface HistoryItem {
  id: number;
  simulation_id: string;
  report_id: string | null;
  action: string;
  summary: string;
  created_at: string;
}

export type Assumptions = Record<string, number | boolean>;
