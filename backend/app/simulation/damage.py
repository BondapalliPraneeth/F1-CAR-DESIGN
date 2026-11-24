"""Damage engine.

Translates a list of component damages into *physical modifiers* of the vehicle
model (aero surface efficiencies, ride height, grip, cooling, power ...).
Each component type has its own transfer function; there is no generic
"damage = x% slower" penalty. All coefficients below are modelling assumptions
chosen to represent the *direction and relative magnitude* of known effects.
They are documented in docs/simulation_methodology.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.components import COMPONENTS_BY_ID, valid_damage_types

SEVERITY_LEVELS = [
    (0.0, "healthy"),
    (20.0, "minor"),
    (45.0, "moderate"),
    (75.0, "severe"),
    (100.0, "critical"),
]


def classify_severity(severity: float) -> str:
    """0 -> healthy, (0,20] minor, (20,45] moderate, (45,75] severe, (75,100] critical."""
    if severity <= 0:
        return "healthy"
    for upper, label in SEVERITY_LEVELS[1:]:
        if severity <= upper:
            return label
    return "critical"


class DamageInput(BaseModel):
    component_id: str
    damage_type: str
    severity: float = Field(..., ge=0, le=100, description="Damage severity in percent")

    @field_validator("component_id")
    @classmethod
    def _known_component(cls, v: str) -> str:
        if v not in COMPONENTS_BY_ID:
            raise ValueError(f"Unknown component_id '{v}'")
        return v

    @model_validator(mode="after")
    def _known_damage_type(self) -> DamageInput:
        allowed = valid_damage_types(self.component_id)
        if self.damage_type not in allowed:
            raise ValueError(
                f"damage_type '{self.damage_type}' is not valid for '{self.component_id}'. Allowed: {allowed}"
            )
        return self


@dataclass
class VehicleModifiers:
    """Multiplicative / additive modifiers applied on top of the healthy model."""

    cl_factor: dict[str, float] = field(default_factory=dict)  # per aero surface
    cd_factor: dict[str, float] = field(default_factory=dict)  # per component drag share
    ride_height_delta_front_mm: float = 0.0
    ride_height_delta_rear_mm: float = 0.0
    grip_factor_front: float = 1.0
    grip_factor_rear: float = 1.0
    puncture_front: float = 0.0  # 0..1
    puncture_rear: float = 0.0
    tyre_temp_delta_front_c: float = 0.0
    tyre_temp_delta_rear_c: float = 0.0
    brake_cooling_factor_front: float = 1.0
    brake_cooling_factor_rear: float = 1.0
    radiator_effectiveness_factor: float = 1.0
    inlet_area_factor: float = 1.0
    heat_to_coolant_factor: float = 1.0
    power_factor: float = 1.0
    drs_forced_open_fraction: float = 0.0  # stuck-open flap fraction in corners
    drs_effect_available: float = 1.0  # stuck-closed reduces this
    structural_integrity: dict[str, float] = field(default_factory=dict)
    mechanisms: list[dict] = field(default_factory=list)

    def mul_cl(self, surface: str, factor: float) -> None:
        self.cl_factor[surface] = self.cl_factor.get(surface, 1.0) * max(factor, 0.0)

    def mul_cd(self, comp: str, factor: float) -> None:
        self.cd_factor[comp] = self.cd_factor.get(comp, 1.0) * max(factor, 0.0)

    def explain(self, component_id: str, damage_type: str, text: str) -> None:
        self.mechanisms.append({"component_id": component_id, "damage_type": damage_type, "explanation": text})


def _apply(m: VehicleModifiers, dmg: DamageInput) -> None:
    d = dmg.severity / 100.0
    c, t = dmg.component_id, dmg.damage_type
    pct = lambda x: f"{x * 100:.0f}%"  # noqa: E731

    if d <= 0:
        return

    if c == "front_wing" and t == "endplate_damage":
        m.mul_cl("front_wing", 1 - 0.30 * d)
        m.mul_cl("floor", 1 - 0.08 * d)
        m.mul_cl("venturi_tunnels", 1 - 0.06 * d)
        m.mul_cd("front_wing", 1 + 0.25 * d)
        m.explain(c, t, f"Endplate loss reduces front-wing load by {pct(0.30 * d)} and lets front-tyre wake reach the floor inlet "
                        f"(floor -{pct(0.08 * d)}, tunnels -{pct(0.06 * d)}). Separated flow adds {pct(0.25 * d)} to the wing's drag.")
    elif c == "front_wing" and t == "element_failure":
        m.mul_cl("front_wing", 1 - 0.80 * d)
        m.mul_cl("floor", 1 - 0.04 * d)
        m.mul_cd("front_wing", 1 - 0.35 * d)
        m.explain(c, t, f"Failed flap elements remove {pct(0.80 * d)} of front-wing load. Less load means less induced drag "
                        f"(wing drag -{pct(0.35 * d)}), but the balance shifts strongly rearwards and the car understeers.")
    elif c == "nose_cone":
        m.mul_cl("front_wing", 1 - 0.25 * d)
        m.mul_cd("nose_cone", 1 + 0.6 * d)
        m.structural_integrity[c] = 1 - d
        m.explain(c, t, f"A crushed nose misaligns the front wing (front-wing load -{pct(0.25 * d)}) and adds bluff-body drag.")
    elif c in ("front_suspension", "rear_suspension"):
        front = c == "front_suspension"
        drop = 15.0 * d
        if front:
            m.ride_height_delta_front_mm -= drop
            m.grip_factor_front *= 1 - 0.22 * d
        else:
            m.ride_height_delta_rear_mm -= drop
            m.grip_factor_rear *= 1 - 0.22 * d
        m.mul_cd(c, 1 + 0.5 * d)
        axle = "front" if front else "rear"
        m.explain(c, t, f"Bent members introduce camber/toe error ({axle} mechanical grip -{pct(0.22 * d)}) and the "
                        f"{axle} ride height drops by {drop:.1f} mm, moving the floor away from its optimum height.")
    elif c in ("front_tyres", "rear_tyres") and t == "puncture":
        front = c == "front_tyres"
        if front:
            m.puncture_front = max(m.puncture_front, d)
            m.ride_height_delta_front_mm -= 20.0 * d
        else:
            m.puncture_rear = max(m.puncture_rear, d)
            m.ride_height_delta_rear_mm -= 20.0 * d
        m.mul_cd(c, 1 + 0.3 * d)
        m.explain(c, t, f"Pressure loss of {pct(d)} collapses the sidewall: axle grip falls sharply, the corner drops "
                        f"{20 * d:.1f} mm and the deformed tyre adds drag.")
    elif c in ("front_tyres", "rear_tyres") and t == "overheating":
        dt = 45.0 * d
        if c == "front_tyres":
            m.tyre_temp_delta_front_c += dt
        else:
            m.tyre_temp_delta_rear_c += dt
        m.explain(c, t, f"Surface temperature rises by {dt:.0f} degC, moving the tyre out of its operating window: friction falls and wear rate rises.")
    elif c in ("front_brakes", "rear_brakes"):
        f = 1 - 0.85 * d
        if c == "front_brakes":
            m.brake_cooling_factor_front *= f
        else:
            m.brake_cooling_factor_rear *= f
        m.explain(c, t, f"Duct blockage removes {pct(0.85 * d)} of convective disc cooling. Disc temperature climbs; above the "
                        f"friction window the carbon fades and oxidises.")
    elif c == "sidepods":
        m.inlet_area_factor *= 1 - 0.6 * d
        m.mul_cd("sidepods", 1 + 0.8 * d)
        m.explain(c, t, f"A deformed inlet cuts cooling air mass flow by {pct(0.6 * d)} and torn bodywork adds {pct(0.8 * d)} to the sidepod drag.")
    elif c == "radiators":
        m.radiator_effectiveness_factor *= 1 - 0.85 * d
        m.explain(c, t, f"Radiator effectiveness falls by {pct(0.85 * d)}; heat rejection drops and coolant temperature rises toward the derate limit.")
    elif c == "floor":
        loss = 0.55 * d ** 0.8
        m.mul_cl("floor", 1 - loss)
        m.mul_cl("venturi_tunnels", 1 - 0.25 * d)
        m.mul_cl("diffuser", 1 - 0.20 * d)
        m.mul_cd("floor", 1 + 0.6 * d)
        m.explain(c, t, f"The torn edge breaks the underfloor seal: floor load -{pct(loss)}, and the leak raises underfloor pressure "
                        f"for the tunnels (-{pct(0.25 * d)}) and diffuser (-{pct(0.20 * d)}).")
    elif c == "venturi_tunnels":
        m.mul_cl("venturi_tunnels", 1 - 0.5 * d)
        m.mul_cl("diffuser", 1 - 0.1 * d)
        m.mul_cd("venturi_tunnels", 1 + 0.4 * d)
        m.explain(c, t, f"Damaged fences weaken the vortices that keep tunnel flow attached: tunnel load -{pct(0.5 * d)}, diffuser -{pct(0.1 * d)}.")
    elif c == "diffuser":
        m.mul_cl("diffuser", 1 - 0.7 * d)
        m.mul_cl("venturi_tunnels", 1 - 0.15 * d)
        m.mul_cl("floor", 1 - 0.05 * d)
        m.mul_cd("diffuser", 1 + 0.3 * d)
        m.explain(c, t, f"Poor pressure recovery: diffuser load -{pct(0.7 * d)}, and the higher base pressure reduces upstream tunnel suction (-{pct(0.15 * d)}).")
    elif c == "rear_wing":
        m.mul_cl("rear_wing", 1 - 0.6 * d)
        m.mul_cl("drs", 1 - 0.6 * d)
        m.mul_cd("rear_wing", 1 - 0.2 * d)
        m.explain(c, t, f"Rear-wing load -{pct(0.6 * d)}. Induced drag falls with it (wing drag -{pct(0.2 * d)}), so the balance moves "
                        f"forward: top speed rises slightly but the rear becomes unstable in fast corners.")
    elif c == "drs" and t == "stuck_open":
        m.drs_forced_open_fraction = max(m.drs_forced_open_fraction, d)
        m.explain(c, t, f"The flap stays {pct(d)} open in corners, removing rear-wing load where it is needed.")
    elif c == "drs" and t == "stuck_closed":
        m.drs_effect_available *= 1 - d
        m.explain(c, t, f"The flap only achieves {pct(1 - d)} of its normal opening, so the straight-line drag reduction is lost.")
    elif c == "power_unit" and t == "engine_overheating":
        m.heat_to_coolant_factor *= 1 + 1.0 * d
        m.explain(c, t, f"An internal fault increases heat rejected to coolant by {pct(1.0 * d)}. Above the coolant limit the power unit derates.")
    elif c == "power_unit" and t == "power_loss":
        m.power_factor *= 1 - 0.4 * d
        m.explain(c, t, f"Deliverable power reduced by {pct(0.4 * d)} (lumped hybrid/ICE fault).")
    elif c in ("monocoque", "halo", "cockpit", "rear_crash_structure"):
        m.structural_integrity[c] = 1 - d
        m.mul_cd(c, 1 + 0.3 * d)
        if c == "rear_crash_structure":
            m.mul_cl("rear_wing", 1 - 0.05 * d)
        m.explain(c, t, f"Structural integrity reduced to {pct(1 - d)}. This is a safety-cell / impact-structure issue, not a "
                        f"performance device; only a small drag increase is modelled.")


def build_modifiers(damages: list[DamageInput]) -> VehicleModifiers:
    m = VehicleModifiers()
    for dmg in damages:
        _apply(m, dmg)
    return m
