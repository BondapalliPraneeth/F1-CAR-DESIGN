"""Deterministic, rule-based assistant used when no LLM API key is configured.

It still answers via the same tools, so every number it states comes from the
simulation. It is clearly labelled as rule-based in the UI.
"""

from __future__ import annotations

import re

from app.ai.tools import ToolContext, run_tool
from app.domain.components import COMPONENTS, COMPONENTS_BY_ID

ALIASES: dict[str, list[str]] = {
    "front_wing": ["front wing", "endplate", "front-wing"],
    "nose_cone": ["nose"],
    "front_suspension": ["front suspension"],
    "front_tyres": ["front tyre", "front tire"],
    "front_brakes": ["front brake"],
    "monocoque": ["monocoque", "chassis", "survival cell"],
    "halo": ["halo"],
    "cockpit": ["cockpit"],
    "sidepods": ["sidepod"],
    "radiators": ["radiator", "cooling system", "cooling"],
    "floor": ["floor"],
    "venturi_tunnels": ["venturi", "tunnel"],
    "diffuser": ["diffuser"],
    "rear_suspension": ["rear suspension"],
    "rear_tyres": ["rear tyre", "rear tire"],
    "rear_brakes": ["rear brake"],
    "rear_wing": ["rear wing"],
    "drs": ["drs"],
    "power_unit": ["engine", "power unit", "pu "],
    "rear_crash_structure": ["crash structure"],
}


def _find_component(q: str, selected: str | None) -> str | None:
    ql = q.lower()
    best = None
    for cid, keys in ALIASES.items():
        for k in keys:
            if k in ql and (best is None or len(k) > best[1]):
                best = (cid, len(k))
    if best:
        return best[0]
    if ("tyre" in ql or "tire" in ql):
        return "rear_tyres" if "rear" in ql else "front_tyres"
    if "brake" in ql:
        return "rear_brakes" if "rear" in ql else "front_brakes"
    if "suspension" in ql:
        return "rear_suspension" if "rear" in ql else "front_suspension"
    return selected


