"""Configurable model assumptions.

Every number here is a *generic, order-of-magnitude modelling assumption* for an
open-wheel, ground-effect racing car. None of them are measured values from any
real Formula 1 team or car. They are chosen to be physically plausible so that
the relative effect of damage can be studied, and every one of them can be
overridden per request through the API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class VehicleAssumptions(BaseModel):
    # --- Environment -------------------------------------------------------
    air_density: float = Field(1.225, gt=0.5, lt=1.6, description="Air density [kg/m^3] (ISA sea level)")
    ambient_temp_c: float = Field(25.0, ge=-10, le=50, description="Ambient air temperature [degC]")
    track_temp_c: float = Field(40.0, ge=0, le=70, description="Track surface temperature [degC]")
    gravity: float = Field(9.81, description="Gravitational acceleration [m/s^2]")

    # --- Mass & geometry ---------------------------------------------------
    mass_kg: float = Field(800.0, gt=500, lt=1200, description="Vehicle mass incl. driver and fuel [kg]")
    wheelbase_m: float = Field(3.6, gt=2.5, lt=4.0, description="Wheelbase [m]")
    static_front_weight_fraction: float = Field(0.45, gt=0.3, lt=0.6, description="Static weight on front axle [-]")
    frontal_area_m2: float = Field(1.5, gt=0.8, lt=2.5, description="Frontal area used for drag coefficient [m^2]")
    reference_area_m2: float = Field(1.5, gt=0.8, lt=2.5, description="Reference area used for lift coefficient [m^2]")

    # --- Aerodynamics (whole-car, healthy) ---------------------------------
    cd_baseline: float = Field(0.88, gt=0.3, lt=1.5, description="Healthy whole-car drag coefficient (on frontal area) [-]")
    cl_baseline: float = Field(2.70, gt=0.5, lt=5.0, description="Healthy whole-car downforce coefficient (on reference area) [-]")
    ride_height_mm: float = Field(35.0, ge=10, le=80, description="Static reference ride height [mm]")
    optimal_ride_height_mm: float = Field(35.0, ge=10, le=80, description="Ride height of peak floor performance [mm]")
    ride_height_sensitivity: float = Field(0.0009, ge=0, le=0.01, description="Quadratic floor-load loss per mm^2 away from optimum [-]")
    drs_open: bool = Field(False, description="DRS flap open for the single-point aero calculation")
    drs_zones_enabled: bool = Field(True, description="Use DRS in the designated straights of the lap simulation")
    drs_rear_wing_cl_reduction: float = Field(0.55, ge=0, le=0.9, description="Fraction of rear-wing downforce removed by open DRS [-]")
    drs_rear_wing_cd_reduction: float = Field(0.35, ge=0, le=0.9, description="Fraction of rear-wing drag removed by open DRS [-]")

    # --- Power unit & cooling ---------------------------------------------
    power_kw: float = Field(750.0, gt=200, lt=1200, description="Combined peak power at the wheels [kW]")
    drivetrain_efficiency: float = Field(0.92, gt=0.5, le=1.0, description="Mechanical efficiency to the wheels [-]")
    rolling_resistance_coeff: float = Field(0.015, ge=0, le=0.05, description="Tyre rolling-resistance coefficient [-]")
    heat_to_coolant_fraction: float = Field(0.32, gt=0.05, lt=0.8, description="Fraction of delivered power rejected to coolant [-]")
    radiator_effectiveness: float = Field(0.65, gt=0.1, le=1.0, description="Healthy radiator effectiveness [-]")
    cooling_inlet_area_m2: float = Field(0.12, gt=0.01, lt=0.3, description="Total effective sidepod inlet area [m^2]")
    cooling_duct_velocity_ratio: float = Field(0.35, gt=0.05, lt=1.0, description="Duct velocity / freestream velocity [-]")
    coolant_thermal_mass_j_per_k: float = Field(60000.0, gt=1000, description="Lumped coolant/engine thermal mass [J/K]")
    coolant_limit_c: float = Field(120.0, gt=80, lt=160, description="Coolant temperature at which power derate begins [degC]")
    coolant_derate_span_c: float = Field(20.0, gt=1, lt=60, description="Span over which power derates to 50% [degC]")

    # --- Tyres ------------------------------------------------------------
    tyre_mu_peak: float = Field(1.70, gt=0.8, lt=2.5, description="Peak tyre friction coefficient in window [-]")
    tyre_optimal_temp_c: float = Field(100.0, gt=50, lt=140, description="Centre of tyre operating window [degC]")
    tyre_window_halfwidth_c: float = Field(25.0, gt=5, lt=60, description="Temperature half-width of tyre window [degC]")
    tyre_surface_temp_c: float = Field(98.0, gt=20, lt=160, description="Nominal tyre surface temperature [degC]")
    tyre_pressure_psi: float = Field(22.0, gt=10, lt=35, description="Nominal hot tyre pressure [psi]")
    tyre_wear_per_lap: float = Field(0.018, ge=0, lt=0.2, description="Healthy tread wear per lap (fraction of life) [-]")

    # --- Brakes -----------------------------------------------------------
    front_brake_bias: float = Field(0.58, gt=0.3, lt=0.8, description="Fraction of brake torque on the front axle [-]")
    brake_disc_mass_kg: float = Field(1.2, gt=0.3, lt=5, description="Mass of one carbon disc [kg]")
    brake_disc_specific_heat: float = Field(1200.0, gt=400, lt=2500, description="Effective specific heat of disc material at temperature [J/kg/K]")
    brake_cooling_coeff: float = Field(0.9, gt=0.05, lt=10, description="Disc convective cooling coefficient per m/s of airspeed [W/K/(m/s)]")
    brake_cooling_static: float = Field(3.0, ge=0, lt=50, description="Disc cooling at zero speed [W/K]")
    brake_optimal_min_c: float = Field(350.0, description="Lower bound of brake friction window [degC]")
    brake_optimal_max_c: float = Field(1000.0, description="Upper bound of brake friction window [degC]")

    # --- Simulation ---------------------------------------------------------
    stint_laps: int = Field(30, ge=1, le=80, description="Laps evaluated for degradation curves")


# Fraction of the healthy whole-car downforce (ClA) generated by each aero
# surface, and the longitudinal centre-of-pressure position of that load,
# measured rearwards from the front axle [m]. Shares sum to 1.0.
AERO_DOWNFORCE_SHARE: dict[str, tuple[float, float]] = {
    "front_wing": (0.26, -0.75),
    "floor": (0.20, 1.70),
    "venturi_tunnels": (0.19, 1.95),
    "diffuser": (0.12, 3.85),
    "rear_wing": (0.20, 4.10),
    "drs": (0.03, 4.15),
}

# Fraction of the healthy whole-car drag (CdA) attributed to each component.
# Shares sum to 1.0. Rotating wheels and wings dominate open-wheel drag.
DRAG_SHARE: dict[str, float] = {
    "front_wing": 0.08,
    "nose_cone": 0.03,
    "front_suspension": 0.04,
    "front_tyres": 0.15,
    "front_brakes": 0.02,
    "monocoque": 0.04,
    "halo": 0.02,
    "cockpit": 0.02,
    "sidepods": 0.07,
    "radiators": 0.06,
    "floor": 0.04,
    "venturi_tunnels": 0.02,
    "diffuser": 0.04,
    "rear_suspension": 0.03,
    "rear_tyres": 0.14,
    "rear_brakes": 0.02,
    "rear_wing": 0.14,
    "drs": 0.03,
    "power_unit": 0.00,
    "rear_crash_structure": 0.01,
}

assert abs(sum(v[0] for v in AERO_DOWNFORCE_SHARE.values()) - 1.0) < 1e-9
assert abs(sum(DRAG_SHARE.values()) - 1.0) < 1e-9
