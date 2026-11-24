"""Component-resolved aerodynamic model.

    F_drag      = 0.5 * rho * v^2 * Cd * A_frontal
    F_downforce = 0.5 * rho * v^2 * Cl * A_reference

The whole-car Cl and Cd are split into per-component shares (see
assumptions.AERO_DOWNFORCE_SHARE / DRAG_SHARE). Damage multiplies individual
shares; underfloor shares are also scaled by a ride-height sensitivity curve.
Balance is the moment split of each surface's load between the axles given its
centre-of-pressure position. This is a lumped coefficient model, not CFD.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.simulation.assumptions import AERO_DOWNFORCE_SHARE, DRAG_SHARE, VehicleAssumptions
from app.simulation.damage import VehicleModifiers

UNDERFLOOR = ("floor", "venturi_tunnels", "diffuser")
DRS_SURFACES = ("rear_wing", "drs")


@dataclass
class AeroCoefficients:
    cla_total: float  # m^2
    cda_total: float  # m^2
    cla_front: float
    cla_rear: float
    front_balance: float  # fraction of downforce on the front axle
    cla_by_component: dict[str, float]
    cda_by_component: dict[str, float]
    ride_height_factor: float
    effective_ride_height_mm: float

    @property
    def cl(self) -> float:
        return self.cla_total

    @property
    def efficiency(self) -> float:
        return self.cla_total / self.cda_total if self.cda_total > 0 else 0.0


def ride_height_factor(a: VehicleAssumptions, h_mm: float) -> float:
    """Quadratic loss of underfloor load away from the optimum ride height.

    Running lower than the optimum is penalised 1.5x harder than running higher
    (approximating flow choking / stall close to the ground). Clipped at 0.3.
    """
    dh = h_mm - a.optimal_ride_height_mm
    k = a.ride_height_sensitivity * (1.5 if dh < 0 else 1.0)
    return float(np.clip(1.0 - k * dh * dh, 0.3, 1.0))


def aero_coefficients(
    a: VehicleAssumptions, m: VehicleModifiers, drs_open_fraction: float = 0.0
) -> AeroCoefficients:
    cla_base = a.cl_baseline * a.reference_area_m2
    cda_base = a.cd_baseline * a.frontal_area_m2

    h_eff = a.ride_height_mm + 0.5 * (m.ride_height_delta_front_mm + m.ride_height_delta_rear_mm)
    rh = ride_height_factor(a, h_eff)

    flap = float(np.clip(max(drs_open_fraction * m.drs_effect_available, m.drs_forced_open_fraction), 0.0, 1.0))

    cla_by: dict[str, float] = {}
    front_moment = 0.0
    for comp, (share, x_cp) in AERO_DOWNFORCE_SHARE.items():
        v = cla_base * share * m.cl_factor.get(comp, 1.0)
        if comp in UNDERFLOOR:
            v *= rh
        if comp in DRS_SURFACES:
            v *= 1.0 - a.drs_rear_wing_cl_reduction * flap
        cla_by[comp] = v
        front_moment += v * (a.wheelbase_m - x_cp) / a.wheelbase_m

    cda_by: dict[str, float] = {}
    for comp, share in DRAG_SHARE.items():
        v = cda_base * share * m.cd_factor.get(comp, 1.0)
        if comp in DRS_SURFACES:
            v *= 1.0 - a.drs_rear_wing_cd_reduction * flap
        cda_by[comp] = v

    cla = sum(cla_by.values())
    cda = sum(cda_by.values())
    return AeroCoefficients(
        cla_total=cla,
        cda_total=cda,
        cla_front=front_moment,
        cla_rear=cla - front_moment,
        front_balance=front_moment / cla if cla > 0 else 0.0,
        cla_by_component=cla_by,
        cda_by_component=cda_by,
        ride_height_factor=rh,
        effective_ride_height_mm=h_eff,
    )


def dynamic_pressure(a: VehicleAssumptions, v_ms: float | np.ndarray) -> float | np.ndarray:
    return 0.5 * a.air_density * np.asarray(v_ms) ** 2


def forces_at_speed(a: VehicleAssumptions, coeffs: AeroCoefficients, v_kmh: float) -> dict:
    q = float(dynamic_pressure(a, v_kmh / 3.6))
    return {
        "speed_kmh": v_kmh,
        "dynamic_pressure_pa": q,
        "downforce_n": q * coeffs.cla_total,
        "drag_n": q * coeffs.cda_total,
        "front_downforce_n": q * coeffs.cla_front,
        "rear_downforce_n": q * coeffs.cla_rear,
        "cl": coeffs.cla_total / a.reference_area_m2,
        "cd": coeffs.cda_total / a.frontal_area_m2,
        "lift_to_drag": coeffs.efficiency,
        "front_balance_pct": coeffs.front_balance * 100,
        "drag_power_kw": q * coeffs.cda_total * (v_kmh / 3.6) / 1000,
    }


def speed_sweep(a: VehicleAssumptions, coeffs: AeroCoefficients, speeds_kmh: np.ndarray) -> dict:
    q = dynamic_pressure(a, speeds_kmh / 3.6)
    return {
        "speed_kmh": speeds_kmh.tolist(),
        "downforce_n": (q * coeffs.cla_total).tolist(),
        "drag_n": (q * coeffs.cda_total).tolist(),
    }
