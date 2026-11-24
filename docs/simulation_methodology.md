# Simulation methodology

> **Every result in ApexVision is MODEL-ESTIMATED.** It comes from a simplified engineering model.
> It is **not CFD**, **not FEA**, and it has **not been validated against any real car**. Use it to understand the
> *direction and relative size* of the effect of damage. Do not use it to predict a real car's lap time.

The model has to be fast enough to rerun every time a slider moves (about 0.1 s for the core model and about 0.8 s with all
dashboard curves). It must also be transparent: every coefficient is a named, editable assumption. The source is in
`backend/app/simulation/`:

| Module | Responsibility |
|---|---|
| `assumptions.py` | All tunable inputs (`VehicleAssumptions`) plus per-component downforce and drag share tables |
| `damage.py` | Turns each damage into physical modifiers (per-component transfer functions) |
| `aerodynamics.py` | Component-resolved lumped aero coefficients, ride-height sensitivity, DRS, balance |
| `tyres.py` | Empirical grip: temperature window, wear, puncture, geometry |
| `thermal.py` | Lumped-capacitance brake disc and coolant loop models, brake fade, power derate |
| `track.py` | Invented 5.18 km test circuit |
| `lapsim.py` | Quasi-steady point-mass lap simulation |
| `vehicle.py` | Orchestration, thermal-performance coupling, summaries, curves, severity sweeps |

## 1. Healthy baseline (default assumptions)

| Quantity | Model value |
|---|---|
| Mass | 800 kg (45% front) |
| Cd·A / Cl·A | 0.88 × 1.5 = 1.32 m² / 2.70 × 1.5 = 4.05 m² |
| Downforce / drag at 250 km/h | ≈ 11.96 kN / 3.90 kN (L/D ≈ 3.07) |
| Aero balance | 46.6% front |
| Wheel power | 750 kW × 0.92 drivetrain efficiency |
| Lap time, test circuit | ≈ 73.9 s |
| Top speed (DRS closed / open) | ≈ 335 / 342 km/h |

These values come from generic, order-of-magnitude assumptions for an open-wheel ground-effect car. They are not data
from any team. Every value can be changed in the **Assumptions** tab or through the `assumptions` field of any simulation request.

## 2. Aerodynamics

```
F_drag      = ½ ρ v² · Cd · A_frontal
F_downforce = ½ ρ v² · Cl · A_reference
```

The whole-car ClA and CdA are split between components using two share tables:

| Surface | Downforce share | Centre of pressure x (m behind front axle) |
|---|---|---|
| Front wing | 26% | −0.75 |
| Floor | 20% | 1.70 |
| Venturi tunnels | 19% | 1.95 |
| Diffuser | 12% | 3.85 |
| Rear wing | 20% | 4.10 |
| DRS flap | 3% | 4.15 |

The drag shares add up to 100% over 19 components. Rotating wheels (29% for the two axles) and the rear wing (14%) are the largest.

The full table is in `assumptions.DRAG_SHARE` and in [component_specifications.md](component_specifications.md).

**Damage** multiplies the share of each surface it affects (`cl_factor[surface]` and `cd_factor[component]`). There is
no generic "x% slower" penalty. See §4.

**Ride height.** Underfloor shares (floor, tunnels and diffuser) are multiplied by

```
f_rh = clip(1 − k·Δh², 0.3, 1),   Δh = h_eff − h_opt,   k = sensitivity × (1.5 if Δh < 0 else 1)
h_eff = h_static + ½(Δh_front + Δh_rear)
```

Running below the optimum is penalised 1.5× harder. This approximates flow choking and stall close to the ground.
Suspension damage and punctures lower the effective ride height.

**DRS.** The rear-wing and DRS shares are reduced by `drs_rear_wing_cl_reduction × flap` for Cl and by
`drs_rear_wing_cd_reduction × flap` for Cd. `flap = max(open × available, forced_open)`. *Stuck closed* reduces
`available`. *Stuck open* sets `forced_open`, so the flap stays open in corners too.

**Balance.** Each surface's load is split between the axles by its centre-of-pressure position x along the wheelbase L:
the rear axle carries x/L and the front axle carries 1 − x/L. Surfaces ahead of the front axle (x < 0) put more than their own
load on the front axle and unload the rear.

