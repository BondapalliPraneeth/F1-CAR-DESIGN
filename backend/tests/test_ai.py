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


def test_offline_healthy_car_and_hint_text_are_verified():
    # Regression: the "Try asking" hint once contained an example number that no tool returned.
    for q in ["What is the current state of the car?", "hello", "What happens if the front wing is damaged?"]:
        text, calls = offline.answer(q, ctx([]))
        assert text and calls
        assert verify_numbers(text, [x["result"] for x in calls], q) == [], (q, text)


def _settings(**kw):
    from app.core.config import Settings
    base = {"gemini_api_key": None, "openai_api_key": None, "groq_api_key": None, "neon_ai_gateway_base_url": None,
            "neon_ai_gateway_token": None, "ai_provider": "auto"}
    return Settings(_env_file=None, **{**base, **kw})


def test_neon_gateway_provider_resolution():
    from app.ai.assistant import resolve_provider
    gw = {"neon_ai_gateway_base_url": "https://gw.example", "neon_ai_gateway_token": "t"}
    assert resolve_provider(_settings()) == "offline"
    assert resolve_provider(_settings(**gw)) == "neon"
    assert resolve_provider(_settings(gemini_api_key="k", **gw)) == "gemini"  # explicit provider keys win
    assert resolve_provider(_settings(ai_provider="neon")) == "offline"  # neon requested but not configured


def test_neon_gateway_request_shape_and_fallback(monkeypatch):
    import httpx

    from app.ai import assistant

    seen = {}

    def fake_post(self, url, headers=None, json=None):
        seen.update(url=url, auth=headers["Authorization"], body=json)
        return httpx.Response(403, json={"error": {"unavailable_reason": "paid_plan_required"}})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    s = _settings(neon_ai_gateway_base_url="https://gw.example/", neon_ai_gateway_token="tok", neon_ai_model="m1")
    out = assistant.ask("What is the current state of the car?", ctx(), s)
    assert seen["url"] == "https://gw.example/v1/chat/completions"
    assert seen["auth"] == "Bearer tok"
    assert seen["body"]["model"] == "m1" and "temperature" not in seen["body"] and seen["body"]["tools"]
    # A gateway error (e.g. no AI credits yet) must still produce a verified offline answer.
    assert out["provider"] == "offline" and out["notice"] and out["numeric_claims_verified"]


def test_groq_provider_resolution():
    from app.ai.assistant import resolve_provider
    assert resolve_provider(_settings(groq_api_key="k")) == "groq"
    assert resolve_provider(_settings(ai_provider="groq")) == "offline"  # requested but no key
    assert resolve_provider(_settings(ai_provider="groq", groq_api_key="k", openai_api_key="o")) == "groq"


def test_groq_request_shape_and_fallback(monkeypatch):
    import httpx

    from app.ai import assistant

    seen = {}

    def fake_post(self, url, headers=None, json=None):
        seen.update(url=url, auth=headers["Authorization"], body=json)
        return httpx.Response(401, json={"error": {"message": "invalid api key"}})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    s = _settings(groq_api_key="gsk_test", groq_model="llama-test")
    out = assistant.ask("What is the current state of the car?", ctx(), s)
    assert seen["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert seen["auth"] == "Bearer gsk_test"
    assert seen["body"]["model"] == "llama-test" and seen["body"]["tools"]
    assert out["provider"] == "offline" and out["notice"] and out["numeric_claims_verified"]


def test_migrations_prefer_unpooled_url():
    s = _settings(database_url="postgresql://u:p@pooler.example/db", database_url_unpooled="postgres://u:p@direct.example/db")
    assert s.sqlalchemy_url == "postgresql+psycopg://u:p@pooler.example/db"
    assert s.migration_url == "postgresql+psycopg://u:p@direct.example/db"
