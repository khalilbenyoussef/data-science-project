"""API « Audit et confiance » : resume, controles, explication (lecture seule)."""
import json
from pathlib import Path

import duckdb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from dashboard_app.api.audit import CHECK_DESCRIPTIONS, create_audit_router

CHECKS = [
    {"check_id": "A1_recomputed_values", "category": "recomputation", "result": "pass", "detail": "0 ecart",
     "affected_rows": [], "affects_publication": True},
    {"check_id": "A6_user_source_facts", "category": "recomputation", "result": "pass", "detail": "aucune",
     "affected_rows": [], "affects_publication": True},
    {"check_id": "C2_partial_peer_coverage", "category": "caveat", "result": "warn", "detail": "84 lignes",
     "affected_rows": [{"kpi_id": "account_ownership", "iso3": "PEERS", "year": y, "missing_peers": ["MAR"]}
                       for y in range(1800, 2050)], "affects_publication": True},
]


@pytest.fixture
def audit_env(tmp_path):
    audit = tmp_path / "audit"
    audit.mkdir()
    (audit / "audit_report.json").write_text(json.dumps({
        "run_id": "run_x", "snapshot_id": "v5", "created_at": "2026-11-04T10:52:21", "verdict": "pass_with_warnings",
        "counts": {"pass": 2, "warn": 1, "fail": 0}, "checks": CHECKS,
        "publication": {"by_status": {"approved": 3, "approved_with_review_note": 2, "blocked": 0}},
        "route2_insight_audit": {"run_id": "route2_x", "audited": 1, "accepted": 1, "rejected": 0, "not_auditable": 1,
                                 "results": [{"insight_id": "overview:INS-1", "accepted": True, "reasons": []}],
                                 "not_auditable_ids": ["poverty:INS-2"]},
    }), encoding="utf-8")
    (audit / "evaluation.json").write_text(json.dumps({
        "created_at": "2026-11-04T09:00:00", "detected": 9, "total": 9,
        "faults": [{"id": "tampered_value", "label": "Valeur modifiee", "expected_check": "A1_recomputed_values",
                    "detected": True, "verdict": "fail", "failing_checks": ["A1_recomputed_values"]}]}), encoding="utf-8")
    spec = tmp_path / "finova.json"
    spec.write_text(json.dumps({"pages": [
        {"id": "overview", "insights": [{"id": "INS-1", "statement": "En 2024, 37.8 % ont un compte.",
                                         "evidence_ids": ["F-account_ownership-TUN-2024"]}]},
        {"id": "poverty", "insights": [{"id": "INS-2", "statement": "SMIG 528 TND.", "evidence_ids": []}]}],
        "facts": [{"id": "F-account_ownership-TUN-2024", "code": "account_ownership", "value": 37.8, "year": 2024,
                   "iso3": "TUN", "provider": "semantic", "display": "37.8 %", "unit": "percent",
                   "evidence_ids": ["EV-account_ownership-TUN-2024"]}]}), encoding="utf-8")
    warehouse = tmp_path / "warehouse.duckdb"
    record = {"kpi_id": "account_ownership", "iso3": "TUN", "country": "Tunisia", "year": 2024, "value": 37.84,
              "unit": "percent", "formula": "100 * value", "transformation": "fraction x 100", "snapshot_id": "v5",
              "catalog_version": "1.6.0", "publication_status": "approved", "review_reasons": [],
              "inputs": [{"role": "valeur", "fact_value": 0.3784, "fact_unit": "fraction", "status": "ok",
                          "raw": {"source": "findex", "file": "C:\\secret\\dossier\\blob.csv", "column": "account_t_d",
                                  "raw_value_text": "0.3784", "record_key": {}}}],
              "checks": [{"check_id": "C4_within_survey_noise", "result": "warn", "affects_publication": False}],
              "narrative": {"fr": "texte"}}
    with duckdb.connect(str(warehouse)) as con:
        con.execute("CREATE TABLE kpi_values (kpi_id VARCHAR, iso3 VARCHAR, year INTEGER, "
                    "publication_status VARCHAR, review_reasons VARCHAR[])")
        con.executemany("INSERT INTO kpi_values VALUES (?, ?, ?, ?, ?)", [
            ("account_ownership", "PEERS", 2011, "approved_with_review_note", ["partial_peer_coverage"]),
            ("account_ownership", "PEERS", 2014, "approved_with_review_note", ["no_peer_observation"]),
            ("user_kpi_inconnu", "TUN", 2024, "approved_with_review_note", ["partial_peer_coverage"]),
            ("account_ownership", "TUN", 2024, "approved", []),
        ])
        con.execute("CREATE TABLE kpi_explanations (kpi_id VARCHAR, iso3 VARCHAR, year INTEGER, explanation JSON)")
        con.execute("INSERT INTO kpi_explanations VALUES ('account_ownership', 'TUN', 2024, ?)", [json.dumps(record)])
    app = FastAPI()
    app.include_router(create_audit_router(audit_dir=audit, warehouse=warehouse, spec_file=spec))
    return TestClient(app), audit


