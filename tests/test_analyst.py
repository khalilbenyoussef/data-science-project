from __future__ import annotations

import pandas as pd

from biflow.agents.analyst import build_facts, fallback_narrative


def _inputs():
    rows = []
    for index, iso3 in enumerate(["MAR", "FRA", "IND"]):
        for year in (2019, 2020, 2021):
            rows.append(
                {
                    "iso3": iso3,
                    "country": {"MAR": "Morocco", "FRA": "France", "IND": "India"}[iso3],
                    "year": year,
                    "account_own": 40 + index * 20 + (year - 2019) * 2,
                    "gender_gap_pp": 20 - index * 6 - (year - 2019),
                    "atm_per_100k": 20 + index * 30 + (year - 2019),
                    "brch_per_100k": 10 + index * 5 + (year - 2019),
                    "depositors_per_1k": 500 + index * 200,
                    "borrowers_per_1k": 100 + index * 50,
                    "gdp_pc": 3000 + index * 20000 + (year - 2019) * 100,
                    "region": ["MENA", "Europe", "South Asia"][index],
                    "is_country": True,
                    "is_aggregate": False,
                }
            )
    cy = pd.DataFrame(rows)
    kpis = pd.DataFrame(
        [
            {"kpi_id": "inclusion_rate", "label": "Taux", "unit": "%", "year": 2019,
             "dimension": "global", "dimension_value": "all", "value": 60.0, "n_obs": 3},
            {"kpi_id": "inclusion_rate", "label": "Taux", "unit": "%", "year": 2021,
             "dimension": "global", "dimension_value": "all", "value": 66.0, "n_obs": 3},
            {"kpi_id": "gender_gap", "label": "Ecart", "unit": "pp", "year": 2019,
             "dimension": "global", "dimension_value": "all", "value": 12.0, "n_obs": 3},
            {"kpi_id": "gender_gap", "label": "Ecart", "unit": "pp", "year": 2021,
             "dimension": "global", "dimension_value": "all", "value": 10.0, "n_obs": 3},
        ]
    )
    return cy, kpis


def test_build_facts_detects_trends_and_rankings():
    cy, kpis = _inputs()
    facts = build_facts(cy, kpis, {"top_n": 2, "correlation_min_obs": 2, "min_years": 2})

    assert facts["coverage"]["countries"] == 3
    trend = next(item for item in facts["kpi_trends"] if item["kpi_id"] == "inclusion_rate")
    assert trend["change"] == 6.0
    assert trend["cagr_pct"] is None

    ranking = facts["rankings"]["account_own"]
    assert ranking["top"][0]["iso3"] == "IND"
    assert ranking["bottom"][0]["iso3"] == "MAR"
    assert facts["correlations"]
    assert facts["improvers"]["account_own"]


def test_fallback_narrative_is_grounded_in_facts():
    cy, kpis = _inputs()
    facts = build_facts(cy, kpis, {"top_n": 3, "correlation_min_obs": 2, "min_years": 2})
    narrative = fallback_narrative(facts)

    assert narrative["executive_summary"]
    assert len(narrative["key_findings"]) >= 2
    assert len(narrative["recommendations"]) == 3
    assert any("India" in finding for finding in narrative["key_findings"])
