"""Vehicle-level simulation orchestrator.

Couples: damage modifiers -> aero coefficients -> tyre grip -> lap simulation
-> brake / coolant thermal models -> (fade, power derate) -> lap simulation ...
The thermal coupling is resolved by fixed-point iteration (3 passes).
"""

from __future__ import annotations

import json
from functools import lru_cache

import numpy as np
from pydantic import BaseModel

from app.domain.components import COMPONENTS
from app.simulation import aerodynamics as aero
from app.simulation import thermal
from app.simulation.assumptions import VehicleAssumptions
from app.simulation.damage import DamageInput, VehicleModifiers, build_modifiers, classify_severity
from app.simulation.lapsim import (
    LapInputs,
    braking_distance_m,
    corner_speed_kmh,
    max_lateral_g,
    simulate_lap,
    top_speed_kmh,
)
from app.simulation.track import build_track
from app.simulation.tyres import axle_state

MODEL_VERSION = "apexvision-sim-1.0.0"
SPEED_GRID = np.arange(50, 351, 25, dtype=float)
REFERENCE_SPEED_KMH = 250.0
CORNER_RADII = {"slow_corner_r25": 25.0, "medium_corner_r100": 100.0, "fast_corner_r250": 250.0}


class AeroSummary(BaseModel):
    reference_speed_kmh: float
    downforce_n: float
    drag_n: float
    front_downforce_n: float
    rear_downforce_n: float
    cl: float
    cd: float
    cla_m2: float
    cda_m2: float
    lift_to_drag: float
    front_balance_pct: float
    drag_power_kw: float
    effective_ride_height_mm: float
    ride_height_factor: float
    downforce_by_component_n: dict[str, float]
    drag_by_component_n: dict[str, float]


class PerformanceSummary(BaseModel):
    lap_time_s: float
    top_speed_kmh: float
    top_speed_drs_kmh: float
    corner_speeds_kmh: dict[str, float]
    max_lateral_g_at_250: float
    braking_distance_300_100_m: float
    tyre_grip_front: float
    tyre_grip_rear: float
    tyre_temp_front_c: float
    tyre_temp_rear_c: float
    tyre_pressure_front_psi: float
    tyre_pressure_rear_psi: float
    tyre_wear_rate_front: float
    tyre_wear_rate_rear: float
    brake_temp_front_peak_c: float
    brake_temp_rear_peak_c: float
    brake_temp_front_mean_c: float
    brake_temp_rear_mean_c: float
    brake_friction_factor: float
    brake_wear_index_front: float
    brake_wear_index_rear: float
    coolant_temp_peak_c: float
    coolant_temp_mean_c: float
    power_derate_factor: float
    delivered_power_factor: float


class ComponentHealth(BaseModel):
    component_id: str
    name: str
    health_pct: float
    severity_pct: float
    level: str
    damage_type: str | None


class SimulationResult(BaseModel):
    model_version: str
    label: str = "MODEL-ESTIMATED: simplified engineering model, not CFD and not validated against a real car"
    damages: list[DamageInput]
    aero: AeroSummary
    performance: PerformanceSummary
    component_health: list[ComponentHealth]
    overall_health_pct: float
    performance_index_pct: float
    structural_integrity_pct: float
    retire_recommended: bool
    warnings: list[str]
    mechanisms: list[dict]
    curves: dict


def _assumption_key(a: VehicleAssumptions) -> str:
    return json.dumps(a.model_dump(), sort_keys=True)


def _component_health(damages: list[DamageInput]) -> list[ComponentHealth]:
    worst: dict[str, DamageInput] = {}
    for d in damages:
        if d.component_id not in worst or d.severity > worst[d.component_id].severity:
            worst[d.component_id] = d
    out = []
    for c in COMPONENTS:
        d = worst.get(c.id)
        sev = d.severity if d else 0.0
        out.append(ComponentHealth(
            component_id=c.id, name=c.name, health_pct=100 - sev, severity_pct=sev,
            level=classify_severity(sev), damage_type=d.damage_type if d and sev > 0 else None,
        ))
    return out


