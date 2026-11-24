"""Validation of model behaviour: equations, conservation, monotonic trends, physical bounds.
These check internal consistency of the model; they are not validation against a real car."""
import math

import pytest

from app.domain.components import COMPONENTS, DAMAGE_SCENARIOS
from app.simulation import aerodynamics as aero
from app.simulation.assumptions import AERO_DOWNFORCE_SHARE, DRAG_SHARE, VehicleAssumptions
from app.simulation.damage import DamageInput, build_modifiers, classify_severity
from app.simulation.vehicle import simulate


def dmg(c, t, s):
    return DamageInput(component_id=c, damage_type=t, severity=s)


def test_shares_sum_to_one():
    assert math.isclose(sum(s for s, _ in AERO_DOWNFORCE_SHARE.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(DRAG_SHARE.values()), 1.0, abs_tol=1e-9)
    assert set(DRAG_SHARE) == {c.id for c in COMPONENTS}


def test_twenty_components_with_damage_types():
    assert len(COMPONENTS) == 20
    assert len({c.id for c in COMPONENTS}) == 20
    assert all(c.damage_types for c in COMPONENTS)


@pytest.mark.parametrize("sev,level", [(0, "healthy"), (10, "minor"), (20, "minor"), (30, "moderate"),
                                       (60, "severe"), (76, "critical"), (100, "critical")])
def test_severity_levels(sev, level):
    assert classify_severity(sev) == level


def test_drag_and_downforce_equations(a):
    c = aero.aero_coefficients(a, build_modifiers([]), 0.0)
    v = 250 / 3.6
    f = aero.forces_at_speed(a, c, 250)
    assert f["drag_n"] == pytest.approx(0.5 * a.air_density * v**2 * a.cd_baseline * a.frontal_area_m2, rel=1e-6)
    assert f["downforce_n"] == pytest.approx(0.5 * a.air_density * v**2 * a.cl_baseline * a.reference_area_m2, rel=1e-6)
    assert f["front_downforce_n"] + f["rear_downforce_n"] == pytest.approx(f["downforce_n"], rel=1e-9)


def test_forces_scale_with_speed_squared(a):
    c = aero.aero_coefficients(a, build_modifiers([]), 0.0)
    f1, f2 = aero.forces_at_speed(a, c, 100), aero.forces_at_speed(a, c, 200)
    assert f2["downforce_n"] / f1["downforce_n"] == pytest.approx(4.0, rel=1e-9)


def test_baseline_is_in_plausible_ranges(a):
    r = simulate(a, [], curves=False)
    p = r.performance
    assert 60 < p.lap_time_s < 90
    assert 300 < p.top_speed_kmh < 370
    assert 40 < r.aero.front_balance_pct < 52
    assert p.brake_temp_front_peak_c < 1100
    assert p.coolant_temp_mean_c < a.coolant_limit_c
    assert r.overall_health_pct == 100
    assert not r.retire_recommended
    assert r.label.startswith("MODEL-ESTIMATED")


@pytest.mark.parametrize("comp,dtype", [("front_wing", "element_failure"), ("floor", "floor_damage"),
                                        ("diffuser", "diffuser_damage"), ("front_suspension", "suspension_damage"),
                                        ("radiators", "cooling_failure"), ("power_unit", "power_loss")])
def test_more_damage_never_faster(a, comp, dtype):
    times = [simulate(a, [dmg(comp, dtype, s)], curves=False).performance.lap_time_s for s in (0, 25, 50, 75, 100)]
    assert all(t2 >= t1 - 1e-6 for t1, t2 in zip(times, times[1:], strict=False)), times
    assert times[-1] > times[0]


def test_front_wing_damage_shifts_balance_rearward(a):
    base = simulate(a, [], curves=False).aero.front_balance_pct
    cur = simulate(a, [dmg("front_wing", "element_failure", 60)], curves=False).aero.front_balance_pct
    assert cur < base


def test_rear_wing_damage_shifts_balance_forward_and_cuts_drag(a):
    b = simulate(a, [], curves=False)
    c = simulate(a, [dmg("rear_wing", "wing_damage", 60)], curves=False)
    assert c.aero.front_balance_pct > b.aero.front_balance_pct
    assert c.aero.drag_n < b.aero.drag_n
    assert c.performance.top_speed_kmh > b.performance.top_speed_kmh


def test_floor_damage_reduces_downforce(a):
    b = simulate(a, [], curves=False).aero.downforce_n
    c = simulate(a, [dmg("floor", "floor_damage", 50)], curves=False).aero.downforce_n
    assert c < b


def test_drs_stuck_open_lowers_drag_and_downforce(a):
    b = simulate(a, [], curves=False)
    c = simulate(a, [dmg("drs", "stuck_open", 100)], curves=False)
    assert c.aero.drag_n < b.aero.drag_n and c.aero.downforce_n < b.aero.downforce_n


def test_brake_cooling_failure_raises_temperature_bounded(a):
    b = simulate(a, [], curves=False).performance.brake_temp_front_peak_c
    c = simulate(a, [dmg("front_brakes", "brake_overheating", 100)], curves=False).performance.brake_temp_front_peak_c
    assert b < c < 1800  # radiation keeps it bounded


def test_cooling_failure_raises_coolant_temperature(a):
    b = simulate(a, [], curves=False).performance.coolant_temp_mean_c
    c = simulate(a, [dmg("radiators", "cooling_failure", 60)], curves=False).performance.coolant_temp_mean_c
    assert c > b


def test_puncture_recommends_retirement(a):
    r = simulate(a, [dmg("rear_tyres", "puncture", 90)], curves=False)
    assert r.retire_recommended


def test_invalid_damage_type_rejected():
    with pytest.raises(ValueError):
        dmg("floor", "puncture", 50)
    with pytest.raises(ValueError):
        dmg("floor", "floor_damage", 150)


def test_all_scenarios_run(a):
    for sc in DAMAGE_SCENARIOS:
        r = simulate(a, [DamageInput(**d) for d in sc["damages"]], curves=False)
        assert r.performance.lap_time_s > 0


def test_curves_present(a):
    r = simulate(a, [dmg("floor", "floor_damage", 50)], curves=True, sweep_damage=dmg("floor", "floor_damage", 50))
    for k in ("aero_vs_speed", "balance", "lap_trace", "coolant_by_lap", "tyre_degradation", "lap_time_impact", "severity_sweep"):
        assert k in r.curves


def test_assumption_changes_propagate():
    heavy = simulate(VehicleAssumptions(mass_kg=900), [], curves=False).performance.lap_time_s
    light = simulate(VehicleAssumptions(mass_kg=780), [], curves=False).performance.lap_time_s
    assert heavy > light