def test_summary_counts_reasons_insights_and_stale_evaluation(audit_env):
    client, _ = audit_env
    body = client.get("/api/audit/summary").json()
    assert (body["verdict"], body["counts"], body["snapshot_id"]) == ("pass_with_warnings",
                                                                      {"pass": 2, "warn": 1, "fail": 0}, "v5")
    assert body["publication"] == {"approved": 3, "approved_with_review_note": 2, "blocked": 0}
    # kpi hors catalogue officiel (source utilisateur) non compte
    assert [(r["reason"], r["rows"]) for r in body["review_reasons"]] == [("no_peer_observation", 1),
                                                                          ("partial_peer_coverage", 1)]
    insights = body["insight_audit"]["insights"]
    assert insights[0]["cited"][0]["iso3"] == "TUN" and insights[0]["cited"][0]["year"] == 2024
    assert insights[1]["accepted"] is None and insights[1]["statement"] == "SMIG 528 TND."
    assert body["evaluation"]["detected"] == 9 and body["evaluation"]["stale"] is True


def test_checks_have_french_descriptions_and_capped_rows(audit_env):
    client, _ = audit_env
    checks = {c["check_id"]: c for c in client.get("/api/audit/checks").json()["checks"]}
    assert checks["A1_recomputed_values"]["description"] == CHECK_DESCRIPTIONS["A1_recomputed_values"]
    assert checks["A6_user_source_facts"]["user_sources"] is True
    warn = checks["C2_partial_peer_coverage"]
    assert warn["affected_count"] == 250 and len(warn["affected_rows"]) == 200 and warn["truncated"] is True


def test_every_known_check_has_a_description():
    report = Path("data/audit/audit_report.json")
    if report.is_file():
        ids = {c["check_id"] for c in json.loads(report.read_text(encoding="utf-8"))["checks"]}
        assert ids <= set(CHECK_DESCRIPTIONS)


def test_explain_is_validated_and_hides_local_paths(audit_env):
    client, _ = audit_env
    body = client.get("/api/audit/explain", params={"kpi_id": "account_ownership", "iso3": "tun", "year": 2024}).json()
    assert body["value"] == 37.84 and body["inputs"][0]["raw"]["file"] == "blob.csv"
    assert body["checks_touching"][0]["check_id"] == "C4_within_survey_noise"
    assert "A1_recomputed_values" in body["checks_passed"] and "A6_user_source_facts" not in body["checks_passed"]
    for params, status in (({"kpi_id": "inconnu", "iso3": "TUN", "year": 2024}, 400),
                           ({"kpi_id": "account_ownership", "iso3": "T;N", "year": 2024}, 400),
                           ({"kpi_id": "account_ownership", "iso3": "MAR", "year": 2024}, 404),
                           ({"kpi_id": "account_ownership", "iso3": "TUN", "year": 1500}, 422)):
        assert client.get("/api/audit/explain", params=params).status_code == status, params


def test_missing_report_returns_503(tmp_path):
    app = FastAPI()
    app.include_router(create_audit_router(audit_dir=tmp_path, warehouse=tmp_path / "w.duckdb",
                                           spec_file=tmp_path / "f.json"))
    assert TestClient(app).get("/api/audit/summary").status_code == 503
