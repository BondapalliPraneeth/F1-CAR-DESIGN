"""Engineering catalogue for the 20 selectable components of the ApexVision car.

Descriptions are general, publicly documented engineering knowledge about
open-wheel racing cars. Numerical parameters are the *model assumptions* used
by the simulation (see app/simulation/assumptions.py) and are labelled as such;
they are not measured values from any real car.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DamageType:
    id: str
    label: str
    description: str
    visual: str  # what the 3D viewer actually does for this damage type


@dataclass(frozen=True)
class Component:
    id: str
    name: str
    category: str  # aerodynamic | mechanical | structural | thermal | powertrain
    analysis_panel: str  # which component-specific panel the UI renders
    position: str
    purpose: str
    primary_function: str
    construction: str
    performance_contribution: str
    failure_modes: list[str]
    damage_susceptibility: str  # low | medium | high
    susceptibility_note: str
    engineering_explanation: str
    damage_types: list[DamageType]
    related: list[str] = field(default_factory=list)


TINT = "Tinted by severity (amber to red)"


def _dt(id: str, label: str, description: str, visual: str) -> DamageType:
    return DamageType(id, label, description, visual)


COMPONENTS: list[Component] = [
    Component(
        id="front_wing",
        name="Front Wing",
        category="aerodynamic",
        analysis_panel="front_wing",
        position="Ahead of the front axle, mounted beneath the nose",
        purpose="Generates front-axle downforce and conditions the airflow for everything downstream.",
        primary_function="Front downforce generation and wake management around the front tyres.",
        construction="Typically a multi-element carbon-fibre composite structure with endplates.",
        performance_contribution="Model share: 26% of total downforce, 8% of total drag. Largest single lever on aerodynamic balance.",
        failure_modes=["Endplate detachment after wheel-to-wing contact", "Flap or element failure", "Pylon / mounting failure", "Flutter under load"],
        damage_susceptibility="high",
        susceptibility_note="Most exposed component on the car; first contact point in lap-one incidents.",
        engineering_explanation=(
            "The front wing operates in clean air and in ground effect. Losing an element reduces front "
            "load directly, moving the aerodynamic balance rearwards and causing understeer. Endplate "
            "damage mainly degrades outwash control around the front tyres, so tyre wake ends up in the "
            "floor inlet and the floor also loses load."
        ),
        damage_types=[
            _dt("endplate_damage", "Endplate damage", "Partial loss of an endplate: reduced wing load, more drag, tyre wake reaches the floor.", "Left endplate rotates outward, drops and detaches at critical severity. " + TINT),
            _dt("element_failure", "Partial wing failure", "Failure of the upper flap elements: large front-load loss.", "Upper flaps droop and twist; detach at critical severity. " + TINT),
        ],
        related=["nose_cone", "floor", "front_tyres"],
    ),
    Component(
        id="nose_cone",
        name="Nose Cone",
        category="structural",
        analysis_panel="structural",
        position="Front of the monocoque, carries the front wing",
        purpose="Front impact structure and the mounting for the front wing.",
        primary_function="Absorbs frontal impact energy; positions the front wing.",
        construction="Typically a crushable carbon-fibre composite impact structure.",
        performance_contribution="Model share: 3% of drag. Damage also misaligns the front wing (front-load loss).",
        failure_modes=["Crush after frontal impact", "Wing-pylon cracking", "Misalignment of the front wing"],
        damage_susceptibility="high",
        susceptibility_note="Directly exposed to rear-end contacts with other cars.",
        engineering_explanation="A damaged nose changes the angle and height of the front wing it carries, so it couples into front downforce even though the nose itself produces little load.",
        damage_types=[_dt("nose_damage", "Nose damage", "Crushed tip and misaligned wing mounting.", "Nose shortens (crush) and tilts down. " + TINT)],
        related=["front_wing", "monocoque"],
    ),
    Component(
        id="front_suspension",
        name="Front Suspension",
        category="mechanical",
        analysis_panel="suspension",
        position="Between the monocoque and the front uprights",
        purpose="Controls front wheel motion, ride height and tyre contact patch.",
        primary_function="Wheel location, camber/toe control and aero platform control.",
        construction="Typically carbon-fibre wishbones and push/pull rods with metallic uprights.",
        performance_contribution="Sets front ride height (floor performance) and front mechanical grip. Model share: 4% of drag.",
        failure_modes=["Bent wishbone or track rod", "Pushrod failure (ride height collapse)", "Toe/camber misalignment"],
        damage_susceptibility="medium",
        susceptibility_note="Exposed to kerb strikes and wheel-to-wheel contact.",
        engineering_explanation="Bent members change camber and toe, reducing the usable contact patch. A failed pushrod drops the ride height, which moves the floor away from its optimum and can stall the underfloor flow.",
        damage_types=[_dt("suspension_damage", "Suspension damage", "Bent members: camber/toe error and ride-height drop on the front axle.", "Left front corner drops and the wheel cambers over. " + TINT)],
        related=["front_tyres", "floor", "monocoque"],
    ),
    Component(
        id="front_tyres",
        name="Front Tyres",
        category="mechanical",
        analysis_panel="tyres",
        position="Front axle",
        purpose="Transfer steering, braking and cornering forces to the track.",
        primary_function="Front-axle grip.",
        construction="Pneumatic radial racing tyres on forged wheel rims.",
        performance_contribution="Front-axle grip limit; rotating wheels are a major drag source (model share 15%).",
        failure_modes=["Puncture / deflation", "Overheating (out of window)", "Graining", "Flat-spotting"],
        damage_susceptibility="high",
        susceptibility_note="Debris, lock-ups and contact can all cause failures.",
        engineering_explanation="Tyre friction peaks inside a temperature window. Outside it the rubber either does not generate enough hysteresis (cold) or loses structural integrity (hot). A puncture removes most of the axle's lateral capacity.",
        damage_types=[
            _dt("puncture", "Tyre puncture", "Loss of inflation pressure on the left-front tyre.", "Tyre flattens vertically in proportion to pressure loss. " + TINT),
            _dt("overheating", "Tyre overheating", "Surface temperature driven above the operating window.", "Tyre glows with a heat colour map."),
        ],
        related=["front_suspension", "front_brakes"],
    ),
    Component(
        id="front_brakes",
        name="Front Brake Assembly",
        category="thermal",
        analysis_panel="brakes",
        position="Inside the front wheel rims",
        purpose="Convert kinetic energy to heat to slow the car; front axle carries most brake torque.",
        primary_function="Deceleration and braking stability.",
        construction="Typically carbon-carbon discs and pads with multi-piston calipers and cooling ducts.",
        performance_contribution="Brake bias and friction window set braking performance. Model share: 2% of drag (ducts).",
        failure_modes=["Overheating from blocked cooling ducts", "Excessive oxidation wear", "Caliper failure"],
        damage_susceptibility="medium",
        susceptibility_note="Debris (e.g. tear-offs) can block brake ducts.",
        engineering_explanation="Carbon brakes need a high temperature to work. Above their window they oxidise rapidly and friction fades. Blocking the duct removes convective cooling, so the disc temperature rises lap after lap.",
        damage_types=[_dt("brake_overheating", "Brake overheating", "Cooling duct blockage reducing convective cooling.", "Discs glow with a heat colour map proportional to severity.")],
        related=["front_tyres", "front_suspension"],
    ),
    Component(
        id="monocoque",
        name="Monocoque",
        category="structural",
        analysis_panel="structural",
        position="Central survival cell",
        purpose="Safety cell for the driver and primary structural backbone.",
        primary_function="Carries suspension, power-unit and impact loads; protects the driver.",
        construction="Typically a carbon-fibre / honeycomb composite shell.",
        performance_contribution="Structural stiffness; model share 4% of drag.",
        failure_modes=["Delamination", "Penetration", "Mounting point cracking"],
        damage_susceptibility="low",
        susceptibility_note="Designed to survive severe impacts.",
        engineering_explanation="The monocoque is not modelled as a performance device. Damage is reported as a structural-integrity reduction and, above the critical threshold, a model rule recommends retirement.",
        damage_types=[_dt("structural_damage", "Structural damage", "Delamination or cracking of the survival cell.", TINT + "; no deformation model.")],
        related=["halo", "cockpit", "nose_cone"],
    ),
    Component(
        id="halo",
        name="Halo",
        category="structural",
        analysis_panel="structural",
        position="Above the cockpit opening",
        purpose="Driver head protection from large debris and car-to-car contact.",
        primary_function="Head-protection structure.",
        construction="Typically a titanium tubular structure with an aerodynamic fairing.",
        performance_contribution="Model share: 2% of drag.",
        failure_modes=["Mounting failure", "Fairing damage"],
        damage_susceptibility="low",
        susceptibility_note="Very high strength; mostly fairing damage in practice.",
        engineering_explanation="Damage to the halo is treated as a safety-integrity issue. It has a minor drag effect only.",
        damage_types=[_dt("structural_damage", "Structural damage", "Fairing or mount damage.", TINT + "; no deformation model.")],
        related=["cockpit", "monocoque"],
    ),
    Component(
        id="cockpit",
        name="Cockpit",
        category="structural",
        analysis_panel="structural",
        position="Within the monocoque, behind the front bulkhead",
        purpose="Houses the driver, seat, steering wheel and controls.",
        primary_function="Driver interface and containment.",
        construction="Moulded seat and composite cockpit surround.",
        performance_contribution="Model share: 2% of drag.",
        failure_modes=["Cockpit-surround damage", "Control system faults"],
        damage_susceptibility="low",
        susceptibility_note="Protected by the monocoque and halo.",
        engineering_explanation="Cockpit damage is reported as a safety-integrity reduction; control-system faults are outside the scope of this model.",
        damage_types=[_dt("structural_damage", "Surround damage", "Damage to the cockpit surround.", TINT + "; no deformation model.")],
        related=["halo", "monocoque"],
    ),
    Component(
        id="sidepods",
        name="Sidepods",
        category="thermal",
        analysis_panel="cooling",
        position="Either side of the monocoque, ahead of the rear wheels",
        purpose="House the radiators, feed cooling air and shape flow to the rear of the car.",
        primary_function="Cooling inlet and bodywork flow management.",
        construction="Typically thin carbon-fibre bodywork panels.",
        performance_contribution="Inlet area sets cooling mass flow; model share 7% of drag.",
        failure_modes=["Inlet damage / blockage", "Panel detachment"],
        damage_susceptibility="medium",
        susceptibility_note="Exposed to side impacts and debris.",
        engineering_explanation="Damage that deforms the inlet reduces cooling air mass flow, raising coolant temperature. Torn bodywork also adds parasitic drag.",
        damage_types=[_dt("inlet_damage", "Sidepod inlet damage", "Deformed or blocked left inlet.", "Left sidepod is crushed inward. " + TINT)],
        related=["radiators", "power_unit"],
    ),
    Component(
        id="radiators",
        name="Radiators & Cooling System",
        category="thermal",
        analysis_panel="cooling",
        position="Inside the sidepods",
        purpose="Reject power-unit heat to the airflow.",
        primary_function="Coolant and oil heat exchange.",
        construction="Typically aluminium heat-exchanger cores.",
        performance_contribution="Cooling drag (model share 6%) and coolant temperature control.",
        failure_modes=["Core puncture / coolant leak", "Core blockage", "Pump failure"],
        damage_susceptibility="medium",
        susceptibility_note="Debris through the inlet can puncture cores.",
        engineering_explanation="Radiator effectiveness and air mass flow together set heat rejection. When rejection drops below the engine heat input, coolant temperature climbs and the power unit must derate to protect itself.",
        damage_types=[_dt("cooling_failure", "Cooling system failure", "Loss of radiator effectiveness (leak or blocked core).", "Radiator cores glow with a heat colour map. " + TINT)],
        related=["sidepods", "power_unit"],
    ),
    Component(
        id="floor",
        name="Floor",
        category="aerodynamic",
        analysis_panel="floor",
        position="Underside of the car, between the axles",
        purpose="Main ground-effect surface; seals the underfloor flow.",
        primary_function="Underfloor downforce with low drag cost.",
        construction="Typically carbon-fibre composite with a sacrificial wear plank.",
        performance_contribution="Model share: 20% of downforce, 4% of drag. Highly sensitive to ride height.",
        failure_modes=["Floor-edge damage (seal loss)", "Plank wear", "Torn floor after kerb strike"],
        damage_susceptibility="high",
        susceptibility_note="Kerbs and debris frequently damage floor edges.",
        engineering_explanation="The floor accelerates air underneath the car, lowering pressure. The edges act as an aerodynamic seal. When an edge is damaged, high-pressure air leaks in and all underfloor devices (tunnels and diffuser) lose load.",
        damage_types=[_dt("floor_damage", "Floor edge damage", "Torn left floor edge, breaking the underfloor seal.", "Left floor edge bends downward and detaches at critical severity. " + TINT)],
        related=["venturi_tunnels", "diffuser", "front_suspension", "rear_suspension"],
    ),
    Component(
        id="venturi_tunnels",
        name="Venturi Tunnels",
        category="aerodynamic",
        analysis_panel="floor",
        position="Underfloor, either side of the plank",
        purpose="Shaped underfloor channels that accelerate air to generate ground-effect suction.",
        primary_function="Ground-effect downforce.",
        construction="Typically carbon-fibre fences and tunnel roof.",
        performance_contribution="Model share: 19% of downforce, 2% of drag.",
        failure_modes=["Fence damage", "Tunnel-inlet damage", "Flow stall at very low ride height"],
        damage_susceptibility="medium",
        susceptibility_note="Inlet fences are exposed to debris.",
        engineering_explanation="Air accelerated through a converging-diverging tunnel drops in pressure (Bernoulli). Inlet fences manage vortices that keep the tunnel flow attached; damaging them reduces suction.",
        damage_types=[_dt("tunnel_damage", "Tunnel fence damage", "Damaged inlet fences on the left side.", "Left fences droop and twist. " + TINT)],
        related=["floor", "diffuser"],
    ),
    Component(
        id="diffuser",
        name="Diffuser",
        category="aerodynamic",
        analysis_panel="floor",
        position="Rear of the floor, beneath the crash structure",
        purpose="Expands the underfloor flow back to ambient pressure, sustaining suction upstream.",
        primary_function="Underfloor pressure recovery and rear downforce.",
        construction="Typically carbon-fibre ramp with strakes.",
        performance_contribution="Model share: 12% of downforce, 4% of drag.",
        failure_modes=["Strake damage", "Ramp cracking after rear contact"],
        damage_susceptibility="medium",
        susceptibility_note="Exposed in rear-end contacts.",
        engineering_explanation="The diffuser lets the fast underfloor flow decelerate gradually. Damaging it raises underfloor pressure, which also reduces load from the tunnels upstream.",
        damage_types=[_dt("diffuser_damage", "Diffuser damage", "Damaged strakes and ramp.", "Diffuser ramp droops. " + TINT)],
        related=["floor", "venturi_tunnels", "rear_crash_structure"],
    ),
    Component(
        id="rear_suspension",
        name="Rear Suspension",
        category="mechanical",
        analysis_panel="suspension",
        position="Between the gearbox and the rear uprights",
        purpose="Controls rear wheel motion, rear ride height and traction.",
        primary_function="Wheel location and rear aero platform control.",
        construction="Typically carbon-fibre wishbones and pull/push rods.",
        performance_contribution="Rear ride height (diffuser sensitivity) and traction. Model share: 3% of drag.",
        failure_modes=["Bent members", "Toe-link failure", "Ride-height collapse"],
        damage_susceptibility="medium",
        susceptibility_note="Exposed to kerb strikes.",
        engineering_explanation="Rear geometry errors reduce traction and lateral grip. A rear ride-height drop changes floor rake and pushes the underfloor away from its optimum.",
        damage_types=[_dt("suspension_damage", "Suspension damage", "Bent members: camber/toe error and ride-height drop on the rear axle.", "Left rear corner drops and the wheel cambers over. " + TINT)],
        related=["rear_tyres", "floor", "diffuser"],
    ),
    Component(
        id="rear_tyres",
        name="Rear Tyres",
        category="mechanical",
        analysis_panel="tyres",
        position="Rear axle",
        purpose="Transmit drive torque and rear lateral force.",
        primary_function="Traction and rear-axle grip.",
        construction="Pneumatic radial racing tyres on forged wheel rims.",
        performance_contribution="Traction and rear grip limit; model share 14% of drag.",
        failure_modes=["Puncture", "Overheating from wheelspin", "Blistering"],
        damage_susceptibility="high",
        susceptibility_note="Exposed to debris and contact.",
        engineering_explanation="Rear tyres carry the drive torque as well as lateral load, so overheating and wear show up first in traction zones.",
        damage_types=[
            _dt("puncture", "Tyre puncture", "Loss of inflation pressure on the left-rear tyre.", "Tyre flattens vertically in proportion to pressure loss. " + TINT),
            _dt("overheating", "Tyre overheating", "Surface temperature driven above the operating window.", "Tyre glows with a heat colour map."),
        ],
        related=["rear_suspension", "rear_brakes", "power_unit"],
    ),
    Component(
        id="rear_brakes",
        name="Rear Brakes",
        category="thermal",
        analysis_panel="brakes",
        position="Inside the rear wheel rims",
        purpose="Rear-axle braking, assisted by energy recovery in real hybrid cars (not modelled).",
        primary_function="Rear deceleration and stability.",
        construction="Typically carbon-carbon discs and pads.",
        performance_contribution="Carries (1 - brake bias) of brake torque. Model share: 2% of drag.",
        failure_modes=["Overheating", "Wear", "Brake-by-wire faults (not modelled)"],
        damage_susceptibility="medium",
        susceptibility_note="Duct blockage and debris.",
        engineering_explanation="Same thermal behaviour as the front brakes but with less energy per stop because of the forward brake bias.",
        damage_types=[_dt("brake_overheating", "Brake overheating", "Cooling duct blockage reducing convective cooling.", "Discs glow with a heat colour map proportional to severity.")],
        related=["rear_tyres"],
    ),
    Component(
        id="rear_wing",
        name="Rear Wing",
        category="aerodynamic",
        analysis_panel="rear_wing",
        position="Above and behind the rear axle",
        purpose="Generates rear downforce; holds the DRS flap.",
        primary_function="Rear-axle downforce and stability.",
        construction="Typically a carbon-fibre main plane, beam wing and endplates.",
        performance_contribution="Model share: 20% of downforce, 14% of drag.",
        failure_modes=["Endplate damage", "Main-plane cracking", "Mounting failure"],
        damage_susceptibility="medium",
        susceptibility_note="Mostly exposed in rear-end contacts and spins.",
        engineering_explanation="Rear-wing load is high-drag downforce. Losing it moves the balance forward (oversteer) and cuts drag a little: the car gets faster on the straights but much slower in high-speed corners.",
        damage_types=[_dt("wing_damage", "Rear wing damage", "Damaged main plane and right endplate.", "Main plane twists, right endplate tilts outward. " + TINT)],
        related=["drs", "diffuser", "rear_crash_structure"],
    ),
    Component(
        id="drs",
        name="DRS Mechanism",
        category="aerodynamic",
        analysis_panel="rear_wing",
        position="Upper rear-wing flap and actuator",
        purpose="Drag reduction system: opens the upper flap on straights to cut drag.",
        primary_function="Straight-line drag reduction.",
        construction="Typically a hydraulic actuator and a hinged carbon flap.",
        performance_contribution="Model share: 3% of downforce, 3% of drag; opening removes a configurable fraction of rear-wing load and drag.",
        failure_modes=["Stuck closed (no straight-line gain)", "Stuck open (loss of rear load in corners)"],
        damage_susceptibility="low",
        susceptibility_note="Actuator faults are rare but very consequential.",
        engineering_explanation="Opening the flap stalls the upper element so rear-wing drag and load fall together. If it fails open, the car loses rear downforce in corners. If it fails closed, the straight-line gain is lost.",
        damage_types=[
            _dt("stuck_open", "DRS stuck open", "Flap fails partially or fully open in corners.", "Flap visibly rotates open in proportion to severity."),
            _dt("stuck_closed", "DRS stuck closed", "Flap cannot open; straight-line gain is lost.", "Flap is forced closed. " + TINT),
        ],
        related=["rear_wing"],
    ),
    Component(
        id="power_unit",
        name="Engine & Power Unit",
        category="powertrain",
        analysis_panel="power_unit",
        position="Behind the monocoque, ahead of the gearbox",
        purpose="Generates propulsive power.",
        primary_function="Combustion engine plus hybrid power delivery (modelled as one lumped power source).",
        construction="Typically a turbocharged internal-combustion engine with hybrid energy recovery.",
        performance_contribution="Configurable peak wheel power (model assumption 750 kW); heat rejection drives cooling demand.",
        failure_modes=["Overheating", "Loss of hybrid deployment", "Mechanical failure"],
        damage_susceptibility="low",
        susceptibility_note="Protected inside the car; usually fails thermally or mechanically.",
        engineering_explanation="Delivered power is limited by thermal state. When coolant temperature exceeds the limit, the model derates power linearly, as real control systems protect the engine.",
        damage_types=[
            _dt("engine_overheating", "Engine overheating", "Internal fault increasing heat to coolant.", "Engine block glows with a heat colour map."),
            _dt("power_loss", "Power loss", "Loss of deliverable power (e.g. hybrid fault).", TINT + "; no deformation model."),
        ],
        related=["radiators", "sidepods", "rear_tyres"],
    ),
    Component(
        id="rear_crash_structure",
        name="Rear Crash Structure",
        category="structural",
        analysis_panel="structural",
        position="Behind the gearbox",
        purpose="Rear impact energy absorption; mounts the rain light and supports the wing pylon area.",
        primary_function="Rear impact protection.",
        construction="Typically a crushable carbon-fibre composite structure.",
        performance_contribution="Model share: 1% of drag; supports the rear-wing pylon area.",
        failure_modes=["Crush after rear impact", "Mounting cracks"],
        damage_susceptibility="medium",
        susceptibility_note="Exposed in rear-end contacts.",
        engineering_explanation="Primarily a safety structure. Damage is reported as reduced structural integrity, with a small coupling to rear-wing stability.",
        damage_types=[_dt("structural_damage", "Structural damage", "Crush or cracking after rear contact.", "Structure shortens (crush). " + TINT)],
        related=["rear_wing", "diffuser"],
    ),
]

COMPONENTS_BY_ID: dict[str, Component] = {c.id: c for c in COMPONENTS}

assert len(COMPONENTS) == 20, "ApexVision exposes exactly 20 engineering components"


def get_component(component_id: str) -> Component | None:
    return COMPONENTS_BY_ID.get(component_id)


def valid_damage_types(component_id: str) -> list[str]:
    c = COMPONENTS_BY_ID.get(component_id)
    return [d.id for d in c.damage_types] if c else []


# Ten preset scenarios from the specification, plus a combined lap-one incident.
DAMAGE_SCENARIOS: list[dict] = [
    {"id": "fw_endplate", "name": "Front wing endplate damage", "damages": [{"component_id": "front_wing", "damage_type": "endplate_damage", "severity": 40}]},
    {"id": "fw_partial", "name": "Front wing partial failure", "damages": [{"component_id": "front_wing", "damage_type": "element_failure", "severity": 65}]},
    {"id": "floor", "name": "Floor damage", "damages": [{"component_id": "floor", "damage_type": "floor_damage", "severity": 50}]},
    {"id": "diffuser", "name": "Diffuser damage", "damages": [{"component_id": "diffuser", "damage_type": "diffuser_damage", "severity": 50}]},
    {"id": "rear_wing", "name": "Rear wing damage", "damages": [{"component_id": "rear_wing", "damage_type": "wing_damage", "severity": 50}]},
    {"id": "suspension", "name": "Front suspension damage", "damages": [{"component_id": "front_suspension", "damage_type": "suspension_damage", "severity": 55}]},
    {"id": "puncture", "name": "Rear tyre puncture", "damages": [{"component_id": "rear_tyres", "damage_type": "puncture", "severity": 90}]},
    {"id": "brake_overheat", "name": "Front brake overheating", "damages": [{"component_id": "front_brakes", "damage_type": "brake_overheating", "severity": 70}]},
    {"id": "cooling", "name": "Cooling system failure", "damages": [{"component_id": "radiators", "damage_type": "cooling_failure", "severity": 60}]},
    {"id": "engine_overheat", "name": "Engine overheating", "damages": [{"component_id": "power_unit", "damage_type": "engine_overheating", "severity": 60}]},
    {"id": "lap_one", "name": "Lap-one incident (combined)", "damages": [
        {"component_id": "front_wing", "damage_type": "endplate_damage", "severity": 35},
        {"component_id": "floor", "damage_type": "floor_damage", "severity": 25},
        {"component_id": "sidepods", "damage_type": "inlet_damage", "severity": 30},
    ]},
]