## 3. Tyres (`tyres.py`)

```
μ = μ_peak · f_temp(T) · f_wear(w) · f_puncture(p) · f_geometry
f_temp     = clip(1 − 0.12·((T − T_opt)/half_width)², 0.55, 1)
f_wear     = clip(1 − 0.15w − 0.8·max(0, w − 0.7)², 0.5, 1)     (the wear "cliff" begins at 70%)
f_puncture = 1 − 0.75p
```

Tyre temperature is the nominal surface temperature plus 0.4 × (track temperature − 40 °C), plus any damage-induced offset.
An axle overloaded by a balance shift gets a further 1.2 °C per balance point; this represents sliding.

Wear rate per lap rises with over-temperature, geometry loss and puncture.
This is a smooth empirical shape chosen to reproduce the known qualitative behaviour (operating window, wear cliff,
deflation). **It is not a fitted Pacejka model.**

## 4. Damage transfer functions (`damage.py`)

The severity `d` runs from 0 to 1 (the slider value / 100). Severity levels: 0 healthy, up to 20% minor, up to 45% moderate,
up to 75% severe, above 75% critical.

| Damage | Physical modifiers (multiplicative unless stated) |
|---|---|
| Front wing endplate | FW Cl × (1 − 0.30d), floor × (1 − 0.08d), tunnels × (1 − 0.06d), FW Cd × (1 + 0.25d) |
| Front wing element failure | FW Cl × (1 − 0.80d), floor × (1 − 0.04d), FW Cd × (1 − 0.35d), because less load means less induced drag |
| Nose | FW Cl × (1 − 0.25d) (wing misalignment), nose Cd × (1 + 0.6d), structural integrity 1 − d |
| Floor edge | floor Cl × (1 − 0.55d^0.8), tunnels × (1 − 0.25d), diffuser × (1 − 0.20d), floor Cd × (1 + 0.6d) |
| Venturi fences | tunnels × (1 − 0.5d), diffuser × (1 − 0.1d), Cd × (1 + 0.4d) |
| Diffuser | diffuser × (1 − 0.7d), tunnels × (1 − 0.15d), floor × (1 − 0.05d), Cd × (1 + 0.3d) |
| Rear wing | RW and DRS Cl × (1 − 0.6d), RW Cd × (1 − 0.2d) |
| DRS stuck open / closed | flap forced open fraction d / DRS effect available × (1 − d) |
| Suspension (front/rear) | ride height −15d mm on that axle, axle grip × (1 − 0.22d), Cd × (1 + 0.5d) |
| Puncture | puncture p = d (grip and pressure), ride height −20d mm, tyre Cd × (1 + 0.3d) |
| Tyre overheating | +45d °C tyre temperature |
| Brake overheating | disc cooling × (1 − 0.85d) (blocked or damaged duct) |
| Sidepod inlet | inlet area × (1 − 0.6d), sidepod Cd × (1 + 0.8d) |
| Cooling system failure | radiator effectiveness × (1 − 0.85d) |
| Engine overheating | heat rejected to coolant × (1 + d) |
| Power loss | power × (1 − 0.4d) |
| Monocoque, halo, cockpit, rear crash structure | structural integrity 1 − d, Cd × (1 + 0.3d). Rear crash structure also gives RW Cl × (1 − 0.05d), from mounting misalignment |

These coefficients are **assumptions** that represent the direction and relative size of well-known effects.
Each simulation returns a plain-language `mechanism` for every active damage, and the UI shows it.

**Structural damage** is a scalar *integrity* indicator. It is **not** a structural, deformation or fracture model. The app
recommends retirement when integrity drops below 25%, when a puncture is at or above 75%, or when the power derate reaches its 50% floor.

## 5. Thermal models (`thermal.py`)

Both models are lumped-capacitance ODEs. They are solved **exactly** for piecewise-constant inputs along the lap trace,
using a vectorised closed form (`T_{i+1} = T_eq + (T_i − T_eq)·e^{−hΔt/C}`).

**Brake disc** (per disc):

```
m c dT/dt = 0.9 · P_brake,axle / 2 − h(v)(T − T_amb) − εσA(T⁴ − T_amb⁴)
h(v) = (h_0 + k_v·v) × duct_factor
```

