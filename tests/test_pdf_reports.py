"""Rapports PDF a la demande : generes, chiffres egaux a /api/audit/summary, rien ecrit."""
from __future__ import annotations

import base64
import json
import re
import zlib
from pathlib import Path

import duckdb
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from biflow.config import ROOT, load_config
from biflow.tools import deliverables as dl
from biflow.tools.user_sources.data import UserData
from dashboard_app.api.audit import create_audit_router
from dashboard_app.api.pdf_reports import n
from dashboard_app.api.reports import create_reports_router


def pdf_strings(data: bytes) -> list[str]:
    """Chaines de texte des flux de contenu du PDF (reportlab : ASCII85 puis Flate)."""
    out = []
    pattern = rb"/ASCII85Decode /FlateDecode \] /Length \d+\s*>>\s*stream\r?\n(.*?)endstream"
    for raw in re.findall(pattern, data, flags=re.S):
        raw = raw.strip().removesuffix(b"~>").replace(b"\n", b"").replace(b"\r", b"")
        content = zlib.decompress(base64.a85decode(raw))
        for text in re.findall(rb"\(((?:\\.|[^\\)])*)\)\s*Tj", content):
            text = re.sub(rb"\\(\d{3})", lambda m: bytes([int(m.group(1), 8)]), text)
            text = re.sub(rb"\\([()\\])", rb"\1", text)
            out.append(text.decode("cp1252"))
    return out


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def env(tmp_path):
    audit = tmp_path / "audit"
    _write(audit / "audit_report.json", {
        "run_id": "run_x", "snapshot_id": "v7", "created_at": "2026-11-04T10:00:00", "verdict": "pass_with_warnings",
        "counts": {"pass": 17, "warn": 2, "fail": 0}, "rows": 1620,
        "checks": [{"check_id": "A1_recomputed_values", "category": "recomputation", "result": "pass",
                    "detail": "0 ecart", "affected_rows": [], "affects_publication": True},
                   {"check_id": "C2_partial_peer_coverage", "category": "caveat", "result": "warn", "detail": "84",
                    "affected_rows": [{"kpi_id": "x"}] * 84, "affects_publication": True}],
        "publication": {"by_status": {"approved": 1509, "approved_with_review_note": 111, "blocked": 0}},
        "route2_insight_audit": {"run_id": "route2_x", "audited": 15, "accepted": 15, "rejected": 0,
                                 "not_auditable": 2, "results": [{"insight_id": "overview:INS-1", "accepted": True,
                                                                  "reasons": []}],
                                 "not_auditable_ids": ["poverty:INS-2"]}})
    _write(audit / "evaluation.json", {"created_at": "2026-11-03T09:00:00", "detected": 9, "total": 9,
                                       "faults": [{"id": "tampered_value", "label": "Valeur KPI modifiee",
                                                   "expected_check": "A1_recomputed_values", "detected": True,
                                                   "verdict": "fail"}]})
    spec = {"run_id": "route2_x", "generated_at": "2026-11-04T10:01:00", "country": {"iso3": "TUN", "name": "Tunisie"},
            "year": 2024, "pages": [
                {"id": "overview", "title": "Vue d'ensemble", "insights": [
                    {"id": "INS-1", "statement": "En 2024, 37.8 % des adultes ont un compte.",
                     "evidence_ids": ["F-account_ownership-TUN-2024"]},
                    {"id": "INS-3", "statement": "En 2024, 99.9 % des adultes ont un compte.",
                     "evidence_ids": ["F-account_ownership-TUN-2024"]}]},
                {"id": "poverty", "title": "Pauvreté", "insights": [
                    {"id": "INS-2", "statement": "SMIG de reference.", "evidence_ids": []}]}],
            "facts": [{"id": "F-account_ownership-TUN-2024", "code": "account_ownership", "value": 37.844,
                       "year": 2024, "iso3": "TUN", "provider": "semantic", "display": "37.8 %", "unit": "percent",
                       "evidence_ids": ["EV-account_ownership-TUN-2024"]}]}
    spec_file = tmp_path / "finova.json"
    _write(spec_file, spec)
    warehouse = tmp_path / "processed" / "warehouse.duckdb"
    warehouse.parent.mkdir()
    with duckdb.connect(str(warehouse)) as con:
        con.execute("CREATE TABLE kpi_values (kpi_id VARCHAR, iso3 VARCHAR, year INTEGER, value DOUBLE, unit VARCHAR, "
                    "publication_status VARCHAR, review_reasons VARCHAR[], peer_status VARCHAR, "
                    "peers_included VARCHAR[], missing_peers VARCHAR[], availability_status VARCHAR)")
        con.executemany("INSERT INTO kpi_values VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'available')", [
            ("account_ownership", "TUN", 2024, 37.844, "percent", "approved", [], None, None, None),
            ("gender_gap", "TUN", 2024, 22.96, "percentage_points", "approved", [], None, None, None),
            ("account_ownership", "PEERS", 2011, 30.0, "percent", "approved_with_review_note",
             ["partial_peer_coverage"], "partial", ["DZA"], ["MAR"]),
            ("atm_density", "TUN", 2024, 35.44, "per_100k_adults", "approved", [], None, None, None),
        ])
        con.execute("CREATE TABLE fact (source VARCHAR, indicator_code VARCHAR, iso3 VARCHAR, year INTEGER, "
                    "dimension VARCHAR, dimension_value VARCHAR, value DOUBLE, unit VARCHAR)")
        con.executemany("INSERT INTO fact VALUES ('user:banque', ?, 'TUN', ?, 'all', 'all', ?, ?)", [
            ("banque.atm", 2024, 30.8, "per_100k_adults"), ("banque.mobile", 2023, 26.4, "percent")])
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "banque.yaml").write_text(yaml.safe_dump({
        "schema_version": 1, "name": "banque", "fingerprint": "c" * 64, "file": "data/uploads/banque.csv",
        "read": {"encoding": "utf-8", "separator": ";", "decimal": ",", "header_row": 0},
        "layout": "wide_by_indicator",
        "columns": {"country": {"column": "Pays", "kind": "name"}, "year": "Annee",
                    "indicator_columns": {"a": "atm", "b": "mobile"}},
        "indicators": {"atm": {"label": "ATM du reseau (exemple fictif)", "unit": "per_100k_adults",
                               "comparable_kpi": "atm_density"},
                       "mobile": {"label": "Banque mobile (exemple fictif)", "unit": "percent"}}},
        allow_unicode=True), encoding="utf-8")
    user_data = UserData({"uploads": {"mappings_dir": str(sources)}}, warehouse)
    cfg = load_config()
    cfg["paths"] = {**cfg["paths"], "reports": str(tmp_path / "reports"), "audit": str(audit),
                    "quality": str(tmp_path / "quality"), "processed": str(warehouse.parent)}
    cfg["dashboard"] = {**cfg["dashboard"], "spec_output": str(spec_file)}
    context = lambda: dl.load_context(cfg, evaluation_dir=tmp_path / "evaluation",  # noqa: E731
                                      manual_path=tmp_path / "manual.yaml")
    app = FastAPI()
    app.include_router(create_audit_router(audit_dir=audit, warehouse=warehouse, spec_file=spec_file))
    app.include_router(create_reports_router(warehouse=warehouse, audit_dir=audit, spec_file=spec_file,
                                             context=context, spec_for=lambda iso3, year: (spec, "file"),
                                             user_data=user_data))
    return TestClient(app), tmp_path


