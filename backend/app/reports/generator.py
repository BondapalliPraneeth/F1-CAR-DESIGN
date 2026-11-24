"""Engineering report generation (Markdown) from actual simulation outputs only."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.components import COMPONENTS_BY_ID
from app.simulation.assumptions import VehicleAssumptions
from app.simulation.damage import classify_severity
from app.simulation.vehicle import SimulationResult, baseline


def _row(label: str, base: float, cur: float, unit: str, fmt: str = "{:.1f}") -> str:
    delta = cur - base
    pct = (delta / base * 100) if base else 0.0
    return f"| {label} | {fmt.format(base)} {unit} | {fmt.format(cur)} {unit} | {delta:+.2f} {unit} ({pct:+.1f}%) |"


def build_report(result: SimulationResult, a: VehicleAssumptions) -> tuple[str, str]:
    _, cbp, _, pb, _ = baseline(a)
    p, ae = result.performance, result.aero
    q = 0.5 * a.air_density * (ae.reference_speed_kmh / 3.6) ** 2
    damaged = [d for d in result.damages if d.severity > 0]
    title = ("Engineering report: " + ", ".join(
        f"{COMPONENTS_BY_ID[d.component_id].name} ({d.severity:.0f}%)" for d in damaged)) if damaged else "Engineering report: healthy baseline"

    lines = [
        f"# {title}",
        "",
        f"Generated {datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')} by ApexVision 3D, model `{result.model_version}`.",
        "",
        "> **MODEL-ESTIMATED VALUES.** Results come from a simplified, transparent engineering model "
        "(lumped aerodynamic coefficients, point-mass lap simulation, lumped thermal models). "
        "They are not CFD and are not validated against any real car. Use them for relative comparison only.",
        "",
        "## 1. Damage state",
        "",
    ]
    if damaged:
        lines += ["| Component | Damage type | Severity | Level |", "|---|---|---|---|"]
        for d in damaged:
            c = COMPONENTS_BY_ID[d.component_id]
            dt = next(x.label for x in c.damage_types if x.id == d.damage_type)
            lines.append(f"| {c.name} | {dt} | {d.severity:.0f}% | {classify_severity(d.severity)} |")
    else:
        lines.append("No damage applied: healthy reference vehicle.")

    lines += [
        "",
        "## 2. Vehicle-level summary",
        "",
        f"- Overall component health: **{result.overall_health_pct:.1f}%**",
        f"- Performance index (baseline lap / current lap): **{result.performance_index_pct:.2f}%**",
        f"- Structural integrity (weakest structure): **{result.structural_integrity_pct:.0f}%**",
        f"- Retirement recommended (model rule): **{'YES' if result.retire_recommended else 'no'}**",
        "",
        f"## 3. Aerodynamics at {ae.reference_speed_kmh:.0f} km/h",
        "",
        "| Quantity | Baseline | Current | Change |",
        "|---|---|---|---|",
        _row("Downforce", q * cbp.cla_total, ae.downforce_n, "N", "{:.0f}"),
        _row("Drag", q * cbp.cda_total, ae.drag_n, "N", "{:.0f}"),
        _row("Lift-to-drag (L/D)", cbp.efficiency, ae.lift_to_drag, "", "{:.3f}"),
        _row("Front balance", cbp.front_balance * 100, ae.front_balance_pct, "%", "{:.1f}"),
        _row("Effective ride height", cbp.effective_ride_height_mm, ae.effective_ride_height_mm, "mm", "{:.1f}"),
        "",
        "Equations: F_drag = 0.5 rho v^2 Cd A_frontal, F_downforce = 0.5 rho v^2 Cl A_ref "
        f"(rho = {a.air_density} kg/m^3, A = {a.frontal_area_m2} m^2).",
        "",
        "## 4. Performance",
        "",
        "| Quantity | Baseline | Current | Change |",
        "|---|---|---|---|",
        _row("Lap time (test circuit)", pb.lap_time_s, p.lap_time_s, "s", "{:.3f}"),
        _row("Top speed (DRS closed)", pb.top_speed_kmh, p.top_speed_kmh, "km/h"),
        _row("Slow corner speed (R25)", pb.corner_speeds_kmh["slow_corner_r25"], p.corner_speeds_kmh["slow_corner_r25"], "km/h"),
        _row("Medium corner speed (R100)", pb.corner_speeds_kmh["medium_corner_r100"], p.corner_speeds_kmh["medium_corner_r100"], "km/h"),
        _row("Max lateral accel. @250 km/h", pb.max_lateral_g_at_250, p.max_lateral_g_at_250, "g", "{:.2f}"),
        _row("Braking 300 to 100 km/h", pb.braking_distance_300_100_m, p.braking_distance_300_100_m, "m"),
        _row("Front tyre grip (mu)", pb.tyre_grip_front, p.tyre_grip_front, "", "{:.3f}"),
        _row("Rear tyre grip (mu)", pb.tyre_grip_rear, p.tyre_grip_rear, "", "{:.3f}"),
        _row("Front brake peak temp.", pb.brake_temp_front_peak_c, p.brake_temp_front_peak_c, "degC", "{:.0f}"),
        _row("Coolant mean temp.", pb.coolant_temp_mean_c, p.coolant_temp_mean_c, "degC", "{:.1f}"),
        _row("Delivered power factor", pb.delivered_power_factor, p.delivered_power_factor, "", "{:.3f}"),
        "",
        "## 5. Engineering explanation",
        "",
    ]
    if result.mechanisms:
        for m in result.mechanisms:
            lines.append(f"- **{COMPONENTS_BY_ID[m['component_id']].name}**: {m['explanation']}")
    else:
        lines.append("- No damage mechanisms active.")

    impacts = result.curves.get("lap_time_impact", {}).get("by_damage", []) if result.curves else []
    if impacts:
        lines += ["", "### Lap-time impact of each damage in isolation", "", "| Component | Severity | Delta lap |", "|---|---|---|"]
        for i in sorted(impacts, key=lambda x: -x["delta_lap_s"]):
            lines.append(f"| {COMPONENTS_BY_ID[i['component_id']].name} | {i['severity']:.0f}% | {i['delta_lap_s']:+.3f} s |")
        lines.append("")
        lines.append("Isolated deltas need not sum to the combined delta: effects interact (e.g. balance and grip).")

    lines += ["", "## 6. Warnings", ""]
    lines += [f"- {w}" for w in result.warnings] or ["- None."]

    if damaged:
        worst = max(impacts, key=lambda x: x["delta_lap_s"]) if impacts else None
        lines += ["", "## 7. Recommended inspection priority", ""]
        if result.retire_recommended:
            lines.append("1. Retirement recommended by the model rule (structure < 25%, puncture >= 75% or power derated to 50%).")
        if worst:
            lines.append(f"- Highest lap-time cost: **{COMPONENTS_BY_ID[worst['component_id']].name}** ({worst['delta_lap_s']:+.3f} s).")

    lines += [
        "",
        "## 8. Assumptions and limitations",
        "",
        "- All coefficients are generic modelling assumptions, not data from any real Formula 1 car.",
        "- Aerodynamics: lumped per-component Cl/Cd shares, quadratic ride-height sensitivity. No CFD, no yaw, no wake interaction beyond the documented couplings.",
        "- Lap time: quasi-steady-state point mass on an invented test circuit; no combined slip, load transfer dynamics or gear shifts.",
        "- Thermal: lumped-capacitance brake disc and coolant models with assumed coefficients.",
        "- Full methodology: docs/simulation_methodology.md.",
        "",
        "### Assumption values used",
        "",
        "| Parameter | Value |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in a.model_dump().items()]
    return title, "\n".join(lines) + "\n"
