"""BI Analyst findings are deterministic, evidence-bound and LLM-free."""
import json
from pathlib import Path

import pytest

from biflow.agents.bi_analyst import (
    LIMITATIONS, BiAnalystAgent, build_findings, render_markdown,
)
from biflow.tools.analysis import AnalysisService
from test_kpi import warehouse, provenance_files


@pytest.fixture
def env(warehouse, provenance_files, tmp_path):
    _, _, write = provenance_files
    write()
    cfg = {"paths": {"reports": str(tmp_path / "reports")}}
    kwargs = {
        "cfg": cfg,
        "warehouse_path": warehouse,
        "lineage_path": warehouse.with_name("lineage.json"),
        "quality_report_path": warehouse.with_name("quality_report.json"),
    }
    return cfg, kwargs, warehouse


def run_agent(env, payload, run_id="agent_run"):
    _, kwargs, _ = env
    return BiAnalystAgent(run_id=run_id, **kwargs).run({"analysis_request": payload})


def test_agent_writes_evidence_backed_report_and_markdown(env):
    cfg, _, warehouse = env
    request = {"iso3": ["TUN", "XKX"], "kpi_ids": ["account_ownership", "saving_rate"]}
    report = run_agent(env, request)
    assert report["status"] == "success" and not report["errors"]
    assert report["llm_usage"] == {}

    outputs = report["outputs"]
    dataset = json.loads(Path(outputs["analysis_dataset_path"]).read_text(encoding="utf-8"))
    analyst = outputs["analysis_report"]
    assert analyst["agent"] == "bi_analyst"
    assert analyst["publication_status"] == "not_evaluated"
    assert analyst["limitations"] == LIMITATIONS
    assert analyst["summary"]["selected_observations"] == 4
    assert analyst["summary"]["available"] == 3
    assert analyst["summary"]["unavailable"] == 1
    assert analyst["summary"]["findings"]["total"] == len(analyst["findings"])

    known = (
        {row["evidence_id"] for row in dataset["observations"]}
        | {row["evidence_id"] for ranking in dataset["rankings"] for row in ranking["rows"]}
        | {point["evidence_id"] for series in dataset["series"] for point in series["points"]}
        | {item for trend in dataset["trends"] for item in trend["evidence_ids"]}
        | {row["evidence_id"] for comparison in dataset["comparisons"] for row in comparison["rows"]}
    )
    assert analyst["findings"]
    assert [finding["id"] for finding in analyst["findings"]] == [
        f"F-{index:03d}" for index in range(1, len(analyst["findings"]) + 1)
    ]
    for finding in analyst["findings"]:
        assert finding["evidence_ids"] and set(finding["evidence_ids"]) <= known
        assert finding["severity"] in {"review", "warning", "info"}

    markdown = Path(cfg["paths"]["reports"], "agent_run", "bi_analyst.md")
    text = markdown.read_text(encoding="utf-8")
    assert text.startswith("# Rapport BI Analyst")
    assert "## Limites" in text and "## Provenance" in text
    assert "non évalué" in text or "not_evaluated" in text
    assert not markdown.with_name("bi_analyst.md.tmp").exists()

    saved = json.loads(Path(
        cfg["paths"]["reports"], "agent_run", "bi_analyst.json").read_text(encoding="utf-8"))
    assert saved["outputs"]["analysis_report"] == analyst
    assert saved["llm_usage"] == {}
    assert warehouse.is_file()


def test_agent_never_builds_an_llm(env, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("BI Analyst must not instantiate an LLM")

    monkeypatch.setattr("biflow.agents.base.build_agent_llm", forbidden)
    report = run_agent(env, {"iso3": ["TUN"], "kpi_ids": ["account_ownership"]})
    assert report["status"] == "success"
    agent = BiAnalystAgent(run_id="x", **env[1])
    assert agent.get_llm() is None
    assert "deterministic" in agent.llm_error


def test_findings_are_deterministic_across_runs(env):
    payload = {"iso3": ["TUN", "XKX"], "kpi_ids": ["account_ownership", "saving_rate"]}
    first = run_agent(env, payload, run_id="first")["outputs"]["analysis_report"]["findings"]
    second = run_agent(env, payload, run_id="second")["outputs"]["analysis_report"]["findings"]
    assert first == second


def test_unavailable_and_provisional_observations_are_flagged(env):
    report = run_agent(env, {"iso3": ["TUN"], "kpi_ids": ["saving_rate", "borrowing_rate"]})
    findings = report["outputs"]["analysis_report"]["findings"]
    codes = {finding["code"] for finding in findings}
    assert "requires_review" in codes
    assert "provisional_definition" in codes
    review = [item for item in findings if item["code"] == "requires_review"]
    assert len(review) == 2
    assert all("revue requise" in item["statement"] for item in review)

    unavailable = run_agent(env, {"iso3": ["FRA"], "kpi_ids": ["account_ownership"]})
    findings = unavailable["outputs"]["analysis_report"]["findings"]
    finding = next(item for item in findings if item["code"] == "unavailable")
    assert finding["severity"] == "warning"
    assert "indisponible" in finding["statement"]
    assert finding["evidence_ids"] == ["EV-account_ownership-FRA-NA"]


def test_top_n_truncates_per_code_and_emits_marker(env):
    report = run_agent(
        env, {"iso3": ["TUN"], "kpi_ids": ["saving_rate", "borrowing_rate"], "top_n": 1},
    )
    findings = report["outputs"]["analysis_report"]["findings"]
    assert sum(1 for item in findings if item["code"] == "requires_review") == 1
    assert any(item["code"] == "requires_review_truncated" for item in findings)
    assert all(
        item["severity"] == "info"
        for item in findings if item["code"].endswith("_truncated")
    )


def test_markdown_escapes_absence_instead_of_printing_zero(env):
    report = run_agent(env, {"iso3": ["FRA"], "kpi_ids": ["account_ownership"]})
    dataset = json.loads(Path(
        report["outputs"]["analysis_dataset_path"]).read_text(encoding="utf-8"))
    text = render_markdown(report["outputs"]["analysis_report"], dataset)
    assert "| FRA | indisponible |" in text
    assert "| 0.00" not in text


def test_invalid_request_fails_without_partial_markdown(env):
    cfg, _, _ = env
    report = run_agent(env, {"iso3": ["TUN"], "kpi_ids": ["unknown"]}, run_id="bad")
    assert report["status"] == "failed" and report["errors"]
    assert "ValidationError" in report["errors"][0]
    assert report["outputs"] == {}
    assert not Path(cfg["paths"]["reports"], "bad", "bi_analyst.md").exists()
    assert Path(cfg["paths"]["reports"], "bad", "bi_analyst.json").is_file()


def test_agent_reuses_existing_dataset_without_rebuilding(env, monkeypatch):
    _, kwargs, _ = env
    report = run_agent(env, {"iso3": ["TUN"], "kpi_ids": ["account_ownership"]}, run_id="once")
    path = report["outputs"]["analysis_dataset_path"]

    agent = BiAnalystAgent(run_id="twice", **kwargs)
    monkeypatch.setattr(
        AnalysisService, "build",
        lambda *args, **k: (_ for _ in ()).throw(AssertionError("must not rebuild")),
    )
    report = agent.run({
        "analysis_request": {"iso3": ["TUN"], "kpi_ids": ["account_ownership"]},
        "analysis_dataset_path": path,
    })
    assert report["status"] == "success"
    assert report["outputs"]["analysis_dataset_path"] == path