def snapshot(root: Path) -> dict[str, float]:
    return {str(p): p.stat().st_mtime for p in root.rglob("*") if p.is_file()}


def test_evaluation_pdf_numbers_equal_audit_summary(env):
    client, root = env
    before = snapshot(root)
    response = client.get("/api/reports/evaluation.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.headers["content-disposition"].startswith("attachment; filename=")
    assert response.content.startswith(b"%PDF")
    summary = client.get("/api/audit/summary").json()
    strings = pdf_strings(response.content)
    joined = " ".join(strings)
    assert n(summary["counts"]["pass"]) in strings and n(summary["counts"]["warn"]) in strings
    publication = summary["publication"]
    for key in ("approved", "approved_with_review_note"):
        assert n(publication[key]) in strings  # 1 509 et 111
    assert f"{n(summary['evaluation']['detected'])} / {n(summary['evaluation']['total'])}" in strings
    insight = summary["insight_audit"]
    assert n(insight["audited"]) in strings and n(insight["not_auditable"]) in strings
    for value in ("run_x", "v7", load_config_catalog_version()):
        assert value in joined
    assert "84" in strings  # lignes signalees par C2, comme /api/audit/checks
    assert snapshot(root) == before  # lecture seule : aucun fichier cree ni modifie


def load_config_catalog_version() -> str:
    from biflow.tools.kpi import load_catalog

    return load_catalog()["catalog_version"]


def test_evaluation_pdf_flags_results_older_than_the_audit(env):
    client, _ = env
    joined = " ".join(pdf_strings(client.get("/api/reports/evaluation.pdf").content))
    assert "2026-11-03 09:00:00" in joined  # date de l'injection de fautes sur la page de garde
    assert "antérieur au dernier audit" in joined


def test_insights_pdf_for_the_scope(env):
    client, root = env
    before = snapshot(root)
    response = client.get("/api/reports/insights.pdf", params={"iso3": "tun", "year": 2024})
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    joined = " ".join(pdf_strings(response.content))
    assert "Tunisie (TUN), 2024" in joined
    assert "accepté" in joined and "rejeté" in joined and "non auditable" in joined  # statut calcule a la demande
    assert "Piste à explorer" in joined and "23.0 pts" in joined
    assert snapshot(root) == before


def test_insights_pdf_has_no_user_data_by_default(env):
    client, _ = env
    response = client.get("/api/reports/insights.pdf", params={"iso3": "TUN", "year": 2024})
    joined = " ".join(pdf_strings(response.content))
    assert "Annexe" not in joined and "exemple fictif" not in joined and "30.8" not in joined
    assert response.headers["content-disposition"].endswith('finova_constats_TUN_2024.pdf"')


def test_insights_pdf_annex_labels_every_user_value(env):
    client, root = env
    before = snapshot(root)
    response = client.get("/api/reports/insights.pdf", params={"iso3": "TUN", "year": 2024, "annexe": "true"})
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('finova_constats_TUN_2024_avec_vos_donnees.pdf"')
    strings = pdf_strings(response.content)
    joined = " ".join(strings)
    annex = joined[joined.index("Annexe : vos données"):]
    official = joined[:joined.index("Annexe : vos données")]
    assert "30.8" not in official and "exemple fictif" not in official  # jamais dans les constats officiels
    assert "BIFlow ne les vérifie pas" in annex
    assert "30.8 pour 100 000 adultes (2024)" in annex and "26.4 % (2023)" in annex  # annee anterieure indiquee
    # chaque ligne de valeurs porte l'etiquette (cellule « Étiquette »), plus le chapeau de section
    assert annex.count("Données utilisateur") >= 3
    assert "Comparaison indicative : définition déclarée par l'utilisateur" in annex
    assert "35.44 pour 100 000 adultes (2024)" in annex  # KPI officiel compare, meme annee
    assert "Pistes à partir de vos données" in annex and "à partir de vos données) :" in annex
    assert "à partir de vos données" not in official
    assert snapshot(root) == before


def test_recommendations_api_keeps_user_pistes_apart(env):
    client, _ = env
    body = client.get("/api/recommendations", params={"iso3": "TUN", "year": 2024}).json()
    assert all(not rec.get("user_data") for rec in body["recommendations"])
    assert [rec["kind"] for rec in body["user_recommendations"]] == ["user_vs_official"]
    assert body["user_recommendations"][0]["text"].startswith("Piste à explorer (à partir de vos données) : ")
    assert body["user_rejected"] == 0


@pytest.mark.parametrize("query", ["iso3=TU&year=2024", "iso3=TUN&year=1800", "iso3=..%2F&year=2024", "year=2024"])
def test_insights_pdf_validates_parameters(env, query):
    client, _ = env
    assert client.get(f"/api/reports/insights.pdf?{query}").status_code in (400, 422)


def test_pdfs_are_never_generated_by_the_pipeline():
    """main.py run et le paquet biflow n'importent ni reportlab ni le module PDF."""
    sources = [ROOT / "main.py", *sorted((ROOT / "src" / "biflow").rglob("*.py"))]
    for path in sources:
        text = path.read_text(encoding="utf-8")
        assert "reportlab" not in text and "pdf_reports" not in text, path
    assert "reportlab" in (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "reportlab==" in (ROOT / "requirements.lock").read_text(encoding="utf-8")
