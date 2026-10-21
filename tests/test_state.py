from __future__ import annotations

from biflow.agents.base import BaseAgent
from biflow.state import add_error, add_warning, merge, new_state


class DummyAgent(BaseAgent):
    name = "dummy"

    def execute(self, ctx):
        return {"received_objective": ctx.get("objective"), "rows": 3}


def test_new_state_defaults():
    state = new_state("Tester le pipeline", run_id="run_test")

    assert state["run_id"] == "run_test"
    assert state["status"] == "running"
    assert state["warnings"] == []
    assert state["errors"] == []


def test_merge_does_not_mutate_and_lists_are_independent():
    state = new_state("objectif", run_id="r1")
    merged = merge(state, {"profiles": {"findex": {"rows": 10}}})

    assert "profiles" in merged
    assert merged["profiles"] == {"findex": {"rows": 10}}
    assert state["profiles"] == {}

    add_warning(merged, "attention")
    add_error(merged, "erreur")
    assert merged["warnings"] == ["attention"]
    assert merged["errors"] == ["erreur"]
    assert state["warnings"] == []


def test_base_agent_writes_report(tmp_path):
    cfg = {"paths": {"reports": str(tmp_path)}}
    agent = DummyAgent(cfg=cfg, run_id="run_test")

    report = agent.run({"objective": "objectif de test"})

    assert report["status"] == "success"
    assert report["agent"] == "dummy"
    assert report["outputs"]["received_objective"] == "objectif de test"

    report_path = tmp_path / "run_test" / "dummy.json"
    assert report_path.exists()


def test_base_agent_captures_failure(tmp_path):
    class FailingAgent(BaseAgent):
        name = "failing"

        def execute(self, ctx):
            raise RuntimeError("boum")

    agent = FailingAgent(cfg={"paths": {"reports": str(tmp_path)}}, run_id="run_fail")
    report = agent.run({})

    assert report["status"] == "failed"
    assert "boum" in report["errors"][0]