def _core(a: VehicleAssumptions, damages: list[DamageInput], baseline_balance: float | None):
    """Run the coupled model. Returns (modifiers, coeffs, lap, perf-dict, traces)."""
    track = build_track()
    m = build_modifiers(damages)
    c_corner = aero.aero_coefficients(a, m, 0.0)
    c_drs = aero.aero_coefficients(a, m, 1.0)
    c_point = aero.aero_coefficients(a, m, 1.0 if a.drs_open else 0.0)
    base_bal = baseline_balance if baseline_balance is not None else c_corner.front_balance
    shift_pct = (c_corner.front_balance - base_bal) * 100

    tf = axle_state(a, temp_delta_c=m.tyre_temp_delta_front_c, puncture=m.puncture_front,
                    geometry_factor=m.grip_factor_front, balance_shift_pct=shift_pct, is_front=True)
    tr = axle_state(a, temp_delta_c=m.tyre_temp_delta_rear_c, puncture=m.puncture_rear,
                    geometry_factor=m.grip_factor_rear, balance_shift_pct=shift_pct, is_front=False)

    def run(derate: float, brake_factor: float):
        inp = LapInputs(c_corner, c_drs, tf.mu, tr.mu, m.power_factor * derate, brake_factor)
        lap = simulate_lap(a, track, inp)
        bf_trace, _ = thermal.integrate_brakes(a, lap.dt, lap.v, lap.p_brake, a.front_brake_bias, m.brake_cooling_factor_front, 300.0)
        br_trace, _ = thermal.integrate_brakes(a, lap.dt, lap.v, lap.p_brake, 1 - a.front_brake_bias, m.brake_cooling_factor_rear, 300.0)
        # coolant: march 6 laps from 90 degC; the last lap defines the operating state
        tc, cool_laps = 90.0, []
        for _ in range(6):
            trace = thermal.coolant_step_trace(a, lap.dt, lap.v, lap.p_drive, m.radiator_effectiveness_factor,
                                               m.inlet_area_factor, m.heat_to_coolant_factor, tc)
            tc = float(trace[-1])
            cool_laps.append((float(trace.mean()), float(trace.max())))
        tbf = thermal.braking_weighted_temp(bf_trace, lap.p_brake, lap.dt)
        tbr = thermal.braking_weighted_temp(br_trace, lap.p_brake, lap.dt)
        bfac = (a.front_brake_bias * thermal.brake_friction_factor(a, tbf)
                + (1 - a.front_brake_bias) * thermal.brake_friction_factor(a, tbr))
        return inp, lap, bf_trace, br_trace, trace, cool_laps, bfac, thermal.power_derate(a, cool_laps[-1][0])

    # 1) brake fade fixed point (two passes is sufficient: weak coupling)
    out = run(1.0, 1.0)
    brake_factor = out[6]
    out = run(1.0, brake_factor)
    # 2) power derate equilibrium: derate_new(x) is decreasing in x, so solve x = derate_new(x) by bisection
    derate = 1.0
    if out[7] < 1.0:
        lo, hi = 0.5, 1.0
        for _ in range(7):
            mid = 0.5 * (lo + hi)
            if run(mid, brake_factor)[7] < mid:
                hi = mid
            else:
                lo = mid
        derate = lo
        out = run(derate, brake_factor)
    inp, lap, bf_trace, br_trace, cool_trace, cool_laps, _, _ = out
    pf = m.power_factor * derate
    perf = PerformanceSummary(
        lap_time_s=lap.lap_time_s,
        top_speed_kmh=top_speed_kmh(a, c_corner, pf),
        top_speed_drs_kmh=top_speed_kmh(a, c_drs, pf),
        corner_speeds_kmh={k: min(corner_speed_kmh(a, c_corner, tf.mu, tr.mu, r), top_speed_kmh(a, c_corner, pf))
                           for k, r in CORNER_RADII.items()},
        max_lateral_g_at_250=max_lateral_g(a, c_corner, tf.mu, tr.mu, 250),
        braking_distance_300_100_m=braking_distance_m(a, inp),
        tyre_grip_front=tf.mu, tyre_grip_rear=tr.mu,
        tyre_temp_front_c=tf.temp_c, tyre_temp_rear_c=tr.temp_c,
        tyre_pressure_front_psi=tf.pressure_psi, tyre_pressure_rear_psi=tr.pressure_psi,
        tyre_wear_rate_front=tf.wear_rate_per_lap, tyre_wear_rate_rear=tr.wear_rate_per_lap,
        brake_temp_front_peak_c=float(bf_trace.max()), brake_temp_rear_peak_c=float(br_trace.max()),
        brake_temp_front_mean_c=float(bf_trace.mean()), brake_temp_rear_mean_c=float(br_trace.mean()),
        brake_friction_factor=brake_factor,
        brake_wear_index_front=thermal.brake_wear_index(a, float(bf_trace.mean())),
        brake_wear_index_rear=thermal.brake_wear_index(a, float(br_trace.mean())),
        coolant_temp_peak_c=cool_laps[-1][1], coolant_temp_mean_c=cool_laps[-1][0],
        power_derate_factor=derate, delivered_power_factor=pf,
    )
    traces = {"lap": lap, "brake_front": bf_trace, "brake_rear": br_trace, "coolant": cool_trace,
              "coolant_laps": cool_laps, "tyre_front": tf, "tyre_rear": tr, "inputs": inp}
    return m, c_point, c_corner, perf, traces