def answer(question: str, ctx: ToolContext) -> tuple[str, list[dict]]:
    q = question.lower()
    calls: list[dict] = []

    def call(name: str, **args) -> dict:
        res = run_tool(ctx, name, args)
        calls.append({"tool": name, "args": args, "result": res})
        return res

    comp = _find_component(question, ctx.selected_component)
    pct = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%", q)

    # 1) hypothetical damage
    if pct and comp and any(w in q for w in ("damage", "happen", "lose", "loss", "puncture", "overheat", "fail")):
        sev = float(pct.group(1))
        dtype = None
        valid = [d.id for d in COMPONENTS_BY_ID[comp].damage_types]
        for kw, did in (("endplate", "endplate_damage"), ("element", "element_failure"), ("partial", "element_failure"),
                        ("puncture", "puncture"), ("overheat", "overheating"), ("overheat", "engine_overheating"),
                        ("stuck open", "stuck_open"), ("stuck closed", "stuck_closed"), ("power", "power_loss")):
            if kw in q and did in valid:
                dtype = did
                break
        res = call("simulate_component_damage", component_id=comp, damage_type=dtype, severity=sev)
        h, cv = res["hypothetical_damage"], res["change_vs_healthy"]
        rr = res["result"]
        lines = [
            f"**{h['name']}: {h['damage_type'].replace('_', ' ')} at {h['severity_pct']:.0f}% ({h['level']})**, simulated:",
            "",
            f"- Lap time: {rr['lap_time_s']:.3f} s ({cv['lap_time_s']:+.3f} s vs healthy)",
            f"- Downforce @250 km/h: {rr['downforce_n_at_250kmh']:.0f} N ({cv['downforce_n_at_250kmh']:+.0f} N)",
            f"- Drag @250 km/h: {rr['drag_n_at_250kmh']:.0f} N ({cv['drag_n_at_250kmh']:+.0f} N)",
            f"- Front aero balance: {rr['front_balance_pct']:.1f}% ({cv['front_balance_pct']:+.1f} pts)",
            f"- Top speed: {rr['top_speed_kmh']:.1f} km/h ({cv['top_speed_kmh']:+.1f} km/h)",
            "",
            "**Why:** " + " ".join(res["mechanisms"]),
        ]
        if res["warnings"]:
            lines += ["", "**Warnings:** " + " ".join(res["warnings"])]
        lines += ["", "_This was a hypothetical run; your car's damage state is unchanged._"]
        return "\n".join(lines), calls

    # 2) drag ranking
    if "drag" in q and any(w in q for w in ("most", "contribut", "biggest", "largest", "which")):
        res = call("calculate_aerodynamic_performance", speed_kmh=250)
        top = res["drag_by_component_n"][:5]
        lines = [f"At {res['speed_kmh']:.0f} km/h the simulated car produces {res['current']['drag_n']:.0f} N of drag. Largest contributors:", ""]
        lines += [f"{i + 1}. {t['name']}: {t['drag_n']:.0f} N ({t['share_pct']:.1f}%)" for i, t in enumerate(top)]
        lines += ["", "Exposed rotating wheels and the wings dominate open-wheel drag: the wheels are bluff bodies, and the wings pay induced drag for their downforce."]
        return "\n".join(lines), calls

    # 3) drag vs downforce
    if "drag" in q and "downforce" in q:
        res = call("calculate_aerodynamic_performance", speed_kmh=250)
        c = res["current"]
        txt = (
            "**Downforce** is the vertical aerodynamic force pushing the car onto the track. It increases tyre normal load and so cornering grip "
            "without adding mass. **Drag** is the force opposing motion. It limits top speed and costs power.\n\n"
            f"Both scale with v²: F = ½·ρ·v²·C·A. In this model at {res['speed_kmh']:.0f} km/h the car makes {c['downforce_n']:.0f} N of downforce "
            f"and {c['drag_n']:.0f} N of drag, an L/D of {c['lift_to_drag']:.3f}. Overcoming that drag costs {c['drag_power_kw']:.1f} kW."
        )
        return txt, calls

    # 4) balance
    if "balance" in q:
        res = call("compare_vehicle_conditions")
        rep = call("get_damage_report")
        ch = res["change"].get("front_balance_pct", 0.0)
        txt = (f"Front aero balance is {res['current']['front_balance_pct']:.1f}% versus {res['healthy']['front_balance_pct']:.1f}% healthy "
               f"({ch:+.1f} pts). Balance is the share of total downforce on the front axle. Each surface's load is split between the axles "
               "according to where its centre of pressure sits. Losing front-wing load moves the balance rearward (understeer). Losing rear-wing or "
               "diffuser load moves it forward (oversteer).")
        if rep["mechanisms"]:
            txt += "\n\n**Active mechanisms:**\n" + "\n".join(f"- {m['explanation']}" for m in rep["mechanisms"])
        return txt, calls

    # 5) inspection priority
    if "inspect" in q or "priority" in q or "first" in q:
        rep = call("get_damage_report")
        if not rep["inspection_priority"]:
            return "No damage is currently applied, so there is nothing to prioritise. The car is in its healthy baseline state.", calls
        lines = [f"Combined lap-time loss: {rep['combined_delta_lap_s']:+.3f} s. Priority by isolated lap-time impact:", ""]
        lines += [f"{p['rank']}. **{p['name']}** ({p['damage_type'].replace('_', ' ')}, {p['severity_pct']:.0f}%): {p['isolated_delta_lap_s']:+.3f} s"
                  for p in rep["inspection_priority"]]
        if rep["retire_recommended"]:
            lines += ["", "The model rule recommends **retirement** (critical structure, puncture or power derate)."]
        if rep["warnings"]:
            lines += ["", "Warnings: " + " ".join(rep["warnings"])]
        return "\n".join(lines), calls

    # 6) tyre overheating
    if ("tyre" in q or "tire" in q) and ("overheat" in q or "temperature" in q):
        tgt = comp if comp in ("front_tyres", "rear_tyres") else "rear_tyres"
        res = call("simulate_component_damage", component_id=tgt, damage_type="overheating", severity=50)
        rr, cv = res["result"], res["change_vs_healthy"]
        key = "front" if tgt == "front_tyres" else "rear"
        txt = (f"Tyre friction peaks inside a temperature window. Overheating softens the compound, so it loses mechanical "
               f"grip and wears faster. Simulated 50% overheating of the {key} tyres: surface temperature {rr[f'tyre_temp_{key}_c']:.1f} degC, "
               f"grip mu {rr[f'tyre_grip_{key}_mu']:.3f} ({cv[f'tyre_grip_{key}_mu']:+.3f}), lap time {cv['lap_time_s']:+.3f} s vs healthy.")
        return txt, calls

    # 7) component explanation (default when a component is identified)
    if comp:
        d = call("get_component_details", component_id=comp)
        txt = (f"**{d['name']}** ({d['category']}, {d['position'].lower()})\n\n{d['purpose']} {d['engineering_explanation']}\n\n"
               f"**Performance contribution:** {d['performance_contribution']}\n\n"
               f"**Current state:** {d['current_health_pct']:.0f}% health ({d['current_damage_level']}).")
        if "current_downforce_n_at_250kmh" in d:
            txt += f" Currently generating {d['current_downforce_n_at_250kmh']:.0f} N of downforce at 250 km/h."
        if "current_drag_n_at_250kmh" in d:
            txt += f" Drag contribution: {d['current_drag_n_at_250kmh']:.0f} N at 250 km/h."
        txt += "\n\n**Failure modes:** " + "; ".join(d["failure_modes"]) + "."
        return txt, calls

    # 8) fallback: vehicle status
    s = call("get_vehicle_status")
    st = s["status"]
    txt = (f"Current simulated state: lap {st['lap_time_s']:.3f} s, top speed {st['top_speed_kmh']:.1f} km/h, "
           f"{st['downforce_n_at_250kmh']:.0f} N downforce and {st['drag_n_at_250kmh']:.0f} N drag at 250 km/h, front balance {st['front_balance_pct']:.1f}%. "
           f"Overall health {st['overall_health_pct']:.1f}%.")
    if s["damaged_components"]:
        txt += " Damaged: " + ", ".join(f"{d['name']} ({d['severity_pct']:.0f}%)" for d in s["damaged_components"]) + "."
    txt += ("\n\nTry asking: *What does the diffuser do?*, *What happens if the front wing is damaged?*, "
            "*Which component contributes most to drag?* or *Which damaged component should be inspected first?*")
    return txt, calls


__all__ = ["answer", "COMPONENTS"]
