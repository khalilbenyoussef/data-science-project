"""Validate the declarative catalog against current contracts; do not calculate KPIs."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import pytest
import yaml

from biflow.agents.etl import PIVOT_SQL
from biflow.config import ROOT, load_config
from biflow.tools.dictionary import INDICATOR_SOURCE, UNITS


EXPECTED = {
    "account_ownership": ("findex", "account_t_d", "account_own", "100 * value", "account_own"),
    "branch_density": ("fas", "branch_density", "brch_per_100k", "value", "brch_per_100k"),
    "digital_payment_rate": ("findex", "g20_any", "digital_payment", "100 * value", "digital_payment"),
    "saving_rate": ("findex", "save_any_t_d", "savings", "100 * value", "savings"),
    "borrowing_rate": ("findex", "borrow_any_t_d", "borrowing", "100 * value", "borrowing"),
    "unbanked_share": ("findex", "account_t_d", "account_own", "100 * (1 - value)", "100 - account_own"),
    "formal_saving_rate": ("findex", "fin17a", "formal_saving", "100 * value", "formal_saving"),
    "formal_borrowing_rate": ("findex", "fin22a", "formal_borrowing", "100 * value", "formal_borrowing"),
}


@pytest.fixture(scope="module")
def catalog():
    return yaml.safe_load((ROOT / "config/kpi_catalog.v1.yaml").read_text(encoding="utf-8"))


def test_catalog_identity_and_versions(catalog):
    assert catalog["schema_version"] == 1
    assert catalog["catalog_version"] == "1.1.0"
    assert catalog["status"] == "draft"
    assert catalog["scope"] == "country_year_total_population"
    assert set(catalog["kpis"]) == set(EXPECTED)
    assert {k["business_objective"] for k in catalog["kpis"].values()} == {
        "financial_inclusion", "banking_infrastructure", "digital_finance",
        "savings_deposits", "credit", "financial_exclusion_vulnerability",
    }


@pytest.mark.parametrize("kpi_id", EXPECTED)
def test_each_definition_is_complete_and_links_to_declared_policies(catalog, kpi_id):
    kpi = catalog["kpis"][kpi_id]
    required = {
        "definition_version", "name", "business_objective", "definition", "verification",
        "source", "warehouse", "formula", "unit", "denominator", "subgroup", "reference_period",
        "valid_years", "year_evidence", "aggregation", "dependencies",
        "missing_data_policy", "aggregation_policy", "traceability_policy", "publication_review_policy",
    }
    assert required <= set(kpi)
    assert re.fullmatch(r"\d+\.\d+\.\d+", kpi["definition_version"])
    assert kpi["name"] and kpi["definition"] and kpi["reference_period"]
    assert {"population", "basis"} <= set(kpi["denominator"])
    assert kpi["year_evidence"] in catalog["references"]
    for policy in ("missing_data_policy", "aggregation_policy", "traceability_policy", "publication_review_policy"):
        assert kpi[policy] == catalog[policy]["id"]
    assert set(kpi["verification"]["evidence"]) <= set(catalog["references"])
    assert kpi["verification"]["evidence"]


@pytest.mark.parametrize("kpi_id", EXPECTED)
def test_source_units_formulas_and_warehouse_mappings_match_existing_etl(catalog, kpi_id):
    source, code, wide, fact_formula, wide_formula = EXPECTED[kpi_id]
    kpi = catalog["kpis"][kpi_id]
    mapping = kpi["warehouse"]
    assert mapping["fact_table"] == "fact"
    assert mapping["wide_table"] == "country_year"
    assert mapping["source"] == kpi["source"]["dataset"] == source == INDICATOR_SOURCE[code]
    assert mapping["indicator_code"] == code
    assert mapping["wide_column"] == wide
    assert mapping["input_unit"] == UNITS[code]
    assert kpi["formula"] == {"from_fact": fact_formula, "from_wide": wide_formula}
    cfg = load_config()
    if source == "findex":
        assert kpi["source"]["indicator"] == code
        assert code in cfg["sources"]["findex"]["indicators"]
        assert mapping["dimension"] == mapping["dimension_value"] == "all"
        assert kpi["subgroup"] == "total_population"
        assert kpi["unit"] == mapping["wide_input_unit"] == "percent"
        condition, scale = " AND dimension_value = 'all'", " * 100"
    else:
        assert kpi["source"]["indicator"] == cfg["sources"]["fas"]["series"][code]
        assert kpi["source"]["series_code_template"] == "{iso3}.FA26N.PHTADLT_NUM.A"
        assert (mapping["dimension"], mapping["dimension_value"]) == ("bank_type", "commercial_banks")
        assert kpi["unit"] == mapping["wide_input_unit"] == "per_100k_adults"
        condition, scale = "", ""
    assert f"max(CASE WHEN indicator_code = '{code}'{condition} THEN value END){scale} AS {wide}" in PIVOT_SQL


@pytest.mark.parametrize("kpi_id", EXPECTED)
def test_years_are_observed_periods_within_current_etl_scope(catalog, kpi_id):
    years = catalog["kpis"][kpi_id]["valid_years"]
    assert years == sorted(set(years))
    cfg = load_config()["etl"]
    assert all(type(y) is int and cfg["min_year"] <= y <= cfg["max_year"] for y in years)
    if kpi_id == "branch_density":
        assert years == list(range(2011, 2025))
    elif kpi_id in {"account_ownership", "unbanked_share", "formal_saving_rate"}:
        assert years == [2011, 2014, 2017, 2021, 2022, 2024]
    else:
        assert years == [2014, 2017, 2021, 2022, 2024]


def test_digital_payments_cannot_be_confused_with_accounts_or_remittances(catalog):
    kpi = catalog["kpis"]["digital_payment_rate"]
    assert kpi["verification"]["status"] == "verified"
    assert kpi["source"]["official_indicator"] == "g20.any"
    assert kpi["reference_period"] == "past_year"
    assert {"dig_acc", "digitally_enabled_account", "remittance_use", "transaction_frequency"} <= set(kpi["not_equivalent_to"])
    assert "findex_2025_glossary" in kpi["verification"]["evidence"]


def test_unverified_saving_and_borrowing_definitions_cannot_be_published(catalog):
    for name in ("saving_rate", "borrowing_rate"):
        kpi = catalog["kpis"][name]
        assert kpi["verification"]["status"] == "provisional"
        assert kpi["verification"]["uncertainties"]
        assert kpi["source"]["official_indicator"] is None
        assert kpi["denominator"]["basis"] == "source_verification_required"
        assert kpi["reference_period"] == "unverified"
        assert "pending verification" in kpi["name"]
    assert catalog["publication_review_policy"]["provisional_definition"] == "block_publication_until_definition_verified"
    assert catalog["kpis"]["branch_density"]["verification"]["status"] == "verified_metadata"


@pytest.mark.parametrize("kpi_id,code,row,any_kpi", [
    ("formal_saving_rate", "fin17a", "A24:C24", "saving_rate"),
    ("formal_borrowing_rate", "fin22a", "A31:C31", "borrowing_rate"),
])
def test_formal_saving_and_borrowing_are_verified_against_glossary(catalog, kpi_id, code, row, any_kpi):
    kpi = catalog["kpis"][kpi_id]
    assert kpi["verification"]["status"] == "verified"
    assert kpi["source"] == {"dataset": "findex", "indicator": code, "official_indicator": code}
    reference = catalog["references"][kpi["verification"]["evidence"][0]]
    assert reference["url"] == catalog["references"]["findex_2025_glossary"]["url"]
    assert reference["locator"].startswith(f"Glossary!{row}, {code}")
    assert kpi["reference_period"] == "past_year"
    # Les mesures "any" restent distinctes et provisoires
    assert any_kpi in kpi["not_equivalent_to"]
    assert catalog["kpis"][any_kpi]["verification"]["status"] == "provisional"


def test_missing_data_never_becomes_a_zero_or_an_imputed_wave(catalog):
    policy = catalog["missing_data_policy"]
    assert policy["nonfinite_input"] == "unavailable"
    assert policy["out_of_range_input"] == "require_review_never_clamp"
    assert policy["zero_is_observed_value"] is True
    for key in ("zero_fill", "interpolate", "forward_fill", "substitute_other_indicator"):
        assert policy[key] is False
    for key in ("null_result", "absent_country_year", "unavailable_survey_year"):
        assert policy[key] == "unavailable"
    assert policy["partial_wave_years"] == [2022]
    assert "missing dependency" in policy["derived_kpis"]


def test_aggregation_requires_compatible_weights_and_excludes_source_aggregates(catalog):
    policy = catalog["aggregation_policy"]
    assert "is_country = true" in policy["entity_filter"]
    assert "is_aggregate = false" in policy["entity_filter"]
    assert policy["country_rollup"]["default"] == "unavailable_without_validated_weights"
    assert len(policy["country_rollup"]["requirements"]) >= 5
    assert policy["country_rollup"]["candidate_weights"] == "population.pop_adult joined on iso3 and year"
    for kpi in catalog["kpis"].values():
        assert kpi["aggregation"]["over_time"] == "none"
        assert kpi["aggregation"]["subgroup_rollup"] == "none"
        assert kpi["aggregation"]["country_year"] == "unique_observation"


def test_traceability_and_review_cover_all_inputs_and_derived_dependencies(catalog):
    trace = catalog["traceability_policy"]
    assert {"catalog_version", "catalog_sha256", "definition_version", "raw_source_sha256",
            "source_indicator", "input_fact_key", "input_value", "input_unit", "formula",
            "quality_report_sha256", "diagnostic_references", "review_record_ids"} <= set(trace["required_result_fields"])
    assert trace["missing_provenance"] == "block_publication"
    review = catalog["publication_review_policy"]
    assert review["implementation_status"] == "specification_only"
    assert review["failed_structural_gate"] == "block_publication"
    assert review["affected_input"] == "pending_review_do_not_publish"
    assert review["diagnostic_match_key"] == ["source", "iso3", "year", "indicator_code"]
    assert {"reviewer", "reviewed_at", "decision", "rationale", "evidence_reference", "input_source_sha256"} <= set(review["required_review_fields"])
    assert review["mutate_values"] is False
    assert review["change_existing_quality_gate"] is False
    scope = review["current_diagnostic_scope"]
    assert scope["threshold_config"] in {"quality." + key for key in load_config()["quality"]}
    assert set(scope["indicators"]).isdisjoint(k["warehouse"]["indicator_code"] for k in catalog["kpis"].values())
    assert "inherit" in review["derived_kpis"]
    derived = catalog["kpis"]["unbanked_share"]
    parent = catalog["kpis"]["account_ownership"]
    assert derived["dependencies"] == ["account_ownership"]
    assert derived["denominator"] == parent["denominator"]
    assert derived["warehouse"] == parent["warehouse"]
    assert derived["valid_years"] == parent["valid_years"]
    for name, kpi in catalog["kpis"].items():
        assert set(kpi["dependencies"]) <= set(catalog["kpis"]) - {name}


def test_external_references_are_existing_world_bank_documentation(catalog):
    for reference in catalog["references"].values():
        assert reference["locator"] and reference["evidence"]
        if "url" in reference:
            parsed = urlparse(reference["url"])
            assert parsed.scheme == "https"
            assert parsed.hostname.endswith(".worldbank.org")
