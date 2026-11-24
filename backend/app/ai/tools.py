"""Tools exposed to the AI engineering assistant.

Every number the assistant may quote must come from one of these functions,
which call the simulation engine directly. Outputs are rounded so that the
numeric-claim verifier can trace values quoted in the answer.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.domain.components import COMPONENTS, COMPONENTS_BY_ID
from app.simulation import aerodynamics as aero
from app.simulation.assumptions import VehicleAssumptions
from app.simulation.damage import DamageInput, build_modifiers, classify_severity
from app.simulation.vehicle import SimulationResult, baseline, simulate


@dataclass
class ToolContext:
    assumptions: VehicleAssumptions
    damages: list[DamageInput]
    selected_component: str | None = None
    _current: SimulationResult | None = None

    @property
    def current(self) -> SimulationResult:
        if self._current is None:
            self._current = simulate(self.assumptions, self.damages, curves=True)
        return self._current


def r(x: float, n: int = 2) -> float:
    return round(float(x), n)


def get_component_details(ctx: ToolContext, component_id: str | None = None) -> dict:
    cid = component_id or ctx.selected_component
    c = COMPONENTS_BY_ID.get(cid or "")
    if not c:
        return {"error": f"Unknown component '{cid}'.", "valid_ids": [x.id for x in COMPONENTS]}
    health = next(h for h in ctx.current.component_health if h.component_id == c.id)
    ae = ctx.current.aero
    out = {
        "component_id": c.id, "name": c.name, "category": c.category, "position": c.position,
        "purpose": c.purpose, "primary_function": c.primary_function, "construction": c.construction,
        "performance_contribution": c.performance_contribution, "failure_modes": c.failure_modes,
        "damage_susceptibility": c.damage_susceptibility, "engineering_explanation": c.engineering_explanation,
        "damage_types": [{"id": d.id, "label": d.label, "description": d.description} for d in c.damage_types],
        "current_health_pct": r(health.health_pct, 1), "current_damage_level": health.level,
        "current_damage_type": health.damage_type,
    }
    if c.id in ae.downforce_by_component_n:
        out["current_downforce_n_at_250kmh"] = r(ae.downforce_by_component_n[c.id], 0)
    if c.id in ae.drag_by_component_n:
        out["current_drag_n_at_250kmh"] = r(ae.drag_by_component_n[c.id], 0)
    return out


def _status(res: SimulationResult) -> dict:
    p, ae = res.performance, res.aero
    return {
        "lap_time_s": r(p.lap_time_s, 3), "top_speed_kmh": r(p.top_speed_kmh, 1),
        "downforce_n_at_250kmh": r(ae.downforce_n, 0), "drag_n_at_250kmh": r(ae.drag_n, 0),
        "lift_to_drag": r(ae.lift_to_drag, 3), "front_balance_pct": r(ae.front_balance_pct, 1),
        "effective_ride_height_mm": r(ae.effective_ride_height_mm, 1),
        "tyre_grip_front_mu": r(p.tyre_grip_front, 3), "tyre_grip_rear_mu": r(p.tyre_grip_rear, 3),
        "tyre_temp_front_c": r(p.tyre_temp_front_c, 1), "tyre_temp_rear_c": r(p.tyre_temp_rear_c, 1),
        "brake_temp_front_peak_c": r(p.brake_temp_front_peak_c, 0), "brake_temp_rear_peak_c": r(p.brake_temp_rear_peak_c, 0),
        "coolant_temp_mean_c": r(p.coolant_temp_mean_c, 1), "power_derate_pct": r(p.power_derate_factor * 100, 1),
        "overall_health_pct": r(res.overall_health_pct, 1), "performance_index_pct": r(res.performance_index_pct, 2),
        "retire_recommended": res.retire_recommended,
    }


def get_vehicle_status(ctx: ToolContext) -> dict:
    res = ctx.current
    damaged = [{"component_id": h.component_id, "name": h.name, "severity_pct": r(h.severity_pct, 0), "level": h.level,
                "damage_type": h.damage_type} for h in res.component_health if h.severity_pct > 0]
    return {"label": res.label, "status": _status(res), "damaged_components": damaged, "warnings": res.warnings}


def calculate_aerodynamic_performance(ctx: ToolContext, speed_kmh: float = 250.0, drs_open: bool = False) -> dict:
    a = ctx.assumptions
    speed_kmh = max(30.0, min(float(speed_kmh), 380.0))
    cur = aero.aero_coefficients(a, build_modifiers(ctx.damages), 1.0 if drs_open else 0.0)
    base = aero.aero_coefficients(a, build_modifiers([]), 1.0 if drs_open else 0.0)
    fc, fb = aero.forces_at_speed(a, cur, speed_kmh), aero.forces_at_speed(a, base, speed_kmh)
    q = fc["dynamic_pressure_pa"]
    drag_rank = sorted(((k, v * q) for k, v in cur.cda_by_component.items() if v > 0), key=lambda kv: -kv[1])
    df_rank = sorted(((k, v * q) for k, v in cur.cla_by_component.items()), key=lambda kv: -kv[1])
    keys = ("downforce_n", "drag_n", "front_downforce_n", "rear_downforce_n", "cl", "cd", "lift_to_drag", "front_balance_pct", "drag_power_kw")
    return {
        "speed_kmh": speed_kmh, "drs_open": drs_open,
        "equations": {"drag": "F_drag = 0.5 * rho * v^2 * Cd * A_frontal", "downforce": "F_downforce = 0.5 * rho * v^2 * Cl * A_ref"},
        "air_density": a.air_density, "frontal_area_m2": a.frontal_area_m2, "reference_area_m2": a.reference_area_m2,
        "current": {k: r(fc[k], 3 if k in ("cl", "cd", "lift_to_drag") else 1) for k in keys},
        "baseline": {k: r(fb[k], 3 if k in ("cl", "cd", "lift_to_drag") else 1) for k in keys},
        "drag_by_component_n": [{"component_id": k, "name": COMPONENTS_BY_ID[k].name, "drag_n": r(v, 0),
                                 "share_pct": r(v / fc["drag_n"] * 100, 1)} for k, v in drag_rank],
        "downforce_by_component_n": [{"component_id": k, "name": COMPONENTS_BY_ID[k].name, "downforce_n": r(v, 0),
                                      "share_pct": r(v / fc["downforce_n"] * 100, 1)} for k, v in df_rank],
    }


def _delta(a: dict, b: dict) -> dict:
    out = {}
    for k, v in b.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool) and isinstance(a.get(k), (int, float)):
            out[k] = r(v - a[k], 3)
    return out


def simulate_component_damage(ctx: ToolContext, component_id: str, damage_type: str | None = None, severity: float = 30.0) -> dict:
    c = COMPONENTS_BY_ID.get(component_id)
    if not c:
        return {"error": f"Unknown component '{component_id}'.", "valid_ids": [x.id for x in COMPONENTS]}
    dt = damage_type if damage_type in [d.id for d in c.damage_types] else c.damage_types[0].id
    sev = max(0.0, min(float(severity), 100.0))
    others = [d for d in ctx.damages if not (d.component_id == component_id and d.damage_type == dt)]
    hyp = others + [DamageInput(component_id=component_id, damage_type=dt, severity=sev)]
    res = simulate(ctx.assumptions, hyp, curves=False)
    base_s = _status(baseline_result(ctx.assumptions))
    cur_s, hyp_s = _status(ctx.current), _status(res)
    return {
        "hypothetical_damage": {"component_id": component_id, "name": c.name, "damage_type": dt, "severity_pct": sev,
                                "level": classify_severity(sev)},
        "note": "Hypothetical run: applied on top of the other current damages. Does not change the user's car.",
        "result": hyp_s, "change_vs_current": _delta(cur_s, hyp_s), "change_vs_healthy": _delta(base_s, hyp_s),
        "mechanisms": [m["explanation"] for m in res.mechanisms if m["component_id"] == component_id],
        "warnings": res.warnings,
    }


_baseline_results: dict[str, SimulationResult] = {}


def baseline_result(a: VehicleAssumptions) -> SimulationResult:
    key = a.model_dump_json()
    if key not in _baseline_results:
        _baseline_results[key] = simulate(a, [], curves=False)
    return _baseline_results[key]


def compare_vehicle_conditions(ctx: ToolContext) -> dict:
    b, c = _status(baseline_result(ctx.assumptions)), _status(ctx.current)
    return {"healthy": b, "current": c, "change": _delta(b, c),
            "interpretation_hints": {"front_balance_pct": "negative change = balance moved rearward (understeer); positive = forward (oversteer)"}}


def get_damage_report(ctx: ToolContext) -> dict:
    res = ctx.current
    pb = baseline(ctx.assumptions)[3]
    impacts = res.curves.get("lap_time_impact", {}).get("by_damage", [])
    ranked = sorted(impacts, key=lambda x: -x["delta_lap_s"])
    return {
        "combined_delta_lap_s": r(res.performance.lap_time_s - pb.lap_time_s, 3),
        "inspection_priority": [{"rank": i + 1, "component_id": x["component_id"], "name": COMPONENTS_BY_ID[x["component_id"]].name,
                                 "damage_type": x["damage_type"], "severity_pct": r(x["severity"], 0),
                                 "isolated_delta_lap_s": r(x["delta_lap_s"], 3)} for i, x in enumerate(ranked)],
        "structural_integrity_pct": r(res.structural_integrity_pct, 0),
        "retire_recommended": res.retire_recommended,
        "mechanisms": res.mechanisms, "warnings": res.warnings,
    }


ToolFn = Callable[..., dict]

TOOLS: dict[str, tuple[ToolFn, str, dict]] = {
    "get_component_details": (get_component_details, "Engineering details and current health of one component. Defaults to the selected component.",
                              {"type": "object", "properties": {"component_id": {"type": "string", "enum": [c.id for c in COMPONENTS]}}}),
    "get_vehicle_status": (get_vehicle_status, "Current simulated vehicle status: key metrics, damaged components, warnings.",
                           {"type": "object", "properties": {}}),
    "calculate_aerodynamic_performance": (calculate_aerodynamic_performance,
                                          "Downforce, drag, L/D and balance at a speed for the current car and the healthy baseline, with per-component breakdown.",
                                          {"type": "object", "properties": {"speed_kmh": {"type": "number"}, "drs_open": {"type": "boolean"}}}),
    "simulate_component_damage": (simulate_component_damage, "Run a hypothetical damage simulation (does not modify the user's car).",
                                  {"type": "object", "properties": {
                                      "component_id": {"type": "string", "enum": [c.id for c in COMPONENTS]},
                                      "damage_type": {"type": "string"},
                                      "severity": {"type": "number", "description": "0-100 percent"}},
                                   "required": ["component_id", "severity"]}),
    "compare_vehicle_conditions": (compare_vehicle_conditions, "Compare the healthy baseline with the current damaged car.",
                                   {"type": "object", "properties": {}}),
    "get_damage_report": (get_damage_report, "Damage report: mechanisms, isolated lap-time impact ranking, warnings, inspection priority.",
                          {"type": "object", "properties": {}}),
}


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any] | None) -> dict:
    if name not in TOOLS:
        return {"error": f"Unknown tool '{name}'"}
    fn = TOOLS[name][0]
    try:
        return fn(ctx, **(args or {}))
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}
