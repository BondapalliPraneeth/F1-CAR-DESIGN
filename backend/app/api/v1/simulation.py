from __future__ import annotations

import io
import logging

import pandas as pd
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.schemas import AeroRequest, CompareRequest, DamageSimulateRequest, DamageSimulateResponse, VehicleState
from app.db import repository as repo
from app.db.session import get_db
from app.reports.generator import build_report
from app.simulation import aerodynamics as aero
from app.simulation.damage import build_modifiers
from app.simulation.vehicle import SPEED_GRID, simulate

router = APIRouter(tags=["simulation"])
log = logging.getLogger(__name__)


@router.post("/damage/simulate", response_model=DamageSimulateResponse)
def damage_simulate(req: DamageSimulateRequest, db: Session = Depends(get_db)) -> DamageSimulateResponse:
    result = simulate(req.assumptions, req.damages, curves=req.include_curves, sweep_damage=req.focus)
    sim_id = report_id = None
    if req.persist:
        title, md = build_report(result, req.assumptions)
        try:
            sim_id, report_id = repo.save_simulation(db, session_id=req.session_id, result=result, a=req.assumptions,
                                                     report_title=title, report_md=md, scenario_key=req.scenario_id)
        except SQLAlchemyError as e:  # simulation still returned; persistence failure reported honestly
            db.rollback()
            log.error("Persisting simulation failed: %s", e)
    return DamageSimulateResponse(simulation_id=sim_id, report_id=report_id, persisted=sim_id is not None, result=result)


@router.post("/aerodynamics/calculate")
def aerodynamics_calculate(req: AeroRequest) -> dict:
    m = build_modifiers(req.damages)
    flap = 1.0 if req.drs_open else 0.0
    cur = aero.aero_coefficients(req.assumptions, m, flap)
    base = aero.aero_coefficients(req.assumptions, build_modifiers([]), flap)
    q = float(aero.dynamic_pressure(req.assumptions, req.speed_kmh / 3.6))
    return {
        "label": "MODEL-ESTIMATED: lumped-coefficient aerodynamic model (not CFD)",
        "equations": {"drag": "F_drag = 0.5 * rho * v^2 * Cd * A_frontal", "downforce": "F_downforce = 0.5 * rho * v^2 * Cl * A_ref"},
        "current": aero.forces_at_speed(req.assumptions, cur, req.speed_kmh),
        "baseline": aero.forces_at_speed(req.assumptions, base, req.speed_kmh),
        "downforce_by_component_n": {k: v * q for k, v in cur.cla_by_component.items()},
        "drag_by_component_n": {k: v * q for k, v in cur.cda_by_component.items()},
        "ride_height": {"effective_mm": cur.effective_ride_height_mm, "underfloor_factor": cur.ride_height_factor},
        "sweep": {"current": aero.speed_sweep(req.assumptions, cur, SPEED_GRID),
                  "baseline": aero.speed_sweep(req.assumptions, base, SPEED_GRID)},
    }


@router.post("/performance/analyse")
def performance_analyse(req: VehicleState) -> dict:
    return simulate(req.assumptions, req.damages, curves=True).model_dump()


@router.post("/simulation/compare")
def simulation_compare(req: CompareRequest) -> dict:
    ra = simulate(req.a.assumptions, req.a.damages, curves=False)
    rb = simulate(req.b.assumptions, req.b.damages, curves=False)

    def flat(res) -> dict:
        p, ae = res.performance, res.aero
        return {
            "lap_time_s": p.lap_time_s, "top_speed_kmh": p.top_speed_kmh, "downforce_n": ae.downforce_n, "drag_n": ae.drag_n,
            "lift_to_drag": ae.lift_to_drag, "front_balance_pct": ae.front_balance_pct,
            "tyre_grip_front": p.tyre_grip_front, "tyre_grip_rear": p.tyre_grip_rear,
            "brake_temp_front_peak_c": p.brake_temp_front_peak_c, "coolant_temp_mean_c": p.coolant_temp_mean_c,
            "overall_health_pct": res.overall_health_pct, "performance_index_pct": res.performance_index_pct,
        }

    fa, fb = flat(ra), flat(rb)
    return {"a": fa, "b": fb, "delta": {k: fb[k] - fa[k] for k in fa},
            "warnings_b": rb.warnings, "label": ra.label}


@router.post("/performance/export.csv")
def performance_export_csv(req: VehicleState) -> Response:
    """Lap trace (baseline vs current) and per-lap tyre/coolant data as CSV, built with pandas."""
    res = simulate(req.assumptions, req.damages, curves=True)
    trace = pd.DataFrame(res.curves["lap_trace"])
    deg = res.curves["tyre_degradation"]
    buf = io.StringIO()
    buf.write(f"# {res.label}\n# model_version={res.model_version}\n# section=lap_trace\n")
    trace.to_csv(buf, index=False)
    if isinstance(deg, dict) and isinstance(deg.get("current"), dict):
        buf.write("# section=tyre_degradation_current\n")
        pd.DataFrame(deg["current"]).to_csv(buf, index=False)
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="apexvision-lap-trace.csv"'})
