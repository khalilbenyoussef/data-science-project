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


def test_invalid_request_fails_before_running_agents(tmp_path, finova_warehouse, config):
    state = run_route2(
        {"iso3": ("TUN", "DZA", "EGY", "JOR", "MAR"), "mode": "year"},
        cfg=config, run_id="route2_bad", warehouse_path=finova_warehouse,
    )
    assert state["status"] == "failed"
    assert state["errors"]
    assert not (tmp_path / "public" / "finova.json").exists()
