"""Format francais des nombres generes (affichage seulement) et lecture par les
controles de nombres : l'Auditor, l'Analyst et Ask acceptent 37,8 et 1 063,3."""
import re

import pytest

from biflow.agents.analyst import build_insights, verify_numbers
from biflow.tools.audit_text import extract_numbers, fr_number, grounding, number_value
from biflow.tools.dashboard_spec import format_value
from biflow.tools.insights import audit_insights

NNBSP = " "


@pytest.mark.parametrize("value,decimals,signed,expected", [
    (37.84, 1, False, "37,8"), (1063.33, 1, False, f"1{NNBSP}063,3"), (23.0, 1, True, "+23,0"),
    (-0.54, 1, True, "-0,5"), (1234567, 0, False, f"1{NNBSP}234{NNBSP}567"), (0.96, 2, False, "0,96"),
])
def test_fr_number(value, decimals, signed, expected):
    assert fr_number(value, decimals, signed) == expected


def test_pdf_thousands_separator_is_a_no_break_space():
    assert fr_number(1509, 0, thousands=" ") == "1 509"


@pytest.mark.parametrize("text,numbers", [
    (f"Déposants 1{NNBSP}063,3 pour mille adultes", ["1063.3"]),
    ("Déposants 1 063,3", ["1063.3"]),
    ("en 2021, 2024 : 37,8 %", ["2021", "2024", "37.8"]),  # virgule + espace : deux nombres
    ("en 2024 37,8", ["2024", "37.8"]),  # une espace ordinaire ne groupe jamais
    ("+1,0 pt vs 2021", ["1.0", "2021"]),
    ("35.44 / 100k adultes", ["35.44"]),  # ancien format toujours lu ; « 100k » est une unite
])
def test_extract_numbers_reads_french_and_dot_formats(text, numbers):
    assert extract_numbers(text) == numbers


def test_number_value_and_grounding_compare_values_not_spelling():
    assert number_value(f"1{NNBSP}063,3") == 1063.3 and number_value("−2,5") == -2.5
    assert grounding("37,8 % en 2024", "37.8 % (2024)") == (True, [])
    assert grounding("38,0 %", "37.8 %") == (False, ["38.0"])


def _row(kpi_id, value, unit, year=2024):
    return {"kpi_id": kpi_id, "iso3": "TUN", "year": year, "value": value, "unit": unit,
            "publication_status": "approved", "review_reasons": []}


def test_auditor_accepts_french_insights_and_still_rejects_wrong_numbers():
    rows = [_row("depositors_per_1k", 1063.33, "per_1k_adults", 2018), _row("account_ownership", 37.84, "percent")]
    claims = [{"kpi_id": "depositors_per_1k", "iso3": "TUN", "year": 2018, "value": 1063.3, "unit": "per_1k_adults"}]
    good = audit_insights([{"insight_id": "a", "text": f"Déposants 1{NNBSP}063,3 pour mille adultes en 2018.",
                            "claims": claims, "recommendation": "-", "confidence": "medium"}], rows)[0]
    assert good["accepted"], good["reasons"]
    bad = audit_insights([{"insight_id": "b", "text": f"Déposants 1{NNBSP}163,3 pour mille adultes en 2018.",
                           "claims": claims, "recommendation": "-", "confidence": "medium"}], rows)[0]
    assert not bad["accepted"]


def test_format_value_is_french():
    assert format_value(37.84, "percent") == "37,8 %"
    assert format_value(1063.33, "per_1k_adults") == f"1{NNBSP}063,3 / 1 000 adultes"
    assert format_value(448.24, "TND_per_month") == "448,24 TND/mois"


def F(code, value, unit="percent", year=2024, provider="semantic", label=None):
    return {"id": f"F-{code}-TUN-{year}", "code": code, "label": label or code, "value": value, "unit": unit,
            "year": year, "iso3": "TUN", "provider": provider, "display": format_value(value, unit),
            "evidence_ids": ()}


# identifiant technique dans une phrase : snake_case (account_t_d) ou code Findex (fin24aP, g20_any)
TECHNICAL = re.compile(r"\b[a-z]+_[a-z0-9_]+\b|\bfin\d+[a-zA-Z]*\b|\bg20\w*\b")


def test_analyst_sentences_are_french_and_free_of_technical_codes():
    facts = [F("account_ownership", 37.84, label="Détention d'un compte"),
             F("digital_payment_rate", 23.68, label="Paiements numériques"),
             F("saving_rate", 48.2, label="Épargne"),
             F("emergency_money", 88.39, label="Fonds d'urgence"),
             F("depositors_per_1k", 1063.33, unit="per_1k_adults", year=2018, provider="warehouse",
               label="Déposants")]
    insights, warnings = build_insights(facts, "Tunisie")
    statements = [item["statement"] for items in insights.values() for item in items]
    assert statements and warnings == []
    for statement in statements:
        assert not TECHNICAL.search(statement), statement
        assert not re.search(r"\d\.\d", statement), statement  # aucune decimale a point
        assert verify_numbers(statement, facts) == [], statement
    emergency = next(s for s in statements if "urgence" in s)
    assert "88,4 %" in emergency and "(2024)" in emergency
