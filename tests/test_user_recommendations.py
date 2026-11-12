"""Règle user_vs_official : vos données face au KPI officiel déclaré comparable.

Déclenchée seulement à année identique, seuil en points (%) ou relatif (autres unités),
toujours « à partir de vos données », nombres justifiés ; jamais dans les livrables."""
from __future__ import annotations

import copy

import pytest

from biflow.tools.recommendations import RULES_PATH, RulesError, USER_KIND, evaluate, load_rules, user_recommendations
from biflow.tools.user_sources.comparisons import INDICATIVE, YEARS_DIFFER

RULES = load_rules(RULES_PATH)


def comp_row(code, unit, user, official, *, user_year=2024, official_year=2024, status="ok"):
    return {"indicator_code": f"banque.{code}", "label": f"{code} (exemple fictif)", "unit": unit,
            "kpi_id": "atm_density" if unit != "percent" else "account_ownership",
            "kpi": "Densité des distributeurs automatiques" if unit != "percent" else "Taux de détention d'un compte",
            "definition": "def", "denominator": "den",
            "user": {"value": user, "display": str(user), "year": user_year, "unit": unit} if user is not None else None,
            "official": {"value": official, "display": str(official), "year": official_year, "unit": unit,
                         "publication_status": "approved"} if official is not None else None,
            "status": status, "same_year": user_year == official_year,
            "notes": [] if user_year == official_year else [YEARS_DIFFER]}


def run(*rows):
    return user_recommendations({"iso3": "TUN", "year": 2024, "note": INDICATIVE, "rows": list(rows)}, RULES)


def test_relative_threshold_for_non_percent_units():
    # 30.8 contre 35.44 : 13.1 % de moins -> piste ; 33 contre 35.44 : 6.9 % -> rien
    result = run(comp_row("atm", "per_100k_adults", 30.8, 35.44))
    assert len(result["recommendations"]) == 1 and result["rejected"] == []
    rec = result["recommendations"][0]
    assert rec["kind"] == USER_KIND and rec["user_data"] is True
    assert rec["text"].startswith("Piste à explorer (à partir de vos données) : ")
    assert "30,8 pour 100 000 adultes (données utilisateur, non vérifiées par BIFlow)" in rec["text"]
    assert "35,4 pour 100 000 adultes" in rec["text"] and "13,1 % de moins en valeur relative" in rec["text"]
    assert rec["text"].endswith(f"{INDICATIVE}. Association, pas causalité.")
    assert rec["trigger"]["threshold"] == 10
    assert run(comp_row("atm", "per_100k_adults", 33.0, 35.44))["recommendations"] == []


def test_points_threshold_for_percent_and_both_directions():
    above = run(comp_row("mobile", "percent", 45.0, 37.8))["recommendations"][0]  # 7.2 pts de plus
    assert "7,2 pts de plus" in above["text"] and "en valeur relative" not in above["text"]
    assert "ce qui distingue votre valeur" in above["text"]
    below = run(comp_row("mobile", "percent", 32.8, 37.8))["recommendations"][0]  # 5.0 pts : seuil inclus
    assert "5,0 pts de moins" in below["text"] and "en dessous de la référence officielle" in below["text"]
    assert run(comp_row("mobile", "percent", 33.0, 37.8))["recommendations"] == []


def test_no_recommendation_when_years_differ_or_values_are_missing():
    rows = [comp_row("atm", "per_100k_adults", 20.0, 35.44, user_year=2023),
            comp_row("mobile", "percent", None, 37.8, status="no_user_value"),
            comp_row("taux", "percent", 10.0, None, status="no_official_value"),
            comp_row("autre", "count", None, None, status="unit_mismatch")]
    result = run(*rows)
    assert result["recommendations"] == [] and result["rules_checked"] == 0


def test_forbidden_wording_is_rejected(monkeypatch):
    rules = copy.deepcopy(RULES)
    rule = next(r for r in rules["rules"] if r["kind"] == USER_KIND)
    rule["piste_below"] = "il faut ouvrir des agences"
    result = user_recommendations({"iso3": "TUN", "year": 2024, "note": INDICATIVE,
                                   "rows": [comp_row("atm", "per_100k_adults", 30.8, 35.44)]}, rules)
    assert result["recommendations"] == [] and "formulation interdite : il faut" in result["rejected"][0]["audit"]["reasons"]


def test_ungrounded_number_is_rejected():
    rules = copy.deepcopy(RULES)
    rule = next(r for r in rules["rules"] if r["kind"] == USER_KIND)
    rule["piste_below"] = "viser 50 agences de plus"
    result = user_recommendations({"iso3": "TUN", "year": 2024, "note": INDICATIVE,
                                   "rows": [comp_row("atm", "per_100k_adults", 30.8, 35.44)]}, rules)
    assert result["recommendations"] == [] and "nombre '50' du texte non justifié" in result["rejected"][0]["audit"]["reasons"]


def test_official_rules_ignore_the_user_rule():
    # evaluate (pistes officielles, livrables) ne lit jamais la regle user_vs_official
    result = evaluate([], "TUN", 2024, RULES, {})
    assert result["recommendations"] == [] and all(r["kind"] != USER_KIND for r in result["rejected"])


def test_rules_file_requires_both_thresholds_and_pistes(tmp_path):
    rules = copy.deepcopy(RULES)
    rule = next(r for r in rules["rules"] if r["kind"] == USER_KIND)
    del rule["threshold_pct"]
    import yaml

    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(rules, allow_unicode=True), encoding="utf-8")
    with pytest.raises(RulesError, match="threshold_pct"):
        load_rules(path)


def test_deliverable_text_mentions_the_rule_but_never_applies_it():
    from biflow.tools import deliverables as dl

    text = dl.render_insights(dl.load_context())
    assert "`user_vs_official`" in text and "n'est jamais appliquée dans ce document" in text
    assert "à partir de vos données) :" not in text  # aucune piste utilisateur
