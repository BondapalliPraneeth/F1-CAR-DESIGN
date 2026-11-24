from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import SESSION_PATTERN
from app.db import repository as repo
from app.db.session import get_db
from app.domain.components import COMPONENTS, DAMAGE_SCENARIOS, get_component
from app.simulation.assumptions import VehicleAssumptions
from app.simulation.damage import DamageInput
from app.simulation.vehicle import MODEL_VERSION, simulate

router = APIRouter(tags=["car"])


@router.get("/car")
def get_car() -> dict:
    fields = VehicleAssumptions.model_fields
    return {
        "id": repo.CAR_SLUG,
        "name": "ApexVision AV-1",
        "description": "Original, generic ground-effect open-wheel concept car. Not a replica of any real team's car.",
        "asset_url": "/models/apexvision_av1.glb",
        "model_version": MODEL_VERSION,
        "component_count": len(COMPONENTS),
        "assumptions": [
            {"key": k, "default": f.default, "description": f.description} for k, f in fields.items()
        ],
        "scenarios": DAMAGE_SCENARIOS,
    }


@router.get("/components")
def list_components() -> list[dict]:
    return [
        {"id": c.id, "name": c.name, "category": c.category, "analysis_panel": c.analysis_panel,
         "damage_susceptibility": c.damage_susceptibility,
         "damage_types": [asdict(d) for d in c.damage_types]}
        for c in COMPONENTS
    ]


@router.get("/components/{component_id}")
def component_detail(component_id: str) -> dict:
    c = get_component(component_id)
    if not c:
        raise HTTPException(status_code=404, detail={"error": "component_not_found", "component_id": component_id,
                                                     "valid_ids": [x.id for x in COMPONENTS]})
    d = asdict(c)
    d["parameters"] = repo.component_parameters(c.id)
    return d


@router.get("/vehicle/status")
def vehicle_status(session_id: str = Query("anonymous", pattern=SESSION_PATTERN), db: Session = Depends(get_db)) -> dict:
    sim = repo.latest_simulation(db, session_id)
    if sim is None:
        res = simulate(VehicleAssumptions(), [], curves=False)
        return {"source": "baseline", "simulation_id": None, "result": res.model_dump(exclude={"curves"})}
    a = VehicleAssumptions(**sim.assumptions)
    res = simulate(a, [DamageInput(**d) for d in sim.damages], curves=False)
    rep = repo.report_for_simulation(db, sim.id)
    return {"source": "latest_saved_simulation", "simulation_id": sim.id, "report_id": rep.id if rep else None,
            "created_at": sim.created_at, "result": res.model_dump(exclude={"curves"})}


@router.get("/scenarios")
def scenarios() -> list[dict]:
    return DAMAGE_SCENARIOS


@router.get("/history")
def get_history(session_id: str = Query(..., pattern=SESSION_PATTERN), db: Session = Depends(get_db)) -> list[dict]:
    rows = repo.history(db, session_id)
    out = []
    for h in rows:
        rep = repo.report_for_simulation(db, h.simulation_id)
        out.append({"id": h.id, "simulation_id": h.simulation_id, "report_id": rep.id if rep else None,
                    "action": h.action, "summary": h.summary, "created_at": h.created_at})
    return out
