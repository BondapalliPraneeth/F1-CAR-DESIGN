from app.ai import offline
from app.ai.tools import TOOLS, ToolContext, run_tool
from app.ai.verify import verify_numbers
from app.simulation.assumptions import VehicleAssumptions
from app.simulation.damage import DamageInput

REQUIRED = {"get_component_details", "get_vehicle_status", "calculate_aerodynamic_performance",
            "simulate_component_damage", "compare_vehicle_conditions", "get_damage_report"}


def ctx(damages=()):
    return ToolContext(assumptions=VehicleAssumptions(), damages=list(damages), selected_component=None)


def test_all_required_tools_registered():
    assert REQUIRED <= set(TOOLS)


def test_tools_run():
    c = ctx([DamageInput(component_id="floor", damage_type="floor_damage", severity=40)])
    for name in REQUIRED:
        args = {"component_id": "floor"} if name in ("get_component_details", "simulate_component_damage") else {}
        assert isinstance(run_tool(c, name, args), dict)


def test_unknown_tool_returns_error():
    assert "error" in run_tool(ctx(), "delete_everything", {})


def test_verifier_accepts_traceable_and_flags_invented():
    tools = [{"lap_time_s": 74.317, "downforce_n": 11459.2}]
    assert verify_numbers("Lap time 74.32 s, downforce 11459 N", tools) == []
    assert verify_numbers("Downforce drops by 4321 N", tools) == ["4321"]


def test_offline_answers_are_fully_verified():
    for q in ["What happens if the floor is 50% damaged?", "Which component contributes most drag?",
              "What should I inspect first?", "How is the aero balance?", "Explain the diffuser"]:
        c = ctx([DamageInput(component_id="front_wing", damage_type="endplate_damage", severity=40)])
        text, calls = offline.answer(q, c)
        assert text and calls
        assert verify_numbers(text, [x["result"] for x in calls], q) == [], (q, text)
