"""Quasi-steady-state point-mass lap simulation.

1. Corner speed limit per node (closed form, per axle, with downforce):
       v^2 / R = mu (w m g + q ClA_axle) / (w m)
   =>  v^2 = mu g / (1/R - mu * 0.5 rho ClA_axle / (w m))
   The lower of the two axles sets the limit, so aero balance matters.
2. Forward pass: traction- and power-limited acceleration.
3. Backward pass: tyre- and brake-limited deceleration with brake bias.
4. Speed = min(limit, forward, backward); lap time = sum(dx / v_mean).

Known simplifications: no combined-slip (friction circle), no load transfer
dynamics, no gear shifts, constant mass, no tyre-temperature evolution in lap.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from app.simulation.aerodynamics import AeroCoefficients
from app.simulation.assumptions import VehicleAssumptions
from app.simulation.track import DX, Track


@dataclass
class LapInputs:
    coeff_corner: AeroCoefficients  # flap closed (or forced-open state)
    coeff_drs: AeroCoefficients  # coefficients in DRS zones
    mu_front: float
    mu_rear: float
    power_factor: float  # damage x thermal derate
    brake_factor: float  # combined friction factor (fade)


@dataclass
class LapResult:
    lap_time_s: float
    v: np.ndarray
    dt: np.ndarray
    p_drive: np.ndarray
    p_brake: np.ndarray

    @property
    def v_kmh(self) -> np.ndarray:
        return self.v * 3.6


def corner_limit(a: VehicleAssumptions, c: AeroCoefficients, mu_f: float, mu_r: float, radius: np.ndarray) -> np.ndarray:
    m, g = a.mass_kg, a.gravity
    out = np.full(radius.shape, np.inf)
    for mu, cla_axle, w in ((mu_f, c.cla_front, a.static_front_weight_fraction),
                            (mu_r, c.cla_rear, 1 - a.static_front_weight_fraction)):
        k = 0.5 * a.air_density * cla_axle / (w * m)
        with np.errstate(divide="ignore"):
            denom = 1.0 / radius - mu * k
            v2 = np.where(denom > 0, mu * g / np.where(denom > 0, denom, 1.0), np.inf)
        out = np.minimum(out, np.sqrt(v2))
    return out


def _forces(a: VehicleAssumptions, c: AeroCoefficients, v: float):
    q = 0.5 * a.air_density * v * v
    nf = a.static_front_weight_fraction * a.mass_kg * a.gravity + q * c.cla_front
    nr = (1 - a.static_front_weight_fraction) * a.mass_kg * a.gravity + q * c.cla_rear
    res = q * c.cda_total + a.rolling_resistance_coeff * (nf + nr)
    return nf, nr, res


def simulate_lap(a: VehicleAssumptions, track: Track, inp: LapInputs) -> LapResult:
    n = len(track.s)
    use_drs = track.drs & a.drs_zones_enabled
    v_lim = corner_limit(a, inp.coeff_corner, inp.mu_front, inp.mu_rear, track.radius)
    v_lim = np.minimum(v_lim, 120.0)
    p_eff = a.power_kw * 1000 * a.drivetrain_efficiency * inp.power_factor
    m = a.mass_kg
    bias = a.front_brake_bias

    # forward pass (two laps so the start speed is periodic)
    vf = np.empty(n)
    v = float(v_lim.min())
    for _ in range(2):
        for i in range(n):
            v = min(v, v_lim[i])
            vf[i] = v
            c = inp.coeff_drs if use_drs[i] else inp.coeff_corner
            nf, nr, res = _forces(a, c, v)
            f_drive = min(p_eff / max(v, 1.0), inp.mu_rear * nr)
            acc = (f_drive - res) / m
            v = np.sqrt(max(v * v + 2 * acc * DX, 0.0))

    # backward pass
    vb = np.empty(n)
    v = float(vf[0])
    for _ in range(2):
        for i in range(n - 1, -1, -1):
            v = min(v, v_lim[i])
            vb[i] = v
            c = inp.coeff_drs if use_drs[i] else inp.coeff_corner
            nf, nr, res = _forces(a, c, v)
            f_brake = min(inp.mu_front * nf / bias, inp.mu_rear * nr / (1 - bias)) * inp.brake_factor
            dec = (f_brake + res) / m
            v = np.sqrt(v * v + 2 * dec * DX)

    vel = np.minimum(vf, vb)
    v_next = np.roll(vel, -1)
    v_mean = np.maximum(0.5 * (vel + v_next), 1.0)
    dt = DX / v_mean

    # power bookkeeping for the thermal models
    acc = (v_next ** 2 - vel ** 2) / (2 * DX)
    q = 0.5 * a.air_density * v_mean ** 2
    cda = np.where(use_drs, inp.coeff_drs.cda_total, inp.coeff_corner.cda_total)
    cla = np.where(use_drs, inp.coeff_drs.cla_total, inp.coeff_corner.cla_total)
    res = q * cda + a.rolling_resistance_coeff * (m * a.gravity + q * cla)
    f_needed = m * acc + res
    p_drive = np.clip(f_needed, 0, None) * v_mean
    p_drive = np.minimum(p_drive, p_eff)
    p_brake = np.clip(-f_needed, 0, None) * v_mean
    return LapResult(lap_time_s=float(dt.sum()), v=vel, dt=dt, p_drive=p_drive, p_brake=p_brake)


def top_speed_kmh(a: VehicleAssumptions, c: AeroCoefficients, power_factor: float) -> float:
    p = a.power_kw * 1000 * a.drivetrain_efficiency * power_factor

    def balance(v: float) -> float:
        _, _, res = _forces(a, c, v)
        return p - res * v

    return float(brentq(balance, 5.0, 200.0) * 3.6)


def corner_speed_kmh(a: VehicleAssumptions, c: AeroCoefficients, mu_f: float, mu_r: float, radius: float) -> float:
    v = corner_limit(a, c, mu_f, mu_r, np.array([radius]))[0]
    return float(min(v, 120.0) * 3.6)


def braking_distance_m(a: VehicleAssumptions, inp: LapInputs, v0_kmh: float = 300, v1_kmh: float = 100) -> float:
    v, dist = v0_kmh / 3.6, 0.0
    step = 0.5
    while v > v1_kmh / 3.6:
        nf, nr, res = _forces(a, inp.coeff_corner, v)
        f = min(inp.mu_front * nf / a.front_brake_bias, inp.mu_rear * nr / (1 - a.front_brake_bias)) * inp.brake_factor
        dec = (f + res) / a.mass_kg
        v = np.sqrt(max(v * v - 2 * dec * step, 0.0))
        dist += step
    return dist


def max_lateral_g(a: VehicleAssumptions, c: AeroCoefficients, mu_f: float, mu_r: float, v_kmh: float) -> float:
    v = v_kmh / 3.6
    nf, nr, _ = _forces(a, c, v)
    w = a.static_front_weight_fraction
    acc = min(mu_f * nf / (w * a.mass_kg), mu_r * nr / ((1 - w) * a.mass_kg))
    return acc / a.gravity
