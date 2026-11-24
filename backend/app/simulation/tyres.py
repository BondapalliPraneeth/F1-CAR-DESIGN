"""Empirical tyre grip model.

mu = mu_peak * f_temp(T) * f_wear(w) * f_puncture(p) * f_geometry

Shapes are smooth, monotonic engineering approximations chosen to reproduce the
known qualitative behaviour of racing tyres (operating window, wear cliff,
deflation). They are not a fitted Pacejka model.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.simulation.assumptions import VehicleAssumptions


def f_temp(a: VehicleAssumptions, t_c: float) -> float:
    x = (t_c - a.tyre_optimal_temp_c) / a.tyre_window_halfwidth_c
    return float(np.clip(1.0 - 0.12 * x * x, 0.55, 1.0))


def f_wear(w: float) -> float:
    w = float(np.clip(w, 0.0, 1.2))
    return float(np.clip(1.0 - 0.15 * w - 0.8 * max(0.0, w - 0.7) ** 2, 0.5, 1.0))


def f_puncture(p: float) -> float:
    return 1.0 - 0.75 * float(np.clip(p, 0.0, 1.0))


@dataclass
class AxleTyreState:
    temp_c: float
    pressure_psi: float
    wear: float
    wear_rate_per_lap: float
    mu: float
    temp_factor: float
    wear_factor: float
    puncture_factor: float
    geometry_factor: float


def axle_state(
    a: VehicleAssumptions,
    *,
    temp_delta_c: float,
    puncture: float,
    geometry_factor: float,
    balance_shift_pct: float,
    is_front: bool,
    wear: float = 0.0,
) -> AxleTyreState:
    """balance_shift_pct: current - baseline front balance in percentage points.
    A rearward shift overloads the front tyres (understeer -> front sliding) and
    vice versa; sliding heats the overloaded axle by 1.2 degC per point."""
    slide = -balance_shift_pct if is_front else balance_shift_pct
    t = a.tyre_surface_temp_c + 0.4 * (a.track_temp_c - 40.0) + temp_delta_c + 1.2 * max(0.0, slide)
    ft, fp = f_temp(a, t), f_puncture(puncture)
    fw = f_wear(wear)
    over = max(0.0, t - a.tyre_optimal_temp_c)
    rate = a.tyre_wear_per_lap * (1 + 0.04 * over) * (1 + 1.5 * (1 - geometry_factor)) * (1 + 3 * puncture)
    return AxleTyreState(
        temp_c=t,
        pressure_psi=a.tyre_pressure_psi * (1 - puncture),
        wear=wear,
        wear_rate_per_lap=rate,
        mu=a.tyre_mu_peak * ft * fw * fp * geometry_factor,
        temp_factor=ft,
        wear_factor=fw,
        puncture_factor=fp,
        geometry_factor=geometry_factor,
    )