@lru_cache(maxsize=32)
def _baseline_cached(key: str):
    a = VehicleAssumptions(**json.loads(key))
    return _core(a, [], None)


def baseline(a: VehicleAssumptions):
    return _baseline_cached(_assumption_key(a))


def lap_time_only(a: VehicleAssumptions, damages: list[DamageInput]) -> float:
    base_bal = baseline(a)[2].front_balance
    return _core(a, damages, base_bal)[3].lap_time_s


def _aero_summary(a: VehicleAssumptions, c: aero.AeroCoefficients) -> AeroSummary:
    f = aero.forces_at_speed(a, c, REFERENCE_SPEED_KMH)
    q = f["dynamic_pressure_pa"]
    return AeroSummary(
        reference_speed_kmh=REFERENCE_SPEED_KMH,
        downforce_n=f["downforce_n"], drag_n=f["drag_n"],
        front_downforce_n=f["front_downforce_n"], rear_downforce_n=f["rear_downforce_n"],
        cl=f["cl"], cd=f["cd"], cla_m2=c.cla_total, cda_m2=c.cda_total,
        lift_to_drag=f["lift_to_drag"], front_balance_pct=f["front_balance_pct"],
        drag_power_kw=f["drag_power_kw"],
        effective_ride_height_mm=c.effective_ride_height_mm, ride_height_factor=c.ride_height_factor,
        downforce_by_component_n={k: v * q for k, v in c.cla_by_component.items()},
        drag_by_component_n={k: v * q for k, v in c.cda_by_component.items() if v > 0},
    )


def _warnings(a: VehicleAssumptions, p: PerformanceSummary, base: PerformanceSummary, c, cb, m: VehicleModifiers) -> list[str]:
    w = []
    shift = (c.front_balance - cb.front_balance) * 100
    if abs(shift) >= 2.0:
        w.append(f"Aero balance moved {shift:+.1f} pts ({'rearward: understeer' if shift < 0 else 'forward: oversteer'} tendency).")
    for axle, t, mu in (("Front", p.tyre_temp_front_c, p.tyre_grip_front), ("Rear", p.tyre_temp_rear_c, p.tyre_grip_rear)):
        if abs(t - a.tyre_optimal_temp_c) > a.tyre_window_halfwidth_c:
            w.append(f"{axle} tyres outside operating window ({t:.0f} degC).")
        if mu < 0.75 * a.tyre_mu_peak:
            w.append(f"{axle} tyre grip severely reduced (mu {mu:.2f}).")
    for axle, t in (("Front", p.brake_temp_front_peak_c), ("Rear", p.brake_temp_rear_peak_c)):
        if t > a.brake_optimal_max_c:
            w.append(f"{axle} brakes exceed the friction window (peak {t:.0f} degC): fade and oxidation risk.")
    if p.coolant_temp_mean_c > a.coolant_limit_c:
        w.append(f"Coolant above limit ({p.coolant_temp_mean_c:.0f} degC): power derated to {p.power_derate_factor * 100:.0f}%.")
    if c.effective_ride_height_mm < a.optimal_ride_height_mm - 8:
        w.append(f"Ride height {c.effective_ride_height_mm:.1f} mm is well below optimum: floor stall / bottoming risk.")
    if p.lap_time_s - base.lap_time_s > 0.5:
        w.append(f"Lap time loss {p.lap_time_s - base.lap_time_s:+.2f} s versus healthy car.")
    return w


