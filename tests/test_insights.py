"""Contrat d'audit des insights de l'Analyst (insights ecrits a la main)."""
from __future__ import annotations

import pytest

from biflow.tools.insights import Insight, audit_insights, insights_from_finova

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


# ------------------------------------------------------------- conversion FinOVA -> Insight
def _fact(fact_id, code, value, year, provider="semantic", unit="percent", evidence=(), iso3="TUN"):
    return {"id": fact_id, "code": code, "value": value, "unit": unit, "year": year, "iso3": iso3,
            "provider": provider, "evidence_ids": tuple(evidence)}


FINOVA_FACTS = [
    _fact("F-account_ownership-TUN-2024", "account_ownership", 37.844486, 2024,
          evidence=("EV-account_ownership-TUN-2024",)),
    _fact("F-account_ownership-TUN-2021", "account_ownership", 36.853236, 2021,
          evidence=("EV-account_ownership-TUN-2021",)),
    _fact("F-account_ownership-delta-TUN-2024", "account_ownership_delta", 0.991250, 2024,
          provider="derived", unit="percentage_points",
          evidence=("EV-account_ownership-TUN-2024", "EV-account_ownership-TUN-2021")),
    # identifiant de widget stable (formal_saving) : le KPI vient de la preuve
    _fact("F-formal_saving-TUN-2024", "formal_saving", 21.6, 2024,
          evidence=("EV-formal_saving_rate-TUN-2024",)),
    _fact("F-index-atm-TUN-2024", "index_atm_per_100k", 119.0, 2024, provider="derived",
          unit="index_2017_100", evidence=("EV-atm_density-TUN-2017", "EV-atm_density-TUN-2024")),
]
KPI_IDS = ("account_ownership", "formal_saving_rate", "atm_density")
CHANGE_ROWS = [
    {"kpi_id": "account_ownership", "iso3": "TUN", "year": 2024, "value": 37.844486, "unit": "percent",
     "publication_status": "approved", "review_reasons": []},
    {"kpi_id": "account_ownership", "iso3": "TUN", "year": 2021, "value": 36.853236, "unit": "percent",
     "publication_status": "approved", "review_reasons": []},
]


def test_change_insight_carries_claims_for_both_years():
    insights = {"overview": [{"id": "INS-overview-account", "evidence_ids": [
        "F-account_ownership-TUN-2024", "F-account_ownership-delta-TUN-2024"],
        "statement": "En 2024, 37.8 % des adultes en Tunisie détiennent un compte. (+1.0 pt vs 2021)"}]}
    converted, not_auditable = insights_from_finova(insights, FINOVA_FACTS, KPI_IDS)
    assert not_auditable == []
    assert {(c["year"], c["value"]) for c in converted[0]["claims"]} == {(2024, 37.844486), (2021, 36.853236)}
    result, = audit_insights(converted, CHANGE_ROWS)
    assert result["accepted"] is True, result["reasons"]
    # sans la ligne 2021, la regle de l'Auditor rejette toujours la variation
    result, = audit_insights(converted, CHANGE_ROWS[:1])
    assert result["accepted"] is False
    assert any("2021" in reason for reason in result["reasons"])


def test_widget_facts_use_the_kpi_of_their_evidence_and_derived_indexes_stay_unaudited():
    insights = {"inclusion": [{"id": "INS-funnel", "evidence_ids": ["F-formal_saving-TUN-2024"],
                               "statement": "21.6 % épargnent."}],
                "access": [{"id": "INS-index", "evidence_ids": ["F-index-atm-TUN-2024"],
                            "statement": "Indice 119.0."}]}
    converted, not_auditable = insights_from_finova(insights, FINOVA_FACTS, KPI_IDS)
    assert [c["claims"] for c in converted] == [[{"kpi_id": "formal_saving_rate", "iso3": "TUN",
                                                  "year": 2024, "value": 21.6, "unit": "percent"}]]
    assert not_auditable == ["access:INS-index"]
