"""Finova analyst: every number must already exist in the facts."""
import pytest
from pydantic import ValidationError

from biflow.agents.analyst import (
    AskRequest, FinovaAnalystAgent, answer_question, build_insights, build_xai,
    narrate, verify_numbers,
)


def F(code, value, display, *, unit="percent", year=2024, provider="warehouse",
      label=None, iso3="TUN"):
    return {
        "id": f"F-{code}-{iso3}-{year}", "code": code,
        "label": label or code, "value": value, "unit": unit, "year": year,
        "iso3": iso3, "provider": provider, "display": display,
        "evidence_ids": (),
    }


@pytest.fixture
def facts():
    return [
        F("account_ownership", 37.84, "37.8 %", provider="semantic",
          label="Détention d'un compte"),
        F("account_ownership_delta", 0.93, "+0.9 pt vs 2021",
          unit="percentage_points", provider="derived"),
        F("digital_payment_rate", 23.68, "23.7 %", provider="semantic",
          label="Paiements numériques"),
        F("saving_rate", 21.6, "21.6 %", provider="semantic", label="Épargne"),
        F("emergency_money", 88.39, "88.4 %", label="Fonds d'urgence"),
        F("formal_saving", 21.6, "21.6 %", label="Épargne formelle"),
        F("formal_borrowing", 3.5, "3.5 %", label="Emprunt formel"),
        F("account_peer_TUN", 37.84, "37.8 %", provider="semantic",
          label="Tunisie", iso3="TUN"),
        F("account_peer_DZA", 35.3, "35.3 %", provider="semantic",
          label="Algérie", iso3="DZA"),
        F("account_peer_EGY", 43.1, "43.1 %", provider="semantic",
          label="Égypte", iso3="EGY"),
        F("account_peer_JOR", 46.5, "46.5 %", provider="semantic",
          label="Jordanie", iso3="JOR"),
        F("account_peer_MAR", 44.4, "44.4 %", provider="semantic",
          label="Maroc", iso3="MAR"),
        F("gender_femmes", 26.6, "26.6 %", label="Compte femmes"),
        F("gender_hommes", 49.6, "49.6 %", label="Compte hommes"),
        F("gap_gender", 23.0, "+23.0 pt", unit="percentage_points",
          provider="derived", label="Écart de compte genre"),
        F("gap_gender", 16.4, "16.4 pt", unit="percentage_points",
          provider="derived", year=2021, label="Écart de compte genre"),
        F("gap_change_gender", 6.6, "+6.6 pt", unit="percentage_points",
          provider="derived", label="Variation de l'écart genre"),
        F("income_40-les-plus-pauvres", 28.0, "28.0 %", label="Compte 40 %"),
        F("income_60-les-plus-riches", 44.0, "44.0 %", label="Compte 60 %"),
        F("gap_income", 16.0, "+16.0 pt", unit="percentage_points",
          provider="derived", label="Écart de compte revenu"),
        F("gap_change_income", 2.0, "+2.0 pt", unit="percentage_points",
          provider="derived", label="Variation écart revenu"),
        F("urban_account", 46.7, "46.7 %", label="Compte urbain"),
        F("rural_account", 30.2, "30.2 %", label="Compte rural"),
        F("gap_urbanicity", 16.6, "+16.6 pt", unit="percentage_points",
          provider="derived", label="Écart de compte milieu"),
        F("atm_per_100k", 35.44, "35.44 / 100k adultes",
          unit="per_100k_adults", label="ATMs"),
        F("atm_per_100k_delta", 0.65, "+0.65 vs 2023", unit="absolute",
          provider="derived", label="Variation ATMs"),
        F("index_atm_per_100k", 119.0, "119.0", unit="index_2017_100",
          provider="derived", label="Indice — ATMs (2017 = 100)"),
        F("branch_density", 22.37, "22.37 / 100k adultes",
          unit="per_100k_adults", provider="semantic", label="Agences"),
        F("depositors_per_1k", 1063.3, "1063.3 / 1 000 adultes",
          unit="per_1k_adults", year=2018, label="Déposants"),
        F("loans_pct_gdp", 67.8, "67.8 % du PIB", unit="percent_of_gdp",
          label="Encours de crédits"),
        F("smig_2025", 448.238, "448.24 TND/mois", unit="TND_per_month",
          year=2025, provider="reference", iso3=None),
        F("smig_2028", 517.571, "517.57 TND/mois", unit="TND_per_month",
          year=2028, provider="reference", iso3=None),
        F("poverty_rate_2021", 16.6, "16.6 %", year=2021, provider="reference",
          iso3=None),
        F("poverty_rate_extreme_2021", 2.9, "2.9 %", year=2021,
          provider="reference", iso3=None),
        F("poverty_rate_rural_2021", 24.8, "24.8 %", year=2021,
          provider="reference", iso3=None),
        F("poverty_rate_urban_2021", 12.7, "12.7 %", year=2021,
          provider="reference", iso3=None),
    ]