def simulate(a: VehicleAssumptions, damages: list[DamageInput], *, curves: bool = True,
             sweep_damage: DamageInput | None = None) -> SimulationResult:
    mb, cb_point, cb_corner, pb, tb = baseline(a)
    m, c_point, c_corner, p, tr = _core(a, damages, cb_corner.front_balance)

    health = _component_health(damages)
    structural = [v for v in m.structural_integrity.values()]
    struct_pct = min(structural) * 100 if structural else 100.0
    retire = struct_pct < 25 or max(m.puncture_front, m.puncture_rear) >= 0.75 or p.power_derate_factor <= 0.5

    result = SimulationResult(
        model_version=MODEL_VERSION,
        damages=damages,
        aero=_aero_summary(a, c_point),
        performance=p,
        component_health=health,
        overall_health_pct=float(np.mean([h.health_pct for h in health])),
        performance_index_pct=pb.lap_time_s / p.lap_time_s * 100,
        structural_integrity_pct=struct_pct,
        retire_recommended=retire,
        warnings=_warnings(a, p, pb, c_corner, cb_corner, m),
        mechanisms=m.mechanisms,
        curves={},
    )
    if curves:
        result.curves = build_curves(a, damages, (mb, cb_point, cb_corner, pb, tb), (m, c_point, c_corner, p, tr), sweep_damage)
    return result


def build_curves(a, damages, base, cur, sweep_damage: DamageInput | None) -> dict:
    _, cbp, _, pb, tb = base
    _, cp, _, p, tr = cur
    track = build_track()
    out: dict = {}

    # Downforce / drag vs speed
    out["aero_vs_speed"] = {"baseline": aero.speed_sweep(a, cbp, SPEED_GRID), "current": aero.speed_sweep(a, cp, SPEED_GRID)}

    # Balance
    out["balance"] = {
        "baseline": {"front_pct": cbp.front_balance * 100, "rear_pct": 100 - cbp.front_balance * 100},
        "current": {"front_pct": cp.front_balance * 100, "rear_pct": 100 - cp.front_balance * 100},
    }

    # Lap traces (decimated for transport)
    step = 4
    dist = track.s[::step].tolist()
    out["lap_trace"] = {
        "distance_m": dist,
        "speed_baseline_kmh": tb["lap"].v_kmh[::step].round(1).tolist(),
        "speed_current_kmh": tr["lap"].v_kmh[::step].round(1).tolist(),
        "brake_front_baseline_c": tb["brake_front"][::step].round(1).tolist(),
        "brake_front_current_c": tr["brake_front"][::step].round(1).tolist(),
        "brake_rear_baseline_c": tb["brake_rear"][::step].round(1).tolist(),
        "brake_rear_current_c": tr["brake_rear"][::step].round(1).tolist(),
        "coolant_baseline_c": tb["coolant"][::step].round(1).tolist(),
        "coolant_current_c": tr["coolant"][::step].round(1).tolist(),
    }

    # Engine temperature warm-up over laps
    out["coolant_by_lap"] = {
        "lap": list(range(1, len(tr["coolant_laps"]) + 1)),
        "baseline_mean_c": [x[0] for x in tb["coolant_laps"]],
        "current_mean_c": [x[0] for x in tr["coolant_laps"]],
        "current_peak_c": [x[1] for x in tr["coolant_laps"]],
        "limit_c": a.coolant_limit_c,
    }

    # Tyre degradation over a stint (lap sim per sample point)
    out["tyre_degradation"] = {"baseline": _baseline_degradation(_assumption_key(a)), "current": _degradation(a, tr)}

    # Lap-time impact of each damaged component in isolation
    impacts = []
    for d in damages:
        if d.severity <= 0:
            continue
        lt = lap_time_only(a, [d])
        impacts.append({"component_id": d.component_id, "damage_type": d.damage_type, "severity": d.severity,
                        "delta_lap_s": lt - pb.lap_time_s})
    out["lap_time_impact"] = {"baseline_lap_s": pb.lap_time_s, "combined_delta_s": p.lap_time_s - pb.lap_time_s,
                              "by_damage": impacts}

    # Severity sweep for the focus damage
    focus = sweep_damage or next((d for d in damages if d.severity > 0), None)
    if focus is not None:
        out["severity_sweep"] = _sweep_cached(_assumption_key(a), focus.component_id, focus.damage_type)
    return out


