FLOOR = {"component_id": "floor", "damage_type": "floor_damage", "severity": 50}


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_components(client):
    comps = client.get("/api/v1/components").json()
    assert len(comps) == 20
    d = client.get("/api/v1/components/diffuser").json()
    assert d["parameters"] and all(p["source"] == "model_assumption" for p in d["parameters"])
    assert client.get("/api/v1/components/warp_drive").status_code == 404


def test_car_and_scenarios(client):
    car = client.get("/api/v1/car").json()
    assert car["component_count"] == 20 and car["asset_url"].endswith(".glb")
    assert len(client.get("/api/v1/scenarios").json()) >= 10


def test_live_simulation_does_not_persist(client):
    r = client.post("/api/v1/damage/simulate", json={"damages": [FLOOR], "include_curves": False}).json()
    assert r["persisted"] is False and r["simulation_id"] is None


def test_persisted_simulation_report_and_history(client):
    sid = "pytest-session-1"
    r = client.post("/api/v1/damage/simulate", json={"session_id": sid, "persist": True, "damages": [FLOOR]}).json()
    assert r["persisted"] and r["report_id"]
    for fmt, ctype in (("json", "application/json"), ("md", "text/markdown"), ("html", "text/html")):
        resp = client.get(f"/api/v1/reports/{r['report_id']}?format={fmt}")
        assert resp.status_code == 200 and resp.headers["content-type"].startswith(ctype)
    assert client.get("/api/v1/reports/does-not-exist").status_code == 404
    status = client.get(f"/api/v1/vehicle/status?session_id={sid}").json()
    assert status["source"] == "latest_saved_simulation" and status["simulation_id"] == r["simulation_id"]
    hist = client.get(f"/api/v1/history?session_id={sid}").json()
    assert hist[0]["simulation_id"] == r["simulation_id"]


def test_validation_errors(client):
    bad = client.post("/api/v1/damage/simulate", json={"damages": [{**FLOOR, "severity": 300}]})
    assert bad.status_code == 422 and bad.json()["error"] == "validation_error"
    assert client.post("/api/v1/damage/simulate", json={"assumptions": {"mass_kg": -5}}).status_code == 422


def test_aero_and_compare(client):
    r = client.post("/api/v1/aerodynamics/calculate", json={"speed_kmh": 200, "damages": [FLOOR]}).json()
    assert r["current"]["downforce_n"] < r["baseline"]["downforce_n"]
    assert "not CFD" in r["label"]
    c = client.post("/api/v1/simulation/compare", json={"b": {"damages": [FLOOR]}}).json()
    assert c["delta"]["lap_time_s"] > 0


def test_performance_analyse(client):
    r = client.post("/api/v1/performance/analyse", json={"damages": [FLOOR]}).json()
    assert r["performance"]["lap_time_s"] > 0 and "lap_trace" in r["curves"]


def test_ai_ask_offline(client):
    r = client.post("/api/v1/ai/ask", json={"question": "What happens if the rear wing is 50% damaged?"}).json()
    assert r["provider"] == "offline" and r["tool_calls"] and r["numeric_claims_verified"]
    bad = client.post("/api/v1/ai/ask", json={"question": "hi there", "selected_component": "flux_capacitor"})
    assert bad.status_code == 422


def test_csv_export(client):
    r = client.post("/api/v1/performance/export.csv", json={"damages": [FLOOR]})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "speed_current_kmh" in r.text and "MODEL-ESTIMATED" in r.text


def test_ai_global_rate_limit_cannot_be_bypassed_with_spoofed_ips(client, monkeypatch):
    from app.api.v1 import ai_reports
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ai_global_rate_limit_per_minute", 3)
    monkeypatch.setattr(ai_reports, "_global_hits", ai_reports.deque())
    codes = [client.post("/api/v1/ai/ask", json={"question": "What does the floor do?"},
                         headers={"X-Forwarded-For": f"10.0.0.{i}"}).status_code for i in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3:] == [429, 429]
