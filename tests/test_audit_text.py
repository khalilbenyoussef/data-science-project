"""Gabarits FR/EN, extraction des nombres et reformulation LLM verifiee (LLM simule)."""
from __future__ import annotations

import pytest

from biflow.tools.audit_text import (
    change_text, extract_numbers, grounding, rephrase, render_markdown, template_text,
)

RECORD = {
    "kpi_id": "account_ownership", "kpi_name": "Account ownership rate", "iso3": "TUN", "country": "Tunisia",
    "year": 2024, "value": 37.844486, "unit": "percent", "reason": None, "publication_status": "approved",
    "transformation": "fraction Findex x 100 (part des adultes en %)",
    "transformation_en": "Findex fraction x 100 (share of adults in %)", "formula": "100 * value",
    "catalog_version": "1.3.0", "catalog_sha256": "a" * 64, "snapshot_id": "v1",
    "definition_status": "verified", "dependencies": [], "review_reasons": [], "checks": [],
    "inputs": [{"role": "valeur", "fact_key": ["TUN", 2024, "findex", "account_t_d", "all", "all"],
                "fact_value": 0.37844486, "raw": {"source": "findex", "column": "account_t_d",
                                                  "raw_value_text": "0.37844486", "snapshot_id": "v1",
                                                  "record_key": {"codewb": "TUN"}, "sha256": "35f3fa93" + "0" * 56}}],
}


def _gap(year, men, women):
    return {**RECORD, "kpi_id": "gender_gap", "kpi_name": "Account ownership gender gap", "year": year,
            "unit": "percentage_points", "value": men - women, "inputs": [],
            "dependencies": [{"label": "men", "value": men}, {"label": "women", "value": women}]}


@pytest.mark.parametrize("text,expected", [
    ("37,8 % en 2024", ["37.8", "2024"]),
    ("+6,6 pts = hommes +4.4, femmes −2.1", ["6.6", "4.4", "2.1"]),
    ("snapshot v1, sha 35f3fa93, catalogue 1.3.0", ["1.3"]),
    ("pour 100 000 adultes", ["100", "000"]),
])
def test_number_extraction_ignores_identifiers(text, expected):
    assert extract_numbers(text) == expected


def test_grounding_accepts_same_rounding_only():
    reference = "Tunisie 2024 : 37,8 %, variation +6,6 pts."
    assert grounding("En 2024, 37.8 % des adultes ; hausse de 6,6 points.", reference) == (True, [])
    assert grounding("En 2024, environ 38 % des adultes.", reference) == (False, ["38"])
    assert grounding("37,84 % en 2024", reference) == (False, ["37.84"])


@pytest.mark.parametrize("lang,expected", [
    ("fr", "Account ownership rate - Tunisia (TUN), 2024 : 37,8 %."),
    ("en", "Account ownership rate - Tunisia (TUN), 2024: 37.8 %."),
])
def test_templates_are_built_from_the_record(lang, expected):
    text = template_text(RECORD, lang)
    assert text.startswith(expected) and "0.37844486" in text and "snapshot v1" in text
    assert set(extract_numbers(text)) <= {"2024", "37.8", "0.37844486", "100"}


def test_unavailable_and_peer_templates():
    missing = {**RECORD, "iso3": "EGY", "country": "Egypt", "value": None, "reason": "missing_observation"}
    assert "indisponible (missing_observation)" in template_text(missing, "fr")
    assert "No value is imputed" in template_text(missing, "en")
    peers = {**RECORD, "iso3": "PEERS", "country": "Moyenne des pairs", "value": 47.2, "inputs": [],
             "dependencies": [{"iso3": "DZA", "value": 50.0, "included": True},
                              {"iso3": "MAR", "value": 44.4, "included": True},
                              {"iso3": "EGY", "value": None, "included": False}]}
    assert "Moyenne simple de 2 pair(s) : DZA 50,0, MAR 44,4. Pairs sans valeur : EGY." in template_text(peers, "fr")
    assert template_text(peers, "en").startswith("Account ownership rate - Peer average (PEERS)")


def test_gap_change_text_decomposes():
    from biflow.tools.audit_explain import explain_change
    left, right = _gap(2021, 45.14, 28.75), _gap(2024, 49.57, 26.61)
    text = change_text(explain_change(left, right), left, right, "fr")
    assert "16,4 pts -> Tunisia 2024 23,0 pts, variation +6,6 pts" in text
    assert "Décomposition : men +4,4 pts, women -2,1 pts." in text


class FakeLLM:
    def __init__(self, answer):
        self.answer, self.calls = answer, []

    def __call__(self, prompt, system):
        self.calls.append(prompt)
        return self.answer


def test_grounded_rephrasing_is_used():
    template = template_text(RECORD, "fr")
    llm = FakeLLM("En 2024, 37,8 % des adultes tunisiens avaient un compte (valeur brute 0.37844486, snapshot v1).")
    out = rephrase(template, "fr", llm)
    assert out["origin"] == "llm" and out["text"] == llm.answer
    assert "recopie chaque nombre" in llm.calls[0] and template in llm.calls[0]


@pytest.mark.parametrize("answer", [
    "En 2024, pres de 40 % des adultes tunisiens avaient un compte.",     # nombre invente
    "En 2024, 37,84 % des adultes avaient un compte.",                    # arrondi different
])
def test_hallucinated_number_falls_back_to_template(answer):
    template = template_text(RECORD, "fr")
    out = rephrase(template, "fr", FakeLLM(answer))
    assert out["origin"] == "template" and out["text"] == template
    assert out["llm_status"] == "rejected_ungrounded" and out["unsupported_numbers"]
    assert out["rejected_text"] == answer


@pytest.mark.parametrize("ask", [None, FakeLLM(None), FakeLLM("  ")])
def test_no_llm_or_empty_answer_uses_template(ask):
    template = template_text(RECORD, "fr")
    assert rephrase(template, "fr", ask) == {**rephrase(template, "fr", None), **(
        {} if ask is None else {"llm_status": "no_answer"})}


def test_markdown_rendering_has_narrative_and_traceability():
    md = render_markdown(RECORD, "fr")
    assert md.startswith("# Account ownership rate - Tunisia 2024")
    assert "| formula | 100 * value |" in md and "| publication_status | approved |" in md
    left, right = _gap(2021, 45.14, 28.75), _gap(2024, 49.57, 26.61)
    from biflow.tools.audit_explain import explain_change
    md = render_markdown(right, "en", explain_change(left, right), left)
    assert "## Change" in md and "Breakdown: men +4.4 pts, women -2.1 pts." in md
