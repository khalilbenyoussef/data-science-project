"""Frise des agents et relance de la demonstration (page « Sources et qualité »)."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from biflow.config import load_config
from biflow.tools import deliverables as dl
from biflow.tools.user_sources.jobs import STEPS, JobManager
from dashboard_app.api.pipeline import create_pipeline_router


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _agent(name: str, outputs: dict, duration: float = 1.0) -> dict:
    return {"agent": name, "started_at": "2026-11-05T10:00:00", "duration_s": duration, "status": "success",
            "outputs": outputs, "warnings": [], "errors": [], "llm_usage": {}}


@pytest.fixture
def env(tmp_path):
    reports = tmp_path / "reports"
    full = reports / "full_run"
    _write(full / "run.json", {"run_id": "full_run", "status": "success", "profiles": {"fas": {"rows": 10}}})
    for step in dl.ROUTE1:
        _write(full / f"{step}.json", _agent(step, {"quality": {"overall_score": 0.9, "passed": True}}
                                         if step == "quality" else {}, duration=0.5))
    route2 = reports / "route2_x"
    _write(route2 / "run.json", {"run_id": "route2_x", "status": "success"})
    _write(route2 / "analyst.json", _agent("analyst", {"analyst_summary": {"facts": 96, "insights": 17}}))
    _write(route2 / "dashboard_spec.json", _agent("dashboard_spec", {"dashboard_spec_summary": {"pages": 6}}))
    _write(route2 / "finova_spec.json", {})
    demo = reports / "demo_run"
    _write(demo / "run.json", {"run_id": "demo_run", "status": "no_change",
                               "snapshot": {"status": "no_change", "snapshot_id": "v5"}})
    _write(demo / "collector.json", _agent("collector", {"raw_paths": {"fas": "x"}}, duration=0.2))
    _write(demo / "snapshot.json", _agent("snapshot", {"snapshot": {"status": "no_change", "snapshot_id": "v5"}}))
    _write(tmp_path / "audit" / "audit_report.json", {"run_id": "full_run", "snapshot_id": "v5"})
    _write(tmp_path / "finova.json", {"run_id": "route2_x"})
    cfg = load_config()
    cfg["paths"] = {**cfg["paths"], "reports": str(reports), "audit": str(tmp_path / "audit"),
                    "quality": str(tmp_path / "quality"), "processed": str(tmp_path / "processed")}
    cfg["dashboard"] = {**cfg["dashboard"], "spec_output": str(tmp_path / "finova.json")}
    release = threading.Event()

    def runner(job, update):
        update(step="collector")
        release.wait(5)
        update(status="success", steps_done=["collector", "snapshot"], step=None, no_change=True,
               skipped=[s for s in STEPS if s not in ("collector", "snapshot")], run_id="demo_run",
               message="Aucune donnée nouvelle")

    jobs = JobManager(tmp_path / "jobs", timeout_s=60, runner=runner)
    app = FastAPI()
    app.include_router(create_pipeline_router(
        context=lambda: dl.load_context(cfg, evaluation_dir=tmp_path / "e", manual_path=tmp_path / "m.yaml"),
        jobs=jobs))
    return TestClient(app), jobs, release


def test_timeline_lists_every_agent_of_the_last_run(env):
    client, _, _ = env
    body = client.get("/api/pipeline/agents").json()
    assert (body["route1_run_id"], body["route2_run_id"], body["snapshot_id"]) == ("full_run", "route2_x", "v5")
    agents = {a["id"]: a for a in body["agents"]}
    assert [a["id"] for a in body["agents"]] == [a["id"] for a in dl.AGENTS]
    assert agents["etl"]["status"] == "success" and agents["etl"]["duration_s"] == 0.5
    assert agents["etl"]["llm"] is False and agents["auditor"]["llm"] is True
    assert agents["analyst"]["key_output"].startswith("17 constats sur 96 faits")
    assert agents["ask"]["status"] == "on_demand"
    assert body["active_job"] is None


def test_timeline_of_a_no_change_run_marks_skipped_agents(env):
    client, _, _ = env
    body = client.get("/api/pipeline/agents", params={"run_id": "demo_run"}).json()
    agents = {a["id"]: a for a in body["agents"]}
    assert body["no_change"] is True
    assert agents["collector"]["status"] == "success" and agents["snapshot"]["status"] == "success"
    for step in ("profiler", "quality", "etl", "semantic_kpi", "auditor", "analyst", "dashboard_spec"):
        assert agents[step]["status"] == "skipped", step
        assert agents[step]["note"] == "ignoré : aucune donnée nouvelle"


@pytest.mark.parametrize("run_id", ["../etc", "a b", "x" * 81])
def test_timeline_rejects_invalid_run_ids(env, run_id):
    client, _, _ = env
    assert client.get("/api/pipeline/agents", params={"run_id": run_id}).status_code in (400, 422)
    assert client.get("/api/pipeline/agents", params={"run_id": "absent"}).status_code == 404


def test_demo_starts_the_job_and_refuses_a_second_one(env):
    client, jobs, release = env
    first = client.post("/api/pipeline/demo")
    assert first.status_code == 200
    job_id = first.json()["job_id"]
    second = client.post("/api/pipeline/demo")
    assert second.status_code == 409
    assert client.get("/api/pipeline/agents").json()["active_job"]["job_id"] == job_id
    release.set()
    for _ in range(100):
        job = jobs.get(job_id)
        if job["status"] == "success":
            break
        time.sleep(0.05)
    assert job["kind"] == "demo" and job["no_change"] is True
    assert "profiler" in job["skipped"] and "route2" in job["skipped"]


def test_runner_marks_skipped_agents_when_nothing_changed(tmp_path, monkeypatch):
    from biflow.tools.user_sources import jobs as jobs_module

    cfg = load_config()
    cfg["paths"] = {**cfg["paths"], "reports": str(tmp_path / "reports")}
    calls = []

    def fake_stream(command, deadline, update, state, on_line):
        calls.append(command)
        run_id = command[command.index("--run-id") + 1]
        assert run_id.startswith("demo_") and "--offline-official" in command and "--no-llm" in command
        folder = tmp_path / "reports" / run_id
        _write(folder / "run.json", {"run_id": run_id, "status": "no_change",
                                     "snapshot": {"status": "no_change", "snapshot_id": "v5"}})
        for step in ("collector", "snapshot"):
            _write(folder / f"{step}.json", _agent(step, {}))
        return 0, []

    monkeypatch.setattr(jobs_module, "_stream", fake_stream)
    job = {"job_id": "x", "kind": "demo", "source": "", "status": "running", "step": None, "steps_done": []}
    updates = {}
    jobs_module.pipeline_runner(cfg, 60)(job, lambda **fields: updates.update(fields))
    assert len(calls) == 1  # pas de Route 2 sans donnee nouvelle
    assert updates["status"] == "success" and updates["no_change"] is True
    assert updates["steps_done"] == ["collector", "snapshot"]
    assert updates["skipped"] == ["profiler", "quality", "etl", "semantic_kpi", "auditor", "route2"]
    assert updates["message"].startswith("Aucune donnée nouvelle")
