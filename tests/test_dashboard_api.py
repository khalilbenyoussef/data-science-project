import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard_app.api.app import create_app


def _fact(code: str, display: str, *, iso3: str = "TUN", year: int = 2024) -> dict:
    return {
        "id": f"F-{code}-{iso3}-{year}",
        "code": code,
        "label": code,
        "value": float(display.replace(" %", "").replace(" ", "")),
        "display": display,
        "unit": "percent",
        "year": year,
        "iso3": iso3,
        "provider": "semantic",
        "evidence_ids": [],
    }


def _spec(iso3: str = "TUN", year: int = 2024) -> dict:
    name = {"TUN": "Tunisie", "DZA": "Algérie"}.get(iso3, iso3)
    return {
        "schema_version": "2.0",
        "generated_at": "2026-10-29T12:00:00",
        "run_id": f"test_{iso3}",
        "country": {"iso3": iso3, "name": name},
        "year": year,
        "pages": [
            {"id": "overview", "title": "Vue d'ensemble", "metrics": [],
             "charts": [], "insights": [], "blocks": [], "notices": []},
        ],
        "facts": [
            _fact("account_ownership", "37.8 %", iso3=iso3, year=year),
        ],
        "notices": [],
        "publication_status": "not_evaluated",
    }


@pytest.fixture()
def spec_path(tmp_path: Path) -> Path:
    path = tmp_path / "finova.json"
    path.write_text(json.dumps(_spec()), encoding="utf-8")
    return path


@pytest.fixture()
def calls() -> list[tuple[str, int]]:
    return []


@pytest.fixture()
def client(spec_path: Path, calls: list[tuple[str, int]], tmp_path: Path):
    def builder(iso3: str, year: int) -> dict:
        calls.append((iso3, year))
        return _spec(iso3, year)

    app = create_app(
        spec_path=spec_path, warehouse_path=tmp_path / "missing.duckdb",
        reports_dir=tmp_path / "reports", history_dir=tmp_path / "history",
        web_dist=tmp_path / "dist", spec_builder=builder,
    )
    return TestClient(app)


def test_health_and_current_spec(client):
    health = client.get("/api/health")
    assert health.status_code == 200 and health.json()["status"] == "ok"

    response = client.get("/api/spec")
    assert response.status_code == 200
    assert response.headers["X-Finova-Source"] == "file"
    payload = response.json()
    assert payload["country"]["iso3"] == "TUN"
    assert payload["year"] == 2024


def test_other_scope_is_generated_then_cached(client, calls):
    response = client.get("/api/spec", params={"iso3": "dza", "year": 2023})
    assert response.status_code == 200
    assert response.headers["X-Finova-Source"] == "generated"
    assert response.json()["country"]["iso3"] == "DZA"
    assert calls == [("DZA", 2023)]
    client.get("/api/spec", params={"iso3": "DZA", "year": 2023})
    assert calls == [("DZA", 2023)]


def test_ask_uses_verified_facts(client):
    response = client.post(
        "/api/ask", json={"question": "Combien d'adultes ont un compte ?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "account"
    assert body["fallback"] is False
    assert "37.8 %" in body["answer"]
    assert body["number_check"]["passed"] is True
    assert body["iso3"] == "TUN" and body["year"] == 2024


def test_ask_on_other_country_resolves_its_scope(client, calls):
    response = client.post(
        "/api/ask",
        json={"question": "Combien d'adultes ont un compte ?", "iso3": "DZA",
              "year": 2023},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["country_name"] == "Algérie"
    assert body["year"] == 2023
    assert calls == [("DZA", 2023)]


def test_ask_unknown_intent_is_explicit(client):
    response = client.post("/api/ask", json={"question": "Quel temps fait-il ?"})
    assert response.status_code == 200
    assert response.json()["fallback"] is True


def test_ask_rejects_unknown_fields(client):
    response = client.post(
        "/api/ask", json={"question": "Compte ?", "kpi": "poverty"},
    )
    assert response.status_code == 422


def test_ask_rejects_empty_question(client):
    assert client.post("/api/ask", json={"question": "   "}).status_code == 422


def test_ask_chat_uses_the_llm_tools_and_session_history(spec_path, tmp_path):
    from langchain_core.messages import AIMessage

    class Model:
        def __init__(self):
            self.replies = [
                AIMessage("", tool_calls=[{"name": "get_kpi", "id": "c1",
                                           "args": {"kpi_id": "account_ownership"}}]),
                AIMessage("En 2024, 37,8 % des adultes ont un compte."),
            ]
            self.seen = []

        def invoke(self, messages):
            self.seen.append(messages)
            return self.replies.pop(0)

    model = Model()
    app = create_app(
        spec_path=spec_path, warehouse_path=tmp_path / "missing.duckdb",
        reports_dir=tmp_path / "reports", history_dir=tmp_path / "history",
        web_dist=tmp_path / "dist", spec_builder=lambda iso3, year: _spec(iso3, year),
        ask_model=model,
    )
    body = TestClient(app).post("/api/ask", json={
        "question": "Et le taux de compte ?", "session_id": "abc", "page": "overview",
        "history": [{"role": "user", "text": "Bonjour"}, {"role": "assistant", "text": "Bonjour !"}],
    }).json()
    assert body["mode"] == "llm" and body["number_check"]["passed"]
    assert body["facts"][0]["id"] == "F-account_ownership-TUN-2024"
    assert body["budget_left"] == 28 and len(body["suggestions"]) >= 3
    assert [m.content for m in model.seen[0][1:3]] == ["Bonjour", "Bonjour !"]


def test_missing_spec_returns_503(tmp_path: Path):
    app = create_app(
        spec_path=tmp_path / "absent.json", warehouse_path=tmp_path / "w.duckdb",
        reports_dir=tmp_path / "reports", history_dir=tmp_path / "history",
        web_dist=tmp_path / "dist", spec_builder=lambda iso3, year: _spec(),
    )
    other = TestClient(app)
    assert other.get("/api/spec").status_code == 503
    assert other.get("/api/health").json()["spec_loaded"] is False


def test_runs_lists_reports(client, tmp_path: Path):
    reports = tmp_path / "reports"
    run_dir = reports / "route2_test"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({
        "run_id": "route2_test", "status": "success",
        "objective": "Dashboard", "started_at": "2026-10-29T12:00:00",
        "finished_at": "2026-10-29T12:01:00",
    }), encoding="utf-8")
    (run_dir / "finova_spec.json").write_text("{}", encoding="utf-8")
    response = client.get("/api/runs")
    assert response.status_code == 200
    runs = response.json()["runs"]
    assert runs[0]["run_id"] == "route2_test"
    assert runs[0]["spec"] is True


def test_strict_content_security_policy_on_api_and_ui(client):
    from dashboard_app.api.app import CONTENT_SECURITY_POLICY

    for path in ("/api/spec", "/api/health", "/"):
        response = client.get(path)
        csp = response.headers.get("Content-Security-Policy")
        assert csp == CONTENT_SECURITY_POLICY, path
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert "'unsafe-inline'" not in CONTENT_SECURITY_POLICY and "'unsafe-eval'" not in CONTENT_SECURITY_POLICY
    assert "default-src 'self'" in CONTENT_SECURITY_POLICY and "frame-ancestors 'none'" in CONTENT_SECURITY_POLICY
    assert "Content-Security-Policy" not in client.get("/docs").headers  # documentation de developpement