The radiation term is linearised about the previous iterate. The disc is run for four laps from 300 °C.
The friction factor is 1 inside the 350–1000 °C window, falls to 0.75 when cold, and fades by 0.12% per °C above the window
(floor 0.4). **On the default car, brake overheating mainly raises disc temperature and the oxidation-wear index
(exponential, 1.0 at 700 °C). Lap time changes only once the energy-weighted disc temperature leaves the friction window.**
This is intended and physically sensible, so do not expect a large lap-time loss from moderate brake damage.

**Coolant loop:**

```
C dT/dt = f_hc · P_delivered − ε · ṁ(v) · c_p,air · (T − T_amb),   ṁ = ρ · v · duct_ratio · A_inlet
```

The loop is marched for six laps from 90 °C. Above `coolant_limit_c` (120 °C) power is derated linearly, reaching 50% at limit + span.

**Coupling.** Brake fade feeds the braking force (two fixed-point passes). The power derate feeds back into lap power and
therefore heat. The equilibrium derate `x = derate(x)` is found by bisection.

## 6. Lap simulation (`lapsim.py`)

The circuit is an **invented** layout, the "ApexVision Test Circuit". It is 5.18 km long with 8 constant-radius corners
of radius 22–350 m and two DRS straights, discretised at 4 m. It is not a real circuit.

1. **Corner limit**, for each axle and with downforce:
   `v² = μg / (1/R − μ·½ρ·ClA_axle/(w·m))`. The weaker axle sets the limit, so aero balance matters. Speed is capped at 120 m/s.
2. **Forward pass:** acceleration is limited by power (P/v) and rear traction, minus drag and rolling resistance.
3. **Backward pass:** deceleration is limited by tyres and brake bias (`min(μ_f·N_f/bias, μ_r·N_r/(1 − bias))`) and
   multiplied by the brake friction factor.
4. Speed is min(limit, forward, backward). Each pass runs twice so the start speed is periodic. Lap time = Σ dx / v̄.

Top speed comes from a Brent root of P = F_res·v. Corner speeds are reported for R = 25, 100 and 250 m. A 250 m corner is
not grip-limited on the default car, so it reports top speed. Braking distance is integrated from 300 to 100 km/h.

**Known simplifications:**
- no combined slip (friction circle)
- no load-transfer dynamics or suspension kinematics
- no gears
- constant mass and fuel
- tyre temperature held constant within a lap
- a single point mass
- no wake from other cars or yaw

## 7. Outputs and indices

| Output | Definition |
|---|---|
| Component health | 100 − severity, for each damaged component |
| Overall health | Mean health of all 20 components |
| Performance index | Healthy lap time / current lap time × 100 |
| Severity sweep | The focus damage re-simulated at 0–100% (lap time and aero) |
| Stint curves | Lap time and grip re-simulated at 7 points over `stint_laps` |

Illustrative results with default assumptions (lap-time delta against the healthy car, model-estimated):

| Scenario | Δ lap time | Front balance |
|---|---|---|
| Front wing element failure 65% | +3.1 s | 46.6% → 34.9% (understeer) |
| Floor damage 50% | +1.1 s | 46.9% |
| Cooling failure 60% | +6.1 s (power derate) | unchanged |
| Rear tyre puncture 90% | +65.8 s (retire recommended) | 47.2% |

## 8. Limits of validity

- The relative sizes of the effects follow general, publicly known behaviour of ground-effect cars. Absolute values
  depend entirely on the assumptions.
- **No CFD, wind-tunnel, FEA or real telemetry data was used, and there is no validation against any real car.**
- The 3D damage visuals are a **kinematic representation only**: parts rotate, translate, scale, tint, glow and detach.
  They do not come from a deformation or fracture model (see [3d_asset_guide.md](3d_asset_guide.md)).
- The AI assistant may only report numbers returned by these models. Every number in an answer is checked against tool
  outputs, and any number that cannot be traced is flagged in the UI.

## 9. Testing

`backend/tests/` covers:
- monotonicity: more damage never improves the affected metrics
- the direction of the balance shift for front versus rear damage
- share tables summing to 1
- drag and downforce equations scaling with v²
- plausible baseline ranges
- bounded brake-temperature and coolant responses
- retirement on puncture
- every preset scenario running
- assumption changes propagating to results
- severity classification
- API contracts
- AI tool registration and numeric verification
