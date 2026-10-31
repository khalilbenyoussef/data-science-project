"""Route 2 orchestration: isolated from Route 1, deterministic, no LLM."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from biflow import graph as pipeline_graph
from biflow.analysis_graph import AGENTS, STAGES, run_analysis_pipeline
from biflow.agents.bi_analyst import BiAnalystAgent
from biflow.agents.dashboard import DashboardAgent
from biflow.state import new_state
from test_kpi import warehouse, provenance_files


@pytest.fixture(params=["langgraph", "sequential"])
def backend(request, monkeypatch):
    if request.param == "langgraph" and not pipeline_graph.LANGGRAPH_AVAILABLE:
        pytest.skip("LangGraph unavailable")
    monkeypatch.setattr(
        pipeline_graph, "LANGGRAPH_AVAILABLE", request.param == "langgraph")
    return request.param


def recorder(env, cls):
    calls = []
    original = cls.run

    def recording(self, state):
        calls.append(deepcopy(state))
        return original(self, state)

    env["monkeypatch"].setattr(cls, "run", recording)
    return calls


@pytest.fixture
def env(warehouse, provenance_files, tmp_path, monkeypatch, backend):
    _, _, write = provenance_files
    write()

    def forbidden(*args, **kwargs):
        raise AssertionError("Route 2 must not execute Route 1 agents or an LLM")

    for name in pipeline_graph.AGENT_CLASSES:
        monkeypatch.setattr(pipeline_graph.AGENT_CLASSES[name], "run", forbidden)
    monkeypatch.setattr("biflow.agents.base.build_agent_llm", forbidden)

    cfg = {
        "llm": {"enabled": True},
        "paths": {
            "processed": str(warehouse.parent),
            "quality": str(tmp_path / "quality"),
            "reports": str(tmp_path / "reports"),
        },
        "dashboard": {"data_output": str(tmp_path / "public" / "dashboard.json")},
    }
    return {
        "cfg": cfg,
        "warehouse": warehouse,
        "tmp": tmp_path,
        "monkeypatch": monkeypatch,
        "kwargs": {
            "warehouse_path": warehouse,
            "lineage_path": warehouse.with_name("lineage.json"),
            "quality_report_path": warehouse.with_name("quality_report.json"),
        },
    }


PAYLOAD = {"iso3": ["TUN", "XKX"], "kpi_ids": ["account_ownership", "saving_rate"]}


def run(env, payload=PAYLOAD, run_id="route2", **overrides):
    options = {
        "cfg": env["cfg"], "run_id": run_id, "stage": "all",
        **env["kwargs"], **overrides,
    }
    return run_analysis_pipeline(payload, **options)


def test_full_route_writes_every_artifact(env):
    analyst_calls = recorder(env, BiAnalystAgent)
    state = run(env)
    assert state["status"] == "success" and not state["errors"]
    assert len(analyst_calls) == 1
    assert "analysis_report" not in analyst_calls[0]

    assert state["analysis_request"] == {
        "action": "analyze", "iso3": ["TUN", "XKX"],
        "kpi_ids": ["account_ownership", "saving_rate"], "mode": "latest",
        "year": None, "reference_iso3": None, "include_series": True,
        "trend_years": None, "top_n": 10,
    }
    assert state["analysis_report"]["summary"]["selected_observations"] == 4
    assert state["analysis_report"]["publication_status"] == "not_evaluated"

    reports = Path(env["tmp"], "reports", "route2")
    for name in ("analysis_dataset.json", "bi_analyst.json", "bi_analyst.md",
                 "dashboard.json", "dashboard_data.json", "run.json"):
        assert (reports / name).is_file(), name
    public = Path(env["cfg"]["dashboard"]["data_output"])
    assert public.is_file()
    dashboard = json.loads(public.read_text(encoding="utf-8"))
    assert len(dashboard["cards"]) == 4
    assert dashboard["summary"] == state["analysis_report"]["summary"]
    assert state["dashboard_paths"]["public"] == str(public)

    summary = json.loads((reports / "run.json").read_text(encoding="utf-8"))
    assert summary["stage"] == "all"
    assert summary["analysis_request"] == state["analysis_request"]
    assert summary["analysis_summary"] == state["analysis_report"]["summary"]
    assert summary["dashboard_paths"] == state["dashboard_paths"]
    assert summary["dashboard_summary"] == state["dashboard_summary"]
    assert summary["status"] == "success"
    assert summary["finished_at"]
    assert (reports / "bi_analyst.md").read_text(encoding="utf-8").startswith(
        "# Rapport BI Analyst")


def test_route_two_forces_llm_off_and_never_touches_route_one(env, monkeypatch):
    self_cfgs = []
    original = BiAnalystAgent.run

    def capture(self, state):
        self_cfgs.append(deepcopy(self.cfg))
        return original(self, state)

    monkeypatch.setattr(BiAnalystAgent, "run", capture)
    before = deepcopy(env["cfg"])
    state = run(env)
    assert state["status"] == "success"
    assert self_cfgs and all(cfg["llm"]["enabled"] is False for cfg in self_cfgs)
    assert env["cfg"] == before
    assert pipeline_graph.STEP_ORDER == ["collector", "profiler", "quality", "etl"]
    assert set(AGENTS) == {"bi_analyst", "dashboard"}


def test_invalid_request_fails_before_any_agent(env):
    calls = recorder(env, BiAnalystAgent)
    state = run(env, payload={"iso3": ["TUN"], "kpi_ids": ["unknown"]}, run_id="invalid")
    assert state["status"] == "failed" and state["errors"]
    assert "ValidationError" in state["errors"][0]
    assert not calls
    assert "analysis_request" not in state
    assert "analysis_report" not in state
    summary = json.loads(Path(
        env["tmp"], "reports", "invalid", "run.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert summary["analysis_request"] is None


@pytest.mark.parametrize("stage,analyst,dashboard", [
    ("analyst", True, False),
    ("dashboard", False, True),
    ("all", True, True),
])
def test_stages_only_run_selected_agents(env, stage, analyst, dashboard):
    analyst_calls = recorder(env, BiAnalystAgent)
    dashboard_calls = recorder(env, DashboardAgent)
    state = run(env, run_id=f"stage_{stage}", stage=stage)
    assert state["status"] == "success"
    assert len(analyst_calls) == int(analyst)
    assert len(dashboard_calls) == int(dashboard)
    assert ("analysis_report" in state) is analyst
    assert ("dashboard_paths" in state) is dashboard
    reports = Path(env["tmp"], "reports", f"stage_{stage}")
    assert (reports / "analysis_dataset.json").is_file()
    assert (reports / "bi_analyst.json").is_file() is analyst
    assert (reports / "dashboard.json").is_file() is dashboard


def test_unknown_stage_is_rejected_before_agents(env):
    calls = recorder(env, BiAnalystAgent)
    with pytest.raises(ValueError, match="unknown stage"):
        run(env, stage="everything")
    assert not calls


def test_dashboard_failure_fails_run_without_retry(env, monkeypatch):
    calls = []

    def failing(self, ctx):
        calls.append(ctx)
        raise RuntimeError("dashboard exploded")

    monkeypatch.setattr(DashboardAgent, "execute", failing)
    state = run(env, run_id="failure")
    assert state["status"] == "failed" and len(calls) == 1
    assert any("dashboard exploded" in error for error in state["errors"])
    assert Path(env["tmp"], "reports", "failure", "bi_analyst.json").is_file()
    assert "dashboard_paths" not in state
    assert not Path(env["cfg"]["dashboard"]["data_output"]).exists()


def test_run_without_warehouse_fails_cleanly(env):
    state = run(
        env, run_id="missing_db",
        warehouse_path=Path(env["tmp"], "absent", "warehouse.duckdb"),
        lineage_path=Path(env["tmp"], "absent", "lineage.json"),
        quality_report_path=Path(env["tmp"], "absent", "quality.json"),
    )
    assert state["status"] == "failed" and state["errors"]
    assert not Path(env["tmp"], "absent", "warehouse.duckdb").exists()


def test_route_one_state_has_no_route_two_channels():
    state = new_state("baseline")
    for key in ("analysis_request", "analysis_report", "analysis_dataset_path",
                "dashboard_paths", "dashboard_summary"):
        assert key not in state
    assert "analysis_request" not in pipeline_graph._summary(state)
