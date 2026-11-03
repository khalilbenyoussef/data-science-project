"""Route 2 graph: analyst and dashboard agree, finalize merges, history works."""
import json

import pytest

from biflow.route2_graph import run_route2
from test_dashboard_spec import finova_warehouse  # reusable temporary warehouse

REQUEST = {
    "iso3": ("TUN", "DZA", "EGY", "JOR", "MAR"), "mode": "year", "year": 2024,
    "kpi_ids": ("account_ownership", "branch_density", "digital_payment_rate",
                "saving_rate", "borrowing_rate"),
}


@pytest.fixture
def config(tmp_path):
    return {
        "paths": {
            "reports": str(tmp_path / "reports"),
            "processed": str(tmp_path / "processed"),
            "quality": str(tmp_path / "quality"),
        },
        "quality": {"score_threshold": 0.7},
        "dashboard": {
            "spec_output": str(tmp_path / "public" / "finova.json"),
            "history_dir": str(tmp_path / "history"),
            "default_country": "TUN",
            "default_year": 2024,
        },
        "llm": {"enabled": False},
    }


def test_route2_runs_analyst_and_dashboard_in_sequence(tmp_path, finova_warehouse, config):
    state = run_route2(
        REQUEST, cfg=config, run_id="route2_test", warehouse_path=finova_warehouse,
    )
    assert state["status"] == "success", state.get("errors")
    summary = state["route2_summary"]
    assert summary["facts"] > 0 and summary["insights"] > 0
    assert summary["xai"] is True
    assert summary["publication_status"] == "not_evaluated"

    public = tmp_path / "public" / "finova.json"
    assert public.is_file()
    spec = json.loads(public.read_text(encoding="utf-8"))
    assert spec["schema_version"] == "2.0"
    assert [page["id"] for page in spec["pages"]] == [
        "overview", "inclusion", "access", "exclusion", "poverty", "pipeline",
    ]
    overview = spec["pages"][0]
    assert overview["metrics"][0]["value"] == pytest.approx(37.84)
    assert overview["insights"]
    exclusion = spec["pages"][3]
    assert exclusion["xai"]["recommendation"]["kind"] == "hypothesis"
    assert spec["publication_status"] == "not_evaluated"

    assert (tmp_path / "history" / "route2_test.json").is_file()
    assert (tmp_path / "reports" / "route2_test" / "facts.json").is_file()
    assert overview["changes"]["available"] is False


def test_second_run_compares_against_previous_history(tmp_path, finova_warehouse, config):
    assert run_route2(REQUEST, cfg=config, run_id="route2_a",
                      warehouse_path=finova_warehouse)["status"] == "success"
    state = run_route2(REQUEST, cfg=config, run_id="route2_b",
                       warehouse_path=finova_warehouse)
    assert state["status"] == "success"
    spec = json.loads((tmp_path / "public" / "finova.json").read_text(encoding="utf-8"))
    changes = spec["pages"][0]["changes"]
    assert changes["available"] is True
    assert changes["previous_run_id"] == "route2_a"
    statuses = {item["status"] for item in changes["items"]}
    assert statuses == {"stable"}


