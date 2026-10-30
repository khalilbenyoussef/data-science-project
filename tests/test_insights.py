"""Contrat d'audit des insights de l'Analyst (insights ecrits a la main)."""
from __future__ import annotations

import pytest

from biflow.tools.insights import Insight, audit_insights

ROWS = [
    {"kpi_id": "account_ownership", "iso3": "TUN", "year": 2024, "value": 37.844486, "unit": "percent",
     "publication_status": "approved", "review_reasons": []},
    {"kpi_id": "account_ownership", "iso3": "PEERS", "year": 2024, "value": 42.311767, "unit": "percent",
     "publication_status": "approved_with_review_note", "review_reasons": ["partial_peer_coverage"]},
    {"kpi_id": "gender_gap", "iso3": "TUN", "year": 2021, "value": 16.390000, "unit": "percentage_points",
     "publication_status": "approved", "review_reasons": []},
    {"kpi_id": "gender_gap", "iso3": "TUN", "year": 2024, "value": 22.959101, "unit": "percentage_points",
     "publication_status": "approved", "review_reasons": []},
    {"kpi_id": "income_gap", "iso3": "TUN", "year": 2024, "value": 26.959209, "unit": "percentage_points",
     "publication_status": "approved", "review_reasons": []},
    {"kpi_id": "branch_density", "iso3": "TUN", "year": 2024, "value": 22.368009, "unit": "per_100k_adults",
     "publication_status": "blocked", "review_reasons": []},
    {"kpi_id": "saving_rate", "iso3": "TUN", "year": 2024, "value": None, "unit": "percent",
     "publication_status": "approved", "review_reasons": []},
]


def claim(kpi_id, iso3, year, value, unit):
    return {"kpi_id": kpi_id, "iso3": iso3, "year": year, "value": value, "unit": unit}


def insight(text, *claims, **extra):
    return {"insight_id": extra.pop("insight_id", "i1"), "text": text, "claims": list(claims),
            "recommendation": "Cibler les femmes non bancarisees.", "confidence": "medium", **extra}


ACCOUNT = claim("account_ownership", "TUN", 2024, 37.8, "percent")
PEERS = claim("account_ownership", "PEERS", 2024, 42.3, "percent")
GAP21, GAP24 = (claim("gender_gap", "TUN", 2021, 16.4, "percentage_points"),
                claim("gender_gap", "TUN", 2024, 23.0, "percentage_points"))


def audit(*items):
    return audit_insights(items, ROWS)


def test_good_insight_with_values_years_and_peer_difference():
    result, = audit(insight("En 2024, 37,8 % des adultes tunisiens avaient un compte, contre 42,3 % chez "
                            "les pairs, soit 4,5 points de moins.", ACCOUNT, PEERS))
    assert result["accepted"], result["reasons"]
    assert result["notes"] and "partial_peer_coverage" in result["notes"][0]


def test_widening_gap_difference_between_two_years_is_accepted():
    result, = audit(insight("The gender gap widened by 6.6 pts, from 16.4 pts in 2021 to 23.0 pts in 2024.",
                            GAP21, GAP24))
    assert result == {"insight_id": "i1", "accepted": True, "reasons": [], "notes": []}


@pytest.mark.parametrize("text,claims,reason", [
    ("37,9 % des adultes avaient un compte en 2024.", [claim("account_ownership", "TUN", 2024, 37.9, "percent")],
     "different de 37.8 publie"),
    ("En 2024, 37,8 % des adultes avaient un compte, et 52 % des femmes.", [ACCOUNT],
     "nombre '52' du texte non justifie"),
    ("L'ecart s'est creuse de 6,6 points.", [GAP24], "nombre '6,6' du texte non justifie"),
    ("Ecart de revenu 27,0 pts contre ecart de genre 23,0 pts : 4,0 pts de difference.",
     [claim("income_gap", "TUN", 2024, 27.0, "percentage_points"), GAP24], "nombre '4,0'"),
    ("37,8 % en 2024.", [claim("account_ownership", "TUN", 2024, 37.8, "percentage_points")], "unite"),
    ("37,8 % en 2023.", [claim("account_ownership", "TUN", 2023, 37.8, "percent")], "aucune ligne"),
    ("22,4 agences.", [claim("branch_density", "TUN", 2024, 22.4, "per_100k_adults")], "ligne blocked"),
    ("Epargne 40 %.", [claim("saving_rate", "TUN", 2024, 40.0, "percent")], "valeur indisponible"),
])
def test_bad_insights_are_rejected_with_reason(text, claims, reason):
    result, = audit(insight(text, *claims))
    assert result["accepted"] is False
    assert any(reason in r for r in result["reasons"]), result["reasons"]


@pytest.mark.parametrize("change", [
    lambda i: i.update(claims=[]),
    lambda i: i.update(confidence="sure"),
    lambda i: i.update(extra_field=1),
    lambda i: i["claims"][0].update(year="2024"),
])
def test_schema_violations_are_rejected(change):
    item = insight("37,8 % en 2024.", dict(ACCOUNT))
    change(item)
    result, = audit(item)
    assert result["accepted"] is False and result["reasons"][0].startswith("schema invalide")


def test_publication_statuses_from_the_audit_take_precedence():
    statuses = {("account_ownership", "TUN", 2024): "blocked"}
    result, = audit_insights([insight("37,8 % en 2024.", ACCOUNT)], ROWS, statuses)
    assert not result["accepted"] and "ligne blocked" in result["reasons"][0]


def test_schema_is_exported():
    schema = Insight.model_json_schema()
    assert set(schema["required"]) == {"insight_id", "text", "claims", "recommendation", "confidence"}