def test_number_guard_accepts_only_known_tokens(facts):
    assert verify_numbers("37.8 % en 2024 contre 49.6 %", facts) == []
    assert verify_numbers("Le taux est de 99 %", facts) == ["99"]
    assert verify_numbers("En 2019", facts) == ["2019"]


def test_insights_are_number_checked(facts):
    insights, warnings = build_insights(facts, "Tunisie")
    assert warnings == []
    assert {"INS-overview-account", "INS-overview-digital", "INS-overview-emergency",
            "INS-overview-peers"} <= {item["id"] for item in insights["overview"]}
    assert {"INS-inclusion-funnel", "INS-inclusion-gap-gender"} <= {
        item["id"] for item in insights["inclusion"]
    }
    fact_ids = {fact["id"] for fact in facts}
    for items in insights.values():
        for item in items:
            assert item["statement"].strip()
            assert set(item["evidence_ids"]) <= fact_ids
            assert verify_numbers(item["statement"], facts) == []
    # catalogue 1.3.0+ : epargne verifiee, fin24aP correctement libelle -> aucune mise en garde
    overview = {item["id"]: item for item in insights["overview"]}
    assert overview["INS-overview-saving"]["severity"] == "info"
    assert "provisoire" not in overview["INS-overview-saving"]["statement"]
    assert overview["INS-overview-emergency"]["severity"] == "info"
    assert "ne concorde pas" not in overview["INS-overview-emergency"]["statement"]


def test_review_wording_returns_when_the_backend_says_so(facts, monkeypatch):
    import biflow.agents.analyst as analyst

    monkeypatch.setattr(analyst, "_is_provisional", lambda kpi_id: kpi_id == "saving_rate")
    monkeypatch.setattr(analyst, "FIN24AP_MISLABELED", True)
    insights, _ = build_insights(facts, "Tunisie")
    overview = {item["id"]: item for item in insights["overview"]}
    assert overview["INS-overview-saving"]["severity"] == "review"
    assert overview["INS-overview-saving"]["statement"].endswith("est provisoire.")
    assert overview["INS-overview-emergency"]["severity"] == "warning"
    assert "ne concorde pas" in overview["INS-overview-emergency"]["statement"]


def test_xai_barrier_sentence_follows_the_loaded_barriers(facts):
    card, _ = build_xai(facts, "Tunisie")
    assert "ne sont pas chargées" in card["interpretation"][1]["statement"]
    loaded = facts + [F("barrier_insufficient_funds", 45.7, "45.7 %", provider="semantic")]
    card, warnings = build_xai(loaded, "Tunisie")
    assert warnings == []
    sentence = card["interpretation"][1]
    assert "ne sont pas chargées" not in sentence["statement"]
    assert "plusieurs" in sentence["statement"] and "sans en mesurer la cause" in sentence["statement"]
    assert sentence["evidence_ids"] == ("F-barrier_insufficient_funds-TUN-2024",)