def _audited_copy(tmp_path, finova_warehouse, config):
    """Copie du warehouse avec kpi_values audite (approved) et un rapport d'audit minimal."""
    import shutil

    import duckdb

    from biflow.tools.audit_report import write_report

    first = run_route2(REQUEST, cfg=config, run_id="seed", warehouse_path=finova_warehouse)
    dataset = json.loads((tmp_path / "reports" / "seed" / "analysis_dataset.json").read_text(encoding="utf-8"))
    warehouse = tmp_path / "audited" / "warehouse.duckdb"
    warehouse.parent.mkdir()
    shutil.copyfile(finova_warehouse, warehouse)
    with duckdb.connect(str(warehouse)) as con:
        con.execute("CREATE TABLE kpi_values (kpi_id VARCHAR, iso3 VARCHAR, year INTEGER, value DOUBLE, "
                    "unit VARCHAR, publication_status VARCHAR, review_reasons VARCHAR[])")
        con.executemany("INSERT INTO kpi_values VALUES (?, ?, ?, ?, ?, 'approved', [])", [
            (row["kpi_id"], row["iso3"], row["year"], row["value"], row["unit"])
            for row in dataset["observations"] if row["year"] is not None])
    write_report({"run_id": "r1", "snapshot_id": "v1", "created_at": "2026-11-03T10:00:00",
                  "verdict": "pass", "counts": {"pass": 1, "warn": 0, "fail": 0}, "rows": 1,
                  "checks": [], "caveats": [], "publication": {"by_status": {}, "blocked_rows": []},
                  "decision_log": [], "examples": [], "timing_s": 0.1}, tmp_path / "audit")
    assert first["status"] == "success"
    return warehouse


def test_route2_insights_are_audited_into_the_audit_report(tmp_path, finova_warehouse, config):
    warehouse = _audited_copy(tmp_path, finova_warehouse, config)
    config["paths"]["audit"] = str(tmp_path / "audit")
    state = run_route2(REQUEST, cfg=config, run_id="route2_audit", warehouse_path=warehouse)
    assert state["status"] == "success", state.get("errors")
    claims = state["audit_insights"]
    assert claims and all(item["claims"] and item["insight_id"] for item in claims)
    assert isinstance(state["insights"], dict)  # cle du FinOVA Analyst inchangee
    report = json.loads((tmp_path / "audit" / "audit_report.json").read_text(encoding="utf-8"))
    block = report["route2_insight_audit"]
    assert block["run_id"] == "route2_audit" and block["audited"] == len(claims)
    assert block["accepted"] + block["rejected"] == block["audited"]
    assert block["not_auditable"] == len(block["not_auditable_ids"])
    assert block["accepted"] >= 1
    md = (tmp_path / "audit" / "audit_report.md").read_text(encoding="utf-8")
    assert "## Insights de la Route 2 (FinOVA Analyst)" in md
    # statut de publication fixe par l'Auditor, notice « non evalue » retiree
    spec = json.loads((tmp_path / "public" / "finova.json").read_text(encoding="utf-8"))
    assert spec["publication_status"] == "approved"
    assert "publication_not_evaluated" not in {notice["code"] for notice in spec["notices"]}
    assert state["route2_summary"]["publication_status"] == "approved"


def test_route2_never_writes_an_audit_report_without_audit_path(tmp_path, finova_warehouse, config):
    warehouse = _audited_copy(tmp_path, finova_warehouse, config)
    before = (tmp_path / "audit" / "audit_report.json").read_text(encoding="utf-8")
    state = run_route2(REQUEST, cfg=config, run_id="route2_noaudit", warehouse_path=warehouse)
    assert state["status"] == "success"
    assert any("paths.audit absent" in w for w in state["warnings"])
    assert (tmp_path / "audit" / "audit_report.json").read_text(encoding="utf-8") == before


def test_route2_agents_are_not_retried(tmp_path, finova_warehouse, config, monkeypatch):
    from biflow.agents.analyst import FinovaAnalystAgent

    calls = []

    def failing(self, ctx):
        calls.append(1)
        raise RuntimeError("panne analyste")

    monkeypatch.setattr(FinovaAnalystAgent, "execute", failing)
    state = run_route2(REQUEST, cfg=config, run_id="route2_fail", warehouse_path=finova_warehouse)
    assert state["status"] == "failed" and len(calls) == 1


def test_invalid_request_fails_before_running_agents(tmp_path, finova_warehouse, config):
    state = run_route2(
        {"iso3": ("TUN", "DZA", "EGY", "JOR", "MAR"), "mode": "year"},
        cfg=config, run_id="route2_bad", warehouse_path=finova_warehouse,
    )
    assert state["status"] == "failed"
    assert state["errors"]
    assert not (tmp_path / "public" / "finova.json").exists()
