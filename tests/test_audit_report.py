"""Rapport d'audit et evaluation par injection de fautes (fixtures temporaires)."""
from __future__ import annotations

import hashlib
import importlib.util
import json

from biflow.agents.auditor import AuditorAgent
from biflow.config import ROOT
from test_auditor import built, world  # noqa: F401 - fixtures reutilisees


def test_audit_report_json_and_markdown(world):
    audit = AuditorAgent(cfg=world.cfg, run_id="audit_run").execute(world.ctx)["audit"]
    report = json.loads((world.tmp / "audit" / "audit_report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == audit["verdict"] == "pass_with_warnings"
    assert report["counts"] == audit["counts"] and report["timing_s"] > 0
    assert {c["check_id"] for c in report["caveats"]} == {"C2_partial_peer_coverage", "C4_within_survey_noise"}
    assert report["publication"]["blocked_rows"] == []
    assert [e["step"] for e in report["decision_log"]][-1] == "auditor"
    assert [e["title"] for e in report["examples"]] == ["Détention de compte", "Écart hommes-femmes",
                                                        "Densité d'agences et pairs"]
    md = (world.tmp / "audit" / "audit_report.md").read_text(encoding="utf-8")
    for section in ("# Rapport d'audit BIFlow", "**Verdict : CONFORME AVEC AVERTISSEMENTS**", "## Contrôles",
                    "## Avertissements", "## Décisions de publication", "## Journal des décisions du pipeline",
                    "## Exemples d'explications", "Décomposition : men +4,4 pts, women -2,1 pts."):
        assert section in md, section


def test_report_lists_blocked_rows(world):
    world.sql("UPDATE kpi_values SET value = value + 1 WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024")
    AuditorAgent(cfg=world.cfg, run_id="audit_run").execute(world.ctx)
    report = json.loads((world.tmp / "audit" / "audit_report.json").read_text(encoding="utf-8"))
    assert report["verdict"] == "fail"
    assert report["publication"]["blocked_rows"] == [{"kpi_id": "account_ownership", "iso3": "TUN", "year": 2024}]
    assert "**Verdict : NON CONFORME**" in (world.tmp / "audit" / "audit_report.md").read_text(encoding="utf-8")


def test_fault_injection_detects_every_fault_without_touching_sources(world, tmp_path):
    spec = importlib.util.spec_from_file_location("evaluate_auditor", ROOT / "scripts" / "evaluate_auditor.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    warehouse = world.tmp / "processed" / "warehouse.duckdb"
    digest = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    summary = module.evaluate(world.cfg, tmp_path / "eval")
    assert summary["baseline"]["verdict"] != "fail"
    assert summary["detected"] == summary["total"] == 9, [f for f in summary["faults"] if not f["detected"]]
    assert all(f["verdict"] != "pass" for f in summary["faults"])
    assert hashlib.sha256(warehouse.read_bytes()).hexdigest() == digest  # copie de travail uniquement
    md = (tmp_path / "eval" / "evaluation.md").read_text(encoding="utf-8")
    assert "**Fautes détectées : 9 / 9**" in md and "| Ligne agrégat WLD dans kpi_values |" in md
