"""Lumped-capacitance thermal models for brakes and the power-unit coolant loop.

Brake disc (per disc):
    m_d c_d dT/dt = eta_disc * P_brake_axle / 2 - h(v) (T - T_amb) - eps sigma A (T^4 - T_amb^4)
    h(v) = (h_0 + k_v v) * duct_factor

Coolant loop:
    C dT/dt = f_hc * P_delivered - eps * mdot(v) * cp_air * (T - T_amb)
    mdot(v) = rho * v * duct_velocity_ratio * A_inlet

Both are solved exactly for piecewise-constant inputs along the lap time trace
(radiation is linearised about the previous iterate).
"""

from __future__ import annotations

import numpy as np

from app.simulation.assumptions import VehicleAssumptions

CP_AIR = 1005.0  # J/kg/K
DISC_ENERGY_FRACTION = 0.9  # share of brake energy absorbed by the disc (rest: pads)
SIGMA = 5.670374419e-8  # Stefan-Boltzmann constant [W/m^2/K^4]
DISC_EMISSIVITY = 0.8  # assumed emissivity of an oxidised carbon disc
DISC_RADIATING_AREA_M2 = 0.14  # two faces of an annulus r_o=0.17 m, r_i=0.08 m (assumed)


def brake_friction_factor(a: VehicleAssumptions, t_c: float) -> float:
    """1.0 inside the friction window, reduced when cold, fading when overheated."""
    if t_c < a.brake_optimal_min_c:
        return 0.75 + 0.25 * max(t_c, 0.0) / a.brake_optimal_min_c
    if t_c > a.brake_optimal_max_c:
        return max(0.4, 1.0 - 0.0012 * (t_c - a.brake_optimal_max_c))
    return 1.0


def brake_wear_index(a: VehicleAssumptions, t_c: float) -> float:
    """Relative oxidation-wear rate (1.0 at 700 degC); exponential in temperature."""
    return float(np.exp((t_c - 700.0) / 120.0))


def _first_order_trace(t0: float, t_eq: np.ndarray, decay: np.ndarray) -> np.ndarray:
    """Exact solution of C dT/dt = h (T_eq - T) with piecewise-constant inputs.

    T_{i+1} = T_eq_i + (T_i - T_eq_i) * a_i,  a_i = exp(-h_i dt_i / C)
    Solved in closed form with cumulative sums (vectorised, no Python loop):
    T_i = P_i * (T0 + sum_{k<=i} (1-a_k) T_eq_k / P_k),  P_i = prod_{k<=i} a_k
    """
    log_p = np.cumsum(np.log(decay))
    p = np.exp(log_p)
    acc = np.cumsum((1.0 - decay) * t_eq * np.exp(-log_p))
    return p * (t0 + acc)


def integrate_brakes(
    a: VehicleAssumptions,
    dt: np.ndarray,
    v: np.ndarray,
    p_brake: np.ndarray,
    bias: float,
    cooling_factor: float,
    t0: float,
    laps: int = 4,
) -> tuple[np.ndarray, float]:
    """Disc temperature trace of the final lap (after `laps` laps) and end temperature."""
    cap = a.brake_disc_mass_kg * a.brake_disc_specific_heat
    h_conv = np.maximum((a.brake_cooling_static + a.brake_cooling_coeff * v) * cooling_factor, 1e-3)
    q_in = DISC_ENERGY_FRACTION * p_brake * bias / 2.0
    ta_k = a.ambient_temp_c + 273.15
    t = t0
    trace = np.full_like(v, t0)
    for _ in range(laps):
        # Radiation q = eps sigma A (T^4 - Ta^4) linearised as h_rad (T - Ta) using the previous trace
        tk = trace + 273.15
        h_rad = DISC_EMISSIVITY * SIGMA * DISC_RADIATING_AREA_M2 * (tk ** 2 + ta_k ** 2) * (tk + ta_k)
        h = h_conv + h_rad
        t_eq = a.ambient_temp_c + q_in / h
        decay = np.exp(-h * dt / cap)
        trace = _first_order_trace(t, t_eq, decay)
        t = float(trace[-1])
    return trace, t


def coolant_step_trace(
    a: VehicleAssumptions,
    dt: np.ndarray,
    v: np.ndarray,
    p_delivered: np.ndarray,
    eff_factor: float,
    inlet_factor: float,
    heat_factor: float,
    t0: float,
) -> np.ndarray:
    eps = a.radiator_effectiveness * eff_factor
    area = a.cooling_inlet_area_m2 * inlet_factor
    mdot = a.air_density * v * a.cooling_duct_velocity_ratio * area
    h = np.maximum(eps * mdot * CP_AIR, 1.0)
    q_in = a.heat_to_coolant_fraction * heat_factor * p_delivered
    t_eq = a.ambient_temp_c + q_in / h
    decay = np.exp(-h * dt / a.coolant_thermal_mass_j_per_k)
    return _first_order_trace(t0, t_eq, decay)


def braking_weighted_temp(trace: np.ndarray, p_brake: np.ndarray, dt: np.ndarray) -> float:
    """Disc temperature weighted by braking energy: the temperature the pads see when it matters."""
    w = p_brake * dt
    return float((trace * w).sum() / w.sum()) if w.sum() > 0 else float(trace.mean())


def power_derate(a: VehicleAssumptions, coolant_c: float) -> float:
    """Linear derate from 100% at the limit to 50% at limit + span (floor 50%)."""
    over = coolant_c - a.coolant_limit_c
    if over <= 0:
        return 1.0
    return max(0.5, 1.0 - 0.5 * over / a.coolant_derate_span_c)
