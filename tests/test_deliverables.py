"""Livrables ecrits (scripts/build_deliverables.py) : chiffres lus, jamais saisis."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

from biflow.config import ROOT, load_config
from biflow.tools import deliverables as dl

sys.path.insert(0, str(ROOT / "scripts"))
import build_deliverables  # noqa: E402


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _cfg(tmp_path: Path) -> dict:
    cfg = load_config()
    cfg["paths"] = {**cfg["paths"], "reports": str(tmp_path / "reports"), "audit": str(tmp_path / "audit"),
                    "quality": str(tmp_path / "quality"), "processed": str(tmp_path / "processed")}
    cfg["dashboard"] = {**cfg["dashboard"], "spec_output": str(tmp_path / "finova.json")}
    return cfg


def _agent(name: str, outputs: dict, duration: float = 1.5, usage: dict | None = None) -> dict:
    return {"agent": name, "run_id": "r1", "started_at": "2026-11-01T10:00:00", "duration_s": duration,
            "status": "success", "outputs": outputs, "warnings": [], "errors": [], "llm_usage": usage or {}}


@pytest.fixture
def ctx(tmp_path):
    cfg = _cfg(tmp_path)
    run = tmp_path / "reports" / "r1"
    _write(run / "run.json", {"run_id": "r1", "status": "success",
                              "profiles": {"findex": {"rows": 123, "cols": 7}, "fas": {"rows": 77, "cols": 9}}})
    _write(run / "quality.json", _agent("quality", {"quality": {"overall_score": 0.812, "passed": True}},
                                        usage={"calls": 2, "total_tokens": 345}))
    _write(run / "semantic_kpi.json", _agent("semantic_kpi", {"kpi_summary": {
        "rows": 4321, "kpis": 44, "available": 4000, "requires_review": 21}}, duration=3.25))
    _write(run / "auditor.json", _agent("auditor", {"audit": {"verdict": "pass", "rows": 4321,
                                                               "counts": {"pass": 18, "warn": 1, "fail": 0}}}))
    _write(tmp_path / "audit" / "audit_report.json", {"run_id": "r1", "snapshot_id": "v9", "verdict": "pass",
                                                      "rows": 4321, "checks": []})
    _write(tmp_path / "quality" / "quality_report.json", {
        "run_id": "r1", "snapshot_id": "v9", "created_at": "2026-11-01T10:00:00", "overall_score": 0.812,
        "passed": True, "critical_issues": 0, "issue_counts": {"medium": 3},
        "checks": {"fas": {"rows": 77, "cols": 9, "score": 0.654, "gate": True, "issues": [{}],
                           "metrics": {"duplicates": 5, "missing_cells_pct": 12.34}}},
        "issues": [{"source": "fas", "code": "negative_values", "severity": "medium", "message": "m", "count": 6}],
        "diagnostics": [], "user_sources": {}, "excluded_sources": [{"source": "maison", "reason": "gate"}]})
    return dl.load_context(cfg, evaluation_dir=tmp_path / "evaluation", manual_path=tmp_path / "none.yaml")


def test_header_carries_run_snapshot_and_catalog(ctx):
    text = dl.render_quality(ctx)
    assert "`r1`" in text and "`v9`" in text
    assert f"Version du catalogue KPI** : {ctx.catalog['catalog_version']}" in text
    assert text.startswith("# Rapport de qualité des données")


def test_quality_numbers_come_from_the_report(ctx):
    text = dl.render_quality(ctx)
    for expected in ("0.812", "0.654", "12.34 %", "| fas | 77 | 9 | 5 |", "Anomalies moyennes | 3", "maison"):
        assert expected in text


def test_missing_inputs_say_non_disponible(tmp_path):
    ctx = dl.load_context(_cfg(tmp_path), evaluation_dir=tmp_path / "e", manual_path=tmp_path / "m.yaml")
    assert "Rapport qualité non disponible" in dl.render_quality(ctx)
    assert ctx.run_id == dl.NA
    rows = {a["id"]: a for a in dl.agent_summaries(ctx)}
    assert rows["etl"]["duration_s"] is None and rows["etl"]["key_output"] == dl.NA


def test_agent_summaries_read_durations_outputs_and_llm(ctx):
    rows = {a["id"]: a for a in dl.agent_summaries(ctx)}
    assert [a["id"] for a in dl.AGENTS][:7] == dl.ROUTE1
    assert rows["semantic_kpi"]["duration_s"] == 3.25
    assert "4 321 lignes kpi_values" in rows["semantic_kpi"]["key_output"]
    assert rows["quality"]["metrics"]["score"] == 0.812
    assert rows["quality"]["llm_measured"] == "2 appel(s), 345 jetons"
    assert rows["auditor"]["llm_measured"] == "0 appel"
    assert rows["auditor"]["metrics"]["verdict"] == "pass"
    assert rows["profiler"]["status"] is None  # absent du run : rien d'invente


def test_llm_mode_follows_code_and_config():
    cfg = load_config()
    assert dl.llm_mode("etl", cfg) == "déterministe"
    assert dl.llm_mode("collector", cfg) == "déterministe"
    assert dl.llm_mode("auditor", cfg).startswith("déterministe + LLM optionnel")
    assert dl.llm_mode("analyst", {**cfg, "analyst": {"narrate": False}}).startswith("déterministe (narration")
    assert dl.llm_mode("quality", {**cfg, "llm": {"enabled": False}}) == "déterministe (aucun LLM configuré)"


def test_architecture_mermaid_comes_from_the_compiled_graphs(ctx):
    text = dl.render_architecture(ctx)
    assert text.count("```mermaid") == 3
    for node in ("collector", "auditor", "prepare", "finalize", "dashboard"):
        assert f"\t{node}({node})" in text
    assert "quality -.-> etl" in text  # arete conditionnelle du gate


def test_route2_graph_builder_matches_run_route2_wiring():
    from biflow.route2_graph import build_route2_graph

    graph = build_route2_graph(*(lambda s: {},) * 4)
    edges = {(e.source, e.target) for e in graph.get_graph().edges}
    assert {("prepare", "analyst"), ("prepare", "dashboard"), ("analyst", "finalize"),
            ("dashboard", "finalize")} <= edges


def test_kpi_catalog_lists_every_official_kpi(ctx):
    text = dl.render_kpi_catalog(ctx)
    kpis = ctx.official_kpis()
    assert len(re.findall(r"^### ", text, flags=re.M)) == len(kpis)
    for kpi_id, kpi in kpis.items():
        assert f"(`{kpi_id}`)" in text and kpi["name_fr"] in text
        assert ", ".join(str(y) for y in kpi["valid_years"]) in text


def test_check_ignores_generation_date(ctx, tmp_path, monkeypatch):
    monkeypatch.setattr(build_deliverables, "load_context", lambda: ctx)
    out = tmp_path / "out"
    assert build_deliverables.build(out) == 0
    assert build_deliverables.build(out, check=True) == 0
    target = out / "KPI_CATALOG.md"
    target.write_text(target.read_text(encoding="utf-8").replace("- **Généré le** : ", "- **Généré le** : x"),
                      encoding="utf-8")
    assert build_deliverables.build(out, check=True) == 0
    target.write_text(target.read_text(encoding="utf-8") + "\nmodifie\n", encoding="utf-8")
    assert build_deliverables.build(out, check=True) == 1
