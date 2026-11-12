"""Retry de l'orchestrateur (agents factices, aucun reseau ni donnee reelle)."""
from __future__ import annotations

import json

import pytest

from biflow import graph


class _Agent:
    def __init__(self, name, script):
        self.name, self.script = name, script

    def run(self, state):
        self.script["calls"].append(self.name)
        failures = self.script["fail"].get(self.name, 0)
        if failures:
            self.script["fail"][self.name] = failures - 1
            return {"status": "failed", "outputs": {}, "errors": [f"RuntimeError: panne {self.name}"]}
        outputs = {"quality": {"passed": self.script["passed"]}} if self.name == "quality" else {}
        if self.name == "collector":
            outputs["raw_meta"] = {"findex": {"sha256": "a" * 64}}
        if self.name == "etl":
            outputs["warehouse_path"] = "warehouse.duckdb"
        return {"status": "success", "outputs": outputs, "errors": []}


@pytest.fixture(params=["langgraph", "sequential"])
def pipeline(request, monkeypatch, tmp_path):
    if request.param == "langgraph" and not graph.LANGGRAPH_AVAILABLE:
        pytest.skip("LangGraph unavailable")
    monkeypatch.setattr(graph, "LANGGRAPH_AVAILABLE", request.param == "langgraph")
    sleeps = []
    monkeypatch.setattr(graph.time, "sleep", sleeps.append)
    script = {"calls": [], "fail": {}, "passed": True}
    for name in graph.STEP_ORDER:
        monkeypatch.setitem(graph.AGENT_CLASSES, name, lambda name=name, **kw: _Agent(name, script))
    cfg = {"paths": {"reports": str(tmp_path)},
           "orchestrator": {"max_retries": 1, "retry_backoff_s": 0.5}}

    def run(**kwargs):
        state = graph.run_pipeline(cfg=cfg, run_id="retry", use_llm=False, **kwargs)
        summary = json.loads((tmp_path / "retry" / "run.json").read_text(encoding="utf-8"))
        return state, summary

    return script, sleeps, run, cfg


def test_transient_failure_succeeds_on_retry(pipeline):
    script, sleeps, run, _ = pipeline
    script["fail"]["etl"] = 1
    state, summary = run()
    assert state["status"] == "success"
    assert script["calls"] == ["collector", "snapshot", "profiler", "quality", "etl", "etl", "semantic_kpi", "auditor"]
    etl = [a for a in summary["attempts"] if a["step"] == "etl"]
    assert [(a["attempt"], a["status"]) for a in etl] == [(1, "failed"), (2, "success")]
    assert "panne etl" in etl[0]["errors"][0]
    assert sleeps == [0.5]
    assert not state["errors"]
    assert any("tentative 2/2" in w and "panne etl" in w for w in state["warnings"])
    assert state["warehouse_path"] == "warehouse.duckdb"


def test_persistent_failure_stops_with_both_attempts_logged(pipeline):
    script, sleeps, run, _ = pipeline
    script["fail"]["etl"] = 2
    state, summary = run()
    assert state["status"] == "failed"
    assert script["calls"] == ["collector", "snapshot", "profiler", "quality", "etl", "etl"]  # pas de KPI
    assert state["errors"] == ["[etl] tentative 1/2 : RuntimeError: panne etl",
                               "[etl] tentative 2/2 : RuntimeError: panne etl"]
    assert summary["errors"] == state["errors"] and summary["status"] == "failed"
    etl = [a for a in summary["attempts"] if a["step"] == "etl"]
    assert [(a["attempt"], a["status"]) for a in etl] == [(1, "failed"), (2, "failed")]
    # Les sorties des etapes reussies sont conservees
    assert state["raw_meta"] == {"findex": {"sha256": "a" * 64}}
    assert state["quality"] == {"passed": True}
    assert summary["quality"]["passed"] is True


def test_quality_gate_fail_is_a_decision_never_retried(pipeline):
    script, sleeps, run, _ = pipeline
    script["passed"] = False
    state, summary = run()
    assert state["status"] == "quality_failed"
    assert script["calls"] == ["collector", "snapshot", "profiler", "quality"]
    assert [a["step"] for a in summary["attempts"]] == ["collector", "snapshot", "profiler", "quality"]
    assert sleeps == [] and not state["errors"]


def test_max_retries_is_configurable(pipeline):
    script, sleeps, run, cfg = pipeline
    cfg["orchestrator"]["max_retries"] = 0
    script["fail"]["collector"] = 1
    state, summary = run()
    assert state["status"] == "failed" and script["calls"] == ["collector"]
    assert state["errors"] == ["[collector] tentative 1/1 : RuntimeError: panne collector"]
    assert sleeps == []


def test_failed_quality_agent_error_is_retried(pipeline):
    script, _, run, _ = pipeline
    script["fail"]["quality"] = 1
    state, _ = run()
    assert state["status"] == "success"
    assert script["calls"].count("quality") == 2
