from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.simulation.assumptions import VehicleAssumptions
from app.simulation.damage import DamageInput
from app.simulation.vehicle import SimulationResult

SESSION_PATTERN = r"^[A-Za-z0-9_-]{6,64}$"


class VehicleState(BaseModel):
    damages: list[DamageInput] = Field(default_factory=list, max_length=40)
    assumptions: VehicleAssumptions = Field(default_factory=VehicleAssumptions)


class DamageSimulateRequest(VehicleState):
    session_id: str = Field("anonymous", pattern=SESSION_PATTERN)
    persist: bool = Field(False, description="Store the run, its report and a history entry in the database")
    scenario_id: str | None = None
    focus: DamageInput | None = Field(None, description="Damage used for the severity-vs-loss sweep chart")
    include_curves: bool = True


class DamageSimulateResponse(BaseModel):
    simulation_id: str | None
    report_id: str | None
    persisted: bool
    result: SimulationResult


class AeroRequest(VehicleState):
    speed_kmh: float = Field(250.0, ge=30, le=400)
    drs_open: bool = False


class CompareRequest(BaseModel):
    a: VehicleState = Field(default_factory=VehicleState, description="Reference condition (default: healthy)")
    b: VehicleState


class AskRequest(VehicleState):
    session_id: str = Field("anonymous", pattern=SESSION_PATTERN)
    question: str = Field(..., min_length=2, max_length=600)
    selected_component: str | None = None


class AskResponse(BaseModel):
    answer: str
    provider: str
    mode: str
    tool_calls: list[dict[str, Any]]
    numeric_claims_verified: bool
    unverified_values: list[str]
    notice: str | None
    label: str
