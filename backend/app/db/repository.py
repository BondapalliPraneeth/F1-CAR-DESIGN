"""Persistence helpers. All DB access goes through this module."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as M
from app.domain.components import COMPONENTS, DAMAGE_SCENARIOS
from app.simulation.assumptions import AERO_DOWNFORCE_SHARE, DRAG_SHARE, VehicleAssumptions
from app.simulation.vehicle import MODEL_VERSION, SimulationResult, baseline

CAR_SLUG = "apexvision-av1"


def seed(db: Session) -> None:
    """Idempotent seed of the car model, components, specifications and scenarios."""
    if db.scalar(select(M.CarModel).where(M.CarModel.slug == CAR_SLUG)):
        return
    car = M.CarModel(
        slug=CAR_SLUG,
        name="ApexVision AV-1",
        description="Original, generic ground-effect open-wheel concept car generated procedurally for this project.",
        asset_path="/models/apexvision_av1.glb",
        model_version=MODEL_VERSION,
    )
    db.add(car)
    db.flush()
    for c in COMPONENTS:
        comp = M.CarComponent(car_model_id=car.id, key=c.id, name=c.name, category=c.category, mesh_prefix=c.id)
        for p in component_parameters(c.id):
            comp.specifications.append(M.ComponentSpecification(parameter=p["name"], value=str(p["value"]),
                                                                unit=p["unit"], source=p["source"]))
        db.add(comp)
    for s in DAMAGE_SCENARIOS:
        db.add(M.DamageScenario(key=s["id"], name=s["name"], damages=s["damages"]))
    db.commit()


def component_parameters(component_id: str, a: VehicleAssumptions | None = None) -> list[dict]:
    """Model parameters relevant to a component (all labelled as model assumptions)."""
    a = a or VehicleAssumptions()
    out: list[dict] = []
    if component_id in AERO_DOWNFORCE_SHARE:
        share, x = AERO_DOWNFORCE_SHARE[component_id]
        out.append({"name": "Downforce share (healthy)", "value": round(share * 100, 1), "unit": "%", "source": "model_assumption"})
        out.append({"name": "Centre of pressure behind front axle", "value": x, "unit": "m", "source": "model_assumption"})
    if component_id in DRAG_SHARE and DRAG_SHARE[component_id] > 0:
        out.append({"name": "Drag share (healthy)", "value": round(DRAG_SHARE[component_id] * 100, 1), "unit": "%", "source": "model_assumption"})
    extra = {
        "front_wing": [("Whole-car Cl (healthy)", a.cl_baseline, "-")],
        "floor": [("Optimal ride height", a.optimal_ride_height_mm, "mm"), ("Ride-height sensitivity", a.ride_height_sensitivity, "1/mm^2")],
        "venturi_tunnels": [("Optimal ride height", a.optimal_ride_height_mm, "mm")],
        "diffuser": [("Optimal ride height", a.optimal_ride_height_mm, "mm")],
        "rear_wing": [("DRS Cl reduction", a.drs_rear_wing_cl_reduction * 100, "%"), ("DRS Cd reduction", a.drs_rear_wing_cd_reduction * 100, "%")],
        "drs": [("DRS Cl reduction", a.drs_rear_wing_cl_reduction * 100, "%"), ("DRS Cd reduction", a.drs_rear_wing_cd_reduction * 100, "%")],
        "front_tyres": [("Peak friction coefficient", a.tyre_mu_peak, "-"), ("Optimal temperature", a.tyre_optimal_temp_c, "degC"),
                        ("Window half-width", a.tyre_window_halfwidth_c, "degC"), ("Nominal pressure", a.tyre_pressure_psi, "psi")],
        "rear_tyres": [("Peak friction coefficient", a.tyre_mu_peak, "-"), ("Optimal temperature", a.tyre_optimal_temp_c, "degC"),
                       ("Wear per lap", a.tyre_wear_per_lap * 100, "%"), ("Nominal pressure", a.tyre_pressure_psi, "psi")],
        "front_brakes": [("Brake bias (front)", a.front_brake_bias * 100, "%"), ("Disc mass", a.brake_disc_mass_kg, "kg"),
                         ("Friction window", f"{a.brake_optimal_min_c:.0f}-{a.brake_optimal_max_c:.0f}", "degC")],
        "rear_brakes": [("Brake bias (rear)", round((1 - a.front_brake_bias) * 100, 1), "%"), ("Disc mass", a.brake_disc_mass_kg, "kg"),
                        ("Friction window", f"{a.brake_optimal_min_c:.0f}-{a.brake_optimal_max_c:.0f}", "degC")],
        "radiators": [("Radiator effectiveness", a.radiator_effectiveness, "-"), ("Coolant derate limit", a.coolant_limit_c, "degC")],
        "sidepods": [("Cooling inlet area", a.cooling_inlet_area_m2, "m^2"), ("Duct velocity ratio", a.cooling_duct_velocity_ratio, "-")],
        "power_unit": [("Peak wheel power", a.power_kw, "kW"), ("Heat to coolant", a.heat_to_coolant_fraction * 100, "%"),
                       ("Drivetrain efficiency", a.drivetrain_efficiency * 100, "%")],
        "front_suspension": [("Static ride height", a.ride_height_mm, "mm"), ("Static front weight", a.static_front_weight_fraction * 100, "%")],
        "rear_suspension": [("Static ride height", a.ride_height_mm, "mm"), ("Static rear weight", round((1 - a.static_front_weight_fraction) * 100, 1), "%")],
        "monocoque": [("Vehicle mass", a.mass_kg, "kg"), ("Wheelbase", a.wheelbase_m, "m")],
    }.get(component_id, [])
    out += [{"name": n, "value": v, "unit": u, "source": "model_assumption"} for n, v, u in extra]
    return out


def save_simulation(db: Session, *, session_id: str, result: SimulationResult, a: VehicleAssumptions,
                    report_title: str, report_md: str, scenario_key: str | None = None, action: str = "simulate") -> tuple[str, str]:
    pb = baseline(a)[3]
    scenario_id = None
    if scenario_key:
        sc = db.scalar(select(M.DamageScenario).where(M.DamageScenario.key == scenario_key))
        scenario_id = sc.id if sc else None
    sim = M.DamageSimulation(
        session_id=session_id, scenario_id=scenario_id,
        damages=[d.model_dump() for d in result.damages], assumptions=a.model_dump(), model_version=result.model_version,
    )
    ae, p = result.aero, result.performance
    sim.aero = M.AerodynamicResult(
        reference_speed_kmh=ae.reference_speed_kmh, downforce_n=ae.downforce_n, drag_n=ae.drag_n, cl=ae.cl, cd=ae.cd,
        lift_to_drag=ae.lift_to_drag, front_balance_pct=ae.front_balance_pct, ride_height_mm=ae.effective_ride_height_mm)
    sim.performance = M.VehiclePerformance(
        lap_time_s=p.lap_time_s, delta_lap_s=p.lap_time_s - pb.lap_time_s, top_speed_kmh=p.top_speed_kmh,
        performance_index_pct=result.performance_index_pct, overall_health_pct=result.overall_health_pct,
        brake_temp_front_peak_c=p.brake_temp_front_peak_c, coolant_temp_mean_c=p.coolant_temp_mean_c,
        retire_recommended=result.retire_recommended)
    sim.health = [M.ComponentHealthRecord(component_key=h.component_id, health_pct=h.health_pct, level=h.level,
                                          damage_type=h.damage_type) for h in result.component_health]
    db.add(sim)
    db.flush()
    report = M.EngineeringReport(simulation_id=sim.id, title=report_title, markdown=report_md,
                                 payload=result.model_dump(exclude={"curves"}))
    db.add(report)
    db.add(M.SimulationHistory(session_id=session_id, simulation_id=sim.id, action=action,
                               summary=f"{report_title} | lap {p.lap_time_s - pb.lap_time_s:+.3f} s"))
    db.commit()
    return sim.id, report.id


def latest_simulation(db: Session, session_id: str) -> M.DamageSimulation | None:
    return db.scalar(select(M.DamageSimulation).where(M.DamageSimulation.session_id == session_id)
                     .order_by(M.DamageSimulation.created_at.desc()).limit(1))


def history(db: Session, session_id: str, limit: int = 50) -> list[M.SimulationHistory]:
    return list(db.scalars(select(M.SimulationHistory).where(M.SimulationHistory.session_id == session_id)
                           .order_by(M.SimulationHistory.created_at.desc()).limit(limit)))


def get_report(db: Session, report_id: str) -> M.EngineeringReport | None:
    return db.get(M.EngineeringReport, report_id)


def report_for_simulation(db: Session, simulation_id: str) -> M.EngineeringReport | None:
    return db.scalar(select(M.EngineeringReport).where(M.EngineeringReport.simulation_id == simulation_id))


def save_conversation(db: Session, *, session_id: str, question: str, answer: str, provider: str, tool_calls: list) -> None:
    db.add(M.AIConversation(session_id=session_id, question=question, answer=answer, provider=provider, tool_calls=tool_calls))
    db.commit()
