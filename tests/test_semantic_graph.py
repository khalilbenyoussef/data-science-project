"""Opt-in orchestration parity; all database/report artifacts are temporary."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from biflow import graph
from biflow.agents.base import BaseAgent
from biflow.agents.semantic_kpi import SemanticKpiAgent
from biflow.semantic_graph import run_semantic_request
from biflow.state import new_state
from biflow.tools.semantic_kpi import RESPONSE_ADAPTER
from test_kpi import warehouse, provenance_files


@pytest.fixture(params=["langgraph", "sequential"])
def backend(request, monkeypatch):
    if request.param == "langgraph" and not graph.LANGGRAPH_AVAILABLE:
        pytest.skip("LangGraph unavailable")
    monkeypatch.setattr(graph, "LANGGRAPH_AVAILABLE", request.param == "langgraph")
    return request.param


@pytest.fixture
def setup_route(warehouse, tmp_path, monkeypatch, backend):
    def forbidden(*args, **kwargs):
        raise AssertionError("Semantic routing must not execute data agents or LLMs")
    for cls in graph.AGENT_CLASSES.values():
        monkeypatch.setattr(cls, "run", forbidden)
    monkeypatch.setattr("biflow.agents.base.build_agent_llm", forbidden)
    monkeypatch.setattr(BaseAgent, "ask_text", forbidden)
    monkeypatch.setattr(BaseAgent, "ask_json", forbidden)
    calls = []
    original = SemanticKpiAgent.run
    def recording(self, state):
        calls.append(deepcopy(state))
        assert self.cfg["llm"]["enabled"] is False
        return original(self, state)
    monkeypatch.setattr(SemanticKpiAgent, "run", recording)
    cfg = {"llm": {"enabled":True}, "paths": {
        "processed":str(warehouse.parent), "quality":str(tmp_path / "quality"),
        "reports":str(tmp_path / "reports")}}
    return cfg, calls


REQUESTS = [
    {"action":"list"},
    {"action":"describe", "kpi_id":"saving_rate"},
    {"action":"calculate", "kpi_id":"account_ownership", "iso3":"TUN", "year":2024},
    {"action":"latest_available", "kpi_id":"branch_density", "iso3":"TUN"},
    {"action":"compare_countries", "kpi_id":"unbanked_share", "left_iso3":"TUN", "right_iso3":"XKX", "year":2024},
    {"action":"compare_years", "kpi_id":"saving_rate", "iso3":"TUN", "left_year":2021, "right_year":2024},
]


@pytest.mark.parametrize("payload", REQUESTS)
def test_six_actions_graph_and_fallback_exactly_once(setup_route, payload):
    cfg, calls = setup_route
    before = deepcopy(cfg)
    result = graph.run_pipeline(cfg=cfg, run_id="query", semantic_kpi_request=payload)
    assert result["status"] == "success" and not result["errors"]
    assert len(calls) == 1 and cfg == before
    assert result["semantic_kpi_request"] == payload
    response = result["semantic_kpi_response"]
    assert response["action"] == payload["action"]
    RESPONSE_ADAPTER.validate_python(response)
    agent_report = json.loads((Path(cfg["paths"]["reports"]) / "query/semantic_kpi.json").read_text())
    assert response == agent_report["outputs"]["semantic_kpi_response"]
    assert result["warnings"] == agent_report["outputs"]["warnings"]
    assert len(result["warnings"]) == len(set(result["warnings"]))
    summary = json.loads((Path(cfg["paths"]["reports"]) / "query/run.json").read_text())
    assert summary["semantic_kpi_response"] == response
    assert summary["semantic_kpi_request"] == payload
    assert result["profiles"] == result["raw_paths"] == result["sources"] == {}


@pytest.mark.parametrize("payload", [None, {}, {"action":"unknown"},
    {"action":"calculate", "kpi_id":"account_ownership", "iso3":"TUN", "year":"2024"},
    {"action":"list", "publication_status":"approved"}])
def test_invalid_requests_fail_without_falling_into_pipeline(setup_route, payload):
    cfg, calls = setup_route
    result = graph.run_pipeline(cfg=cfg, semantic_kpi_request=payload)
    assert result["status"] == "failed" and result["errors"]
    assert not calls and "semantic_kpi_response" not in result


def test_unknown_kpi_is_an_agent_failure_without_retry(setup_route):
    cfg, calls = setup_route
    result = run_semantic_request({"action":"describe", "kpi_id":"unknown"}, cfg=cfg)
    assert result["status"] == "failed" and "Unknown KPI" in result["errors"][0]
    assert len(calls) == 1 and len(result["errors"]) == 1


def test_missing_warehouse_fails_calculation_but_allows_discovery(setup_route, tmp_path):
    cfg, calls = setup_route
    cfg["paths"]["processed"] = str(tmp_path / "nonexistent")
    result = run_semantic_request(REQUESTS[2], cfg=cfg)
    assert result["status"] == "failed" and "FileNotFoundError" in result["errors"][0]
    assert len(calls) == 1 and not (tmp_path / "nonexistent").exists()
    for payload in REQUESTS[:2]:
        result = run_semantic_request(payload, cfg=cfg)
        assert result["status"] == "success"
    assert len(calls) == 3


@pytest.mark.parametrize("selector", ["only", "start", "stop"])
def test_stage_conflicts_rejected_before_any_agent(setup_route, selector):
    cfg, calls = setup_route
    with pytest.raises(ValueError, match="cannot be combined"):
        graph.run_pipeline(cfg=cfg, semantic_kpi_request=REQUESTS[0], **{selector:"quality"})
    assert not calls


def test_path_binding_provenance_and_warnings(warehouse, provenance_files, setup_route):
    lineage, quality, write = provenance_files
    quality["diagnostics"] = [{"source":"findex", "iso3":"TUN", "year":2024,
        "indicator_code":"account_t_d", "code":"review_input", "reason":"Check source"}]
    write()
    cfg, calls = setup_route
    state = run_semantic_request(
        {"action":"calculate", "kpi_id":"unbanked_share", "iso3":"TUN", "year":2024},
        cfg=cfg, run_id="query_not_source_run", warehouse_path=warehouse,
        quality_report_path=warehouse.with_name("quality_report.json"),
        lineage_path=warehouse.with_name("lineage.json"))
    assert state["status"] == "success" and len(calls) == 1
    result = state["semantic_kpi_response"]["result"]
    assert result["provenance"]["run_id"] == lineage["run_id"] == "test_run"
    assert result["provenance"]["quality_association_status"] == "matches_lineage"
    assert result["provenance"]["raw_source_sha256"] == lineage["inputs"]["findex"]["sha256"]
    assert result["quality_warnings"] == result["dependency_results"][0]["quality_warnings"]
    assert len(result["quality_warnings"]) == 1 and result["requires_review"]
    assert result["publication_status"] == "not_evaluated"
    assert state["warnings"] == ["unresolved_input_quality_warning"]


def test_unavailable_is_success_not_quality_failed(setup_route):
    cfg, calls = setup_route
    state = run_semantic_request({**REQUESTS[2], "year":2023}, cfg=cfg)
    assert state["status"] == "success"
    assert state["semantic_kpi_response"]["result"]["availability_status"] == "unavailable"
    assert len(calls) == 1


def test_read_only_connections_and_warehouse_unchanged(setup_route, warehouse, monkeypatch):
    cfg, _ = setup_route
    digest = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    original = duckdb.connect
    def connect(*args, **kwargs):
        assert kwargs == {"read_only":True}
        return original(*args, **kwargs)
    monkeypatch.setattr(duckdb,"connect",connect)
    state = run_semantic_request(REQUESTS[4], cfg=cfg)
    assert state["status"] == "success"
    assert hashlib.sha256(warehouse.read_bytes()).hexdigest() == digest


def test_bad_response_is_failed_not_retried(setup_route, monkeypatch):
    cfg, calls = setup_route
    def invalid(self, ctx):
        return {"semantic_kpi_response":{"action":"list", "kpis":[]}, "warnings":[]}
    monkeypatch.setattr(SemanticKpiAgent,"execute",invalid)
    state = run_semantic_request(REQUESTS[0], cfg=cfg)
    assert state["status"] == "failed" and len(calls) == 1
    assert "semantic_kpi_response" not in state


def test_normal_pipeline_still_runs_original_order(tmp_path, monkeypatch, backend):
    calls = []
    class FakeAgent:
        def __init__(self, name): self.name = name
        def run(self, state):
            calls.append(self.name)
            outputs = {"quality":{"passed":True}} if self.name == "quality" else {}
            return {"status":"success", "outputs":outputs}
    for name in graph.STEP_ORDER:
        monkeypatch.setitem(graph.AGENT_CLASSES,name,lambda name=name, **kwargs:FakeAgent(name))
    state = graph.run_pipeline(cfg={"paths":{"reports":str(tmp_path)}}, use_llm=False)
    assert calls == graph.STEP_ORDER == ["collector","profiler","quality","etl"]
    assert state["status"] == "success" and "semantic_kpi_request" not in state
    assert "semantic_kpi_response" not in graph._summary(state)
    assert graph._gate({"quality":{"passed":True}}) == "etl"
    assert graph._gate({"quality":{"passed":False}}) == graph.END


def test_optional_semantic_channels_do_not_change_defaults():
    state = new_state("baseline")
    assert "semantic_kpi_request" not in state and "semantic_kpi_response" not in state
    assert "lineage_path" not in state
    assert "semantic_kpi_request" not in graph._summary(state)