def test_xai_is_hypothesis_with_association_caveat(facts):
    card, warnings = build_xai(facts, "Tunisie")
    assert warnings == [] and card is not None
    assert len(card["evidence"]) == 2 and len(card["interpretation"]) == 2
    assert card["recommendation"]["kind"] == "hypothesis"
    assert "causalit" in card["caveat"]
    fact_ids = {fact["id"] for fact in facts}
    for item in (*card["evidence"], *card["interpretation"], card["recommendation"]):
        assert set(item["evidence_ids"]) <= fact_ids
        assert verify_numbers(item["statement"], facts) == []


def test_answers_use_existing_facts_and_disclose_stale_years(facts):
    account = answer_question("Combien d'adultes ont un compte ?", facts,
                              country="Tunisie", year=2024)
    assert account["intent"] == "account" and account["fallback"] is False
    assert "37.8 %" in account["answer"]
    assert verify_numbers(account["answer"], facts) == []

    gender = answer_question("Pourquoi l'écart femmes-hommes ?", facts)
    assert gender["intent"] == "gender"
    assert "26.6 %" in gender["answer"] and "+23.0 pt" in gender["answer"]

    poverty = answer_question("Que dit la pauvreté rurale ?", facts)
    assert poverty["intent"] == "poverty"
    assert "24.8 %" in poverty["answer"]

    smig = answer_question("Quel est le SMIG ?", facts)
    assert smig["intent"] == "smig" and "448.24" in smig["answer"]

    stale = answer_question("Combien d'ATMs ?", facts, year=2025)
    assert "dernière année observée" in stale["answer"]

    unknown = answer_question("Bonjour", facts)
    assert unknown["intent"] == "unknown" and unknown["fallback"] is True
    assert unknown["fact_ids"] == ()


def test_answer_without_matching_data_stays_explicit():
    result = answer_question("Combien d'adultes ont un compte ?", [], country="Maroc")
    assert result["fallback"] is True
    assert "Aucun chiffre" in result["answer"]


def test_ask_request_is_typed():
    assert AskRequest(question="  Compte ? ").question == "Compte ?"
    with pytest.raises(ValidationError):
        AskRequest(question="")
    with pytest.raises(ValidationError):
        AskRequest(question="Compte", extra="x")


def test_llm_narration_is_rejected_on_unknown_number(facts, tmp_path, monkeypatch):
    agent = FinovaAnalystAgent(
        cfg={"llm": {"enabled": False}, "paths": {"reports": str(tmp_path)}},
        run_id="narration",
    )
    insight = {
        "id": "INS", "statement": "37.8 %", "evidence_ids": [facts[0]["id"]],
    }
    monkeypatch.setattr(agent, "ask_text", lambda *a, **k: "Le taux atteint 99 %.")
    assert narrate(agent, insight, facts) is None
    monkeypatch.setattr(agent, "ask_text", lambda *a, **k: "Le taux atteint 37.8 %.")
    assert narrate(agent, insight, facts) == "Le taux atteint 37.8 %."


def test_agent_is_deterministic_and_writes_reports(facts, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("deterministic analyst must not call an LLM")

    monkeypatch.setattr("biflow.agents.base.build_agent_llm", forbidden)
    agent = FinovaAnalystAgent(
        cfg={"llm": {"enabled": True}, "paths": {"reports": str(tmp_path)}},
        run_id="analyst_test",
    )
    report = agent.run({"facts": facts, "country_name": "Tunisie"})
    assert report["status"] == "success"
    assert report["outputs"]["analyst_summary"]["insights"] > 0
    assert report["outputs"]["xai"] is not None
    assert (tmp_path / "analyst_test" / "finova_analyst.json").is_file()
    assert report["warnings"] == []
