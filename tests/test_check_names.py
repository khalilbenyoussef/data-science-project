"""Noms courts des contrôles, note des fautes sur les constats et tableaux du PDF."""
from __future__ import annotations

import re

from biflow.tools.audit_text import CHECK_NAMES, check_name, insight_faults_note
from dashboard_app.api.audit import CHECK_DESCRIPTIONS
from dashboard_app.api.pdf_reports import named_check
from test_audit_api import audit_env  # noqa: F401 - fixture reutilisee
from test_pdf_reports import env, pdf_strings  # noqa: F401 - fixture reutilisee


def test_every_described_check_has_a_short_french_name():
    assert set(CHECK_DESCRIPTIONS) <= set(CHECK_NAMES)
    assert check_name("A2_unavailable_rows_are_null") == "A2 – Valeurs indisponibles vides"
    assert check_name("Z9_inconnu") == "Z9_inconnu"  # controle inconnu : identifiant seul
    for name in CHECK_NAMES.values():
        assert not re.search(r"\b[a-z]+_[a-z_]+\b", name), name


FAULTS = [{"expected_check": f"A{i}", "verdict": "fail"} for i in range(1, 8)] + [
    {"expected_check": "F1_insights_grounded", "verdict": "pass_with_warnings"}] * 2


def test_insight_faults_note_names_the_faults_and_the_verdict():
    note = insight_faults_note(FAULTS)
    assert note.startswith("Fautes 8–9 (constats)")
    assert "rejet du constat" in note and "« conforme avec avertissements »" in note
    assert insight_faults_note(FAULTS[:7]) is None


def test_api_returns_names_and_the_fault_note(audit_env):
    client, _ = audit_env
    checks = {c["check_id"]: c for c in client.get("/api/audit/checks").json()["checks"]}
    assert checks["A1_recomputed_values"]["name"] == "A1 – Valeurs recalculées"
    evaluation = client.get("/api/audit/summary").json()["evaluation"]
    assert evaluation["faults"][0]["expected_check_name"] == "A1 – Valeurs recalculées"
    assert evaluation["insight_faults_note"] is None  # aucune faute sur les constats dans ce jeu


def test_pdf_check_cell_has_the_name_and_the_small_id():
    name, ident = named_check("B8_catalog_definitions")
    assert name.text == "B8 – Définitions du catalogue" and ident.text == "B8_catalog_definitions"
    assert name.style.splitLongWords == 0 and ident.style.fontSize < name.style.fontSize


def test_evaluation_pdf_shows_names_and_never_splits_words(env):
    client, _ = env
    strings = pdf_strings(client.get("/api/reports/evaluation.pdf").content)
    joined = " ".join(strings)
    assert "A1 – Valeurs recalculées" in joined and "A1_recomputed_values" in joined
    assert "C2 – Moyennes de pairs incomplètes" in joined
    # aucun mot coupe en fin de ligne de cellule (« non disp » / « onible »)
    assert not any(s.strip() in ("onible", "ponible") or s.rstrip().endswith((" disp", " dispo")) for s in strings)
