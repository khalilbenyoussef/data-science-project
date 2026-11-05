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
    for expected in ("0,812", "0,654", "12,34 %", "| fas | 77 | 9 | 5 |", "Anomalies moyennes | 3", "maison"):
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


def test_insights_document_lists_audit_status_and_recommendations(ctx, tmp_path, monkeypatch):
    import duckdb

    from biflow.tools import recommendations as reco

    ctx.spec = {"country": {"iso3": "TUN"}, "year": 2024, "pages": [
        {"id": "overview", "insights": [{"id": "A", "statement": "En 2024, 37.8 % ont un compte.",
                                         "evidence_ids": ["F-1"]}]},
        {"id": "poverty", "insights": [{"id": "B", "statement": "SMIG", "evidence_ids": []}]}],
        "facts": [{"id": "F-1", "code": "account_ownership", "value": 37.8, "year": 2024, "iso3": "TUN",
                   "provider": "semantic", "unit": "percent", "evidence_ids": ["EV-account_ownership-TUN-2024"]}]}
    ctx.audit["route2_insight_audit"] = {"run_id": "r2", "audited": 1, "accepted": 1, "rejected": 0,
                                         "not_auditable": 1, "results": [{"insight_id": "overview:A",
                                                                          "accepted": True, "reasons": []}],
                                         "not_auditable_ids": ["poverty:B"]}
    ctx.warehouse = tmp_path / "w.duckdb"
    with duckdb.connect(str(ctx.warehouse)) as con:
        con.execute("CREATE TABLE kpi_values (kpi_id VARCHAR, iso3 VARCHAR, year INTEGER, value DOUBLE, "
                    "unit VARCHAR, publication_status VARCHAR, review_reasons VARCHAR[], peer_status VARCHAR, "
                    "peers_included VARCHAR[], missing_peers VARCHAR[])")
        con.execute("INSERT INTO kpi_values VALUES ('gender_gap', 'TUN', 2024, 22.96, 'percentage_points', "
                    "'approved', [], NULL, NULL, NULL)")
    text = dl.render_insights(ctx)
    assert "| `overview:A` | En 2024, 37.8 % ont un compte. | accepté | Taux de détention d'un compte · TUN · 2024 |" in text
    assert "| `poverty:B` | SMIG | non auditable | — |" in text
    assert "1 audités, 1 acceptés, 0 rejetés, 1 non auditables" in text
    assert "Périmètre : **Tunisie (TUN), 2024**" in text
    assert "1. Piste à explorer : étudier des offres et canaux de distribution conçus pour les femmes." in text
    assert "23,0 pts" in text and "Groupe cible : femmes" in text
    assert str(reco.load_rules()["rules"][0]["threshold_pp"]) + " pts" in text


def test_evaluation_flags_stale_results_and_unmeasured_manual_time(ctx):
    ctx.audit.update({"created_at": "2026-11-04T12:00:00", "counts": {"pass": 18, "warn": 1, "fail": 0}})
    ctx.fault_injection = {"created_at": "2026-11-01T09:00:00", "detected": 9, "total": 9,
                           "faults": [{"label": "Valeur modifiee", "expected_check": "A1_recomputed_values",
                                       "detected": True, "verdict": "fail"}]}
    ctx.baseline = {"created_at": "2026-11-05T09:00:00", "matched": 4, "compared": 4, "tolerance": 1e-9,
                    "countries": ["TUN"], "timing_s": {"naive_pandas": 0.5, "kpi_values_read": 0.01},
                    "by_kpi": {"account_ownership": {"compared": 4, "matched": 4}}, "mismatched": [],
                    "missing_in_naive": []}
    ctx.manual = {"minutes_per_kpi": {"account_ownership": None}}
    text = dl.render_evaluation(ctx)
    assert "Injection de fautes : 2026-11-01T09:00:00 — **résultat antérieur au dernier audit**" in text
    assert "### Injection de fautes (9/9 détectées)" in text
    assert "| `account_ownership` | 4 | 4 | non mesuré |" in text
    assert "**4/4 valeurs identiques**" in text
    assert "Contrôle en direct (10 questions fixes" in text and "non mesuré" in text
    assert text.count("\n## ") == 1 + len(dl.AGENTS) + 2  # fraicheur, synthese, un par agent, reference
    ctx.manual = {"minutes_per_kpi": {"account_ownership": 12.5}}
    assert "| `account_ownership` | 4 | 4 | 12,5 min |" in dl.render_evaluation(ctx)


def test_evaluation_reports_live_ask_check(ctx):
    ctx.ask_live = {"status": "mesuré", "model": "groq (m)", "run_at": "2026-11-05T10:00:00", "questions": 2,
                    "grounded": 1, "llm_answers": 2, "method": "m", "results": [
                        {"question": "q1", "mode": "llm", "grounded": True, "unknown": [], "answer": "37.8 %"},
                        {"question": "q2", "mode": "llm", "grounded": False, "unknown": ["12"], "answer": "12"}]}
    text = dl.render_evaluation(ctx)
    assert "**1/2 réponses fondées**" in text and "groq (m)" in text
    assert "| q2 | llm | non | 12 | 12 |" in text


def test_demo_script_reads_its_numbers(ctx, monkeypatch):
    values = {("account_ownership", "TUN"): 37.84, ("account_ownership", "MAR"): 44.4, ("gender_gap", "TUN"): 22.96,
              ("income_gap", "TUN"): 26.96, ("barrier_insufficient_funds", "TUN"): 45.7}
    monkeypatch.setattr(dl, "kpi_value", lambda c, k, iso3, year: values.get((k, iso3)))
    monkeypatch.setattr(dl, "scope_recommendations", lambda c, iso3=None, year=None: {"recommendations": [
        {"target_group": "femmes"}]})
    ctx.spec = {"country": {"iso3": "TUN"}, "year": 2024}
    ctx.audit.update({"counts": {"pass": 18, "warn": 1, "fail": 0}})
    ctx.fault_injection = {"detected": 9, "total": 9}
    text = dl.render_demo(ctx)
    main, banker = text.split("## Mode banquier", 1)
    assert main.count("\n| ") == 1 + 9  # en-tete et 9 etapes (le separateur commence par |---)
    assert banker.count("\n| ") == 1 + 8 and "banque_fictive_exemple.csv" in banker
    assert "données fictives" in banker and "Mon indicateur mesure la même chose" in banker
    for limit in ("aucune authentification réelle", "Niveau pays uniquement", "Vos données : IA externe"):
        assert limit in banker
    assert "llm.ask.allow_user_data_to_llm" not in banker  # plus de configuration a modifier : un interrupteur
    assert "Détention d'un compte : 37,8 %" in text and "MAR 44,4 %" in text
    assert "Écart hommes − femmes : 23,0 pts ; revenu : 27,0 pts" in text
    assert "1 pistes ; ex. groupe cible « femmes »" in text
    assert "conforme : 18 réussis, 1 avertissements, 0 échecs" in text and "fautes 9/9" in text
    assert "contrôle en direct non mesuré" in text and "| 9:30–10:00 | Conclusion | — |" in text
    assert dl.TARGETS["DEMO.md"] == "docs/DEMO.md"