def _degradation(a: VehicleAssumptions, traces: dict) -> dict:
    from app.simulation.lapsim import simulate_lap as _sim  # local alias for clarity
    from app.simulation.tyres import f_wear

    tf, tr_, inp = traces["tyre_front"], traces["tyre_rear"], traces["inputs"]
    laps = np.unique(np.linspace(0, a.stint_laps, 7).round().astype(int)).tolist()
    track = build_track()
    res = {"lap": laps, "wear_front": [], "wear_rear": [], "grip_front": [], "grip_rear": [], "lap_time_s": []}
    for lap in laps:
        wf, wr = min(tf.wear_rate_per_lap * lap, 1.2), min(tr_.wear_rate_per_lap * lap, 1.2)
        muf = tf.mu / tf.wear_factor * f_wear(wf)
        mur = tr_.mu / tr_.wear_factor * f_wear(wr)
        li = LapInputs(inp.coeff_corner, inp.coeff_drs, muf, mur, inp.power_factor, inp.brake_factor)
        res["wear_front"].append(wf * 100)
        res["wear_rear"].append(wr * 100)
        res["grip_front"].append(muf)
        res["grip_rear"].append(mur)
        res["lap_time_s"].append(_sim(a, track, li).lap_time_s)
    return res


@lru_cache(maxsize=8)
def _baseline_degradation(key: str) -> dict:
    a = VehicleAssumptions(**json.loads(key))
    return _degradation(a, baseline(a)[4])


@lru_cache(maxsize=128)
def _sweep_cached(key: str, component_id: str, damage_type: str) -> dict:
    return severity_sweep(VehicleAssumptions(**json.loads(key)), component_id, damage_type)


def severity_sweep(a: VehicleAssumptions, component_id: str, damage_type: str,
                   severities: tuple[float, ...] = (0, 15, 30, 45, 60, 75, 90, 100)) -> dict:
    _, cbp, _, pb, _ = baseline(a)
    base_df = cbp.cla_total
    base_dr = cbp.cda_total
    out = {"component_id": component_id, "damage_type": damage_type, "severity": list(severities),
           "delta_lap_s": [], "downforce_change_pct": [], "drag_change_pct": [], "performance_loss_pct": []}
    for s in severities:
        d = DamageInput(component_id=component_id, damage_type=damage_type, severity=s)
        _, c_point, _, p, _ = _core(a, [d], baseline(a)[2].front_balance)
        out["delta_lap_s"].append(p.lap_time_s - pb.lap_time_s)
        out["downforce_change_pct"].append((c_point.cla_total / base_df - 1) * 100)
        out["drag_change_pct"].append((c_point.cda_total / base_dr - 1) * 100)
        out["performance_loss_pct"].append((1 - pb.lap_time_s / p.lap_time_s) * 100)
    return out


def classify(severity: float) -> str:
    return classify_severity(severity)
