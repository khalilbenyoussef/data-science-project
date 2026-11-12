"""Validate the declarative catalog against current contracts; do not calculate KPIs."""
from __future__ import annotations

import re
from urllib.parse import urlparse

import pytest
import yaml

from biflow.agents.etl import DERIVE_SQL, PIVOT_SQL
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
GAPS = {
    "gender_gap": ("gender", "men", "women", "gender_gap_pp"),
    "income_gap": ("income", "richest 60%", "poorest 40%", "income_gap_pp"),
    "age_gap": ("age_cat", "age 25+", "ages 15-24", "age_gap_pp"),
}

# Catalogue 1.6.0 : memes ecarts, sans colonne large (sous-groupes etendus)
GAPS_EXTENDED = {
    "education_gap": ("education", "secondary edu or more", "prim edu or less",
                      "account_ownership_secondary_or_more", "account_ownership_primary_or_less"),
    "laborforce_gap": ("laborforce", "in laborforce", "out of laborforce",
                       "account_ownership_in_laborforce", "account_ownership_out_of_laborforce"),
    "urban_gap": ("urbanicity", "urban", "rural", "account_ownership_urban", "account_ownership_rural"),
}


# Catalogue 1.4.0 (REQUEST_CATALOG) : series FAS, Findex et sous-groupes de detention de compte
FAS_NEW = {
    "atm_density": ("FA18N.PHTADLT_NUM", "per_100k_adults", "atm_per_100k"),
    "depositors_per_1k": ("FA29N_COMBANK.PTADLT_NUM", "per_1k_adults", "depositors_per_1k"),
    "borrowers_per_1k": ("FA21N_COMBANK.PTADLT_NUM", "per_1k_adults", "borrowers_per_1k"),
    "deposit_accounts_per_1k": ("FA30N_COMBANK.PTADLT_NUM", "per_1k_adults", "deposit_accounts_per_1k"),
    "loan_accounts_per_1k": ("LOANACCN_COMBANK.PTADLT_NUM", "per_1k_adults", "loan_accounts_per_1k"),
    "deposits_pct_gdp": ("OUTD_COMBANK.POGDP", "percent_of_gdp", None),
    "loans_pct_gdp": ("OUTL_COMBANK.POGDP", "percent_of_gdp", None),
}
FINDEX_NEW = {  # kpi: (code, ligne du glossaire, annees observees)
    "emergency_funds": ("fin24aP", 44, [2014, 2017, 2021, 2022, 2024]),
    "emergency_source_savings": ("fin24sav", 34, [2021, 2022, 2024]),
    "emergency_source_borrowing": ("fin24bor", 37, [2021, 2022, 2024]),
    "mobile_money_account": ("mobileaccount_t_d", 120, [2014, 2017, 2021, 2022, 2024]),
    "inactive_accounts": ("inactive_t_d", 109, [2014, 2017, 2021, 2022, 2024]),
}
SUBGROUPS = {
    "account_ownership_women": ("gender", "women"), "account_ownership_men": ("gender", "men"),
    "account_ownership_poorest_40": ("income", "poorest 40%"),
    "account_ownership_richest_60": ("income", "richest 60%"),
    "account_ownership_age_15_24": ("age_cat", "ages 15-24"),
    "account_ownership_age_25_plus": ("age_cat", "age 25+"),
    "account_ownership_primary_or_less": ("education", "prim edu or less"),
    "account_ownership_secondary_or_more": ("education", "secondary edu or more"),
    "account_ownership_out_of_laborforce": ("laborforce", "out of laborforce"),
    "account_ownership_in_laborforce": ("laborforce", "in laborforce"),
    "account_ownership_rural": ("urbanicity", "rural"),
    "account_ownership_urban": ("urbanicity", "urban"),
}


# Catalogue 1.5.0 : raisons de ne pas avoir de compte (code, ligne du glossaire 2025)
BARRIERS = {
    "barrier_too_far": ("fin11a", 6), "barrier_too_expensive": ("fin11b", 7),
    "barrier_no_documents": ("fin11c", 8), "barrier_insufficient_funds": ("fin11d", 10),
    "barrier_family_has_account": ("fin11e", 11), "barrier_no_trust": ("fin11f", 9),
}


@pytest.fixture(scope="module")
def catalog():
    return yaml.safe_load((ROOT / "config/kpi_catalog.v1.yaml").read_text(encoding="utf-8"))


def test_catalog_identity_and_versions(catalog):
    assert catalog["schema_version"] == 1
    assert catalog["catalog_version"] == "1.7.0"
    assert catalog["status"] == "draft"
    assert catalog["scope"] == "country_year_total_population_and_subgroup_gaps"
    assert set(catalog["kpis"]) == (set(EXPECTED) | set(GAPS) | set(FAS_NEW) | set(FINDEX_NEW)
                                    | set(SUBGROUPS) | set(BARRIERS) | set(GAPS_EXTENDED))
    assert {k["business_objective"] for k in catalog["kpis"].values()} == {
        "financial_inclusion", "banking_infrastructure", "digital_finance",
        "savings_deposits", "credit", "financial_exclusion_vulnerability", "financial_resilience",
    }


@pytest.mark.parametrize("kpi_id", list(EXPECTED) + list(GAPS))
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


@pytest.mark.parametrize("kpi_id", list(EXPECTED) + list(GAPS))
def test_years_are_observed_periods_within_current_etl_scope(catalog, kpi_id):
    years = catalog["kpis"][kpi_id]["valid_years"]
    assert years == sorted(set(years))
    cfg = load_config()["etl"]
    assert all(type(y) is int and cfg["min_year"] <= y <= cfg["max_year"] for y in years)
    if kpi_id == "branch_density":
        assert years == list(range(2011, 2025))
    elif kpi_id in {"account_ownership", "unbanked_share", "formal_saving_rate"} | set(GAPS):
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


@pytest.mark.parametrize("name,official,row,formal", [
    ("saving_rate", "save.any.t.d", "A121:C121", "formal_saving_rate"),
    ("borrowing_rate", "borrow.any.t.d", "A3:C3", "formal_borrowing_rate"),
])
def test_any_saving_and_borrowing_are_verified_against_glossary(catalog, name, official, row, formal):
    kpi = catalog["kpis"][name]
    assert kpi["verification"]["status"] == "verified"
    assert kpi["definition_version"] == "1.1.0"
    assert kpi["verification"]["uncertainties"]
    assert kpi["source"]["official_indicator"] == official
    reference = catalog["references"][kpi["verification"]["evidence"][0]]
    assert reference["locator"].startswith(f"Glossary!{row}, {official}")
    assert kpi["denominator"]["basis"] == "survey_weighted_population_share"
    assert kpi["reference_period"] == "past_year"
    assert formal in kpi["not_equivalent_to"]
    assert "pending" not in kpi["name"]


def test_provisional_definitions_block_publication(catalog):
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
    # Les mesures "any" restent distinctes
    assert any_kpi in kpi["not_equivalent_to"]


@pytest.mark.parametrize("kpi_id", GAPS)
def test_gap_kpis_depend_on_same_year_subgroup_facts(catalog, kpi_id):
    dimension, first, second, wide = GAPS[kpi_id]
    kpi = catalog["kpis"][kpi_id]
    mapping = kpi["warehouse"]
    assert kpi["unit"] == mapping["wide_input_unit"] == "percentage_points"
    assert (mapping["indicator_code"], mapping["dimension"]) == ("account_t_d", dimension)
    assert (mapping["dimension_value"], mapping["subtrahend_dimension_value"]) == (first, second)
    assert [(d["dimension"], d["dimension_value"]) for d in kpi["fact_dependencies"]] == [
        (dimension, first), (dimension, second)]
    assert kpi["dependencies"] == [] and "same survey year" in kpi["reference_period"]
    assert kpi["formula"] == {"from_fact": f"100 * (value[{first}] - value[{second}])", "from_wide": wide}
    assert f"AND dimension = '{dimension}' AND dimension_value = '{first}'" in PIVOT_SQL
    assert f"END AS {wide}" in DERIVE_SQL
    assert f"AND dimension = '{dimension}' AND dimension_value = '{second}'" in PIVOT_SQL


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
    assert review["implementation_status"] == "implemented_by_auditor"
    assert set(review["row_statuses"]) == {"approved", "approved_with_review_note", "blocked"}
    assert review["failed_structural_gate"] == "block_publication"
    assert review["affected_input"] == "pending_review_do_not_publish"
    assert review["diagnostic_match_key"] == ["source", "iso3", "year", "indicator_code"]
    assert {"reviewer", "reviewed_at", "decision", "rationale", "evidence_reference", "input_source_sha256"} <= set(review["required_review_fields"])
    assert review["mutate_values"] is False
    assert review["change_existing_quality_gate"] is False
    scope = review["current_diagnostic_scope"]
    assert scope["threshold_config"] in {"quality." + key for key in load_config()["quality"]}
    # catalogue 1.4.0 : les series % du PIB sont l'entree de leur seul KPI homonyme
    assert {kpi_id for kpi_id, k in catalog["kpis"].items()
            if k["warehouse"]["indicator_code"] in scope["indicators"]} == set(scope["indicators"])
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


@pytest.mark.parametrize("kpi_id", FAS_NEW)
def test_new_fas_series_are_backed_by_raw_metadata(catalog, kpi_id):
    series, unit, wide = FAS_NEW[kpi_id]
    kpi = catalog["kpis"][kpi_id]
    assert kpi["verification"]["status"] == "verified_metadata"
    reference = catalog["references"][kpi["verification"]["evidence"][0]]
    assert reference["path"] == "data/raw/fas.csv" and series in reference["locator"]
    assert kpi["source"] == {"dataset": "fas", "indicator": series, "series_code_template": f"{{iso3}}.{series}.A"}
    assert load_config()["sources"]["fas"]["series"][kpi_id] == series
    mapping = kpi["warehouse"]
    assert (mapping["indicator_code"], mapping["input_unit"], kpi["unit"]) == (kpi_id, unit, unit) == (kpi_id, UNITS[kpi_id], unit)
    assert kpi["formula"]["from_fact"] == "value"  # valeur publiee, jamais recalculee
    assert mapping["wide_column"] == wide
    if wide is not None:
        assert f"max(CASE WHEN indicator_code = '{kpi_id}' THEN value END) AS {wide}" in PIVOT_SQL
    assert kpi["valid_years"] == list(range(2011, 2025))


@pytest.mark.parametrize("kpi_id", FINDEX_NEW)
def test_new_findex_series_cite_their_glossary_row(catalog, kpi_id):
    code, row, years = FINDEX_NEW[kpi_id]
    kpi = catalog["kpis"][kpi_id]
    assert kpi["verification"]["status"] == "verified"
    reference = catalog["references"][kpi["verification"]["evidence"][0]]
    assert reference["url"] == catalog["references"]["findex_2025_glossary"]["url"]
    assert reference["locator"].startswith(f"Glossary!A{row}:C{row}, ")
    assert "(%, age 15+)" in reference["evidence"]
    assert kpi["warehouse"]["indicator_code"] == code and code in load_config()["sources"]["findex"]["indicators"]
    assert kpi["denominator"]["population"] == "all surveyed adults aged 15+"
    assert kpi["formula"]["from_fact"] == "100 * value" and kpi["unit"] == "percent"
    assert kpi["valid_years"] == years


@pytest.mark.parametrize("kpi_id", GAPS_EXTENDED)
def test_extended_gaps_follow_the_gap_pattern(catalog, kpi_id):
    dimension, first, second, first_kpi, second_kpi = GAPS_EXTENDED[kpi_id]
    kpi = catalog["kpis"][kpi_id]
    mapping = kpi["warehouse"]
    reference = catalog["kpis"]["gender_gap"]
    assert set(kpi) == set(reference)
    assert kpi["unit"] == "percentage_points" and kpi["verification"]["status"] == "derived_verified"
    assert (mapping["indicator_code"], mapping["dimension"]) == ("account_t_d", dimension)
    assert (mapping["dimension_value"], mapping["subtrahend_dimension_value"]) == (first, second)
    assert [(d["dimension"], d["dimension_value"]) for d in kpi["fact_dependencies"]] == [
        (dimension, first), (dimension, second)]
    assert kpi["formula"] == {"from_fact": f"100 * (value[{first}] - value[{second}])", "from_wide": None}
    assert mapping["wide_column"] is None  # aucune colonne large : jamais lue ailleurs
    assert kpi["dependencies"] == [] and "same survey year" in kpi["reference_period"]
    # annees : celles ou les deux sous-groupes du catalogue sont observes
    assert kpi["valid_years"] == catalog["kpis"][first_kpi]["valid_years"] == catalog["kpis"][second_kpi]["valid_years"]
    assert "findex_subgroups_extended" in kpi["verification"]["evidence"]


@pytest.mark.parametrize("kpi_id", SUBGROUPS)
def test_subgroup_kpis_read_one_findex_subgroup_each(catalog, kpi_id):
    dimension, value = SUBGROUPS[kpi_id]
    kpi = catalog["kpis"][kpi_id]
    mapping = kpi["warehouse"]
    assert (mapping["indicator_code"], mapping["dimension"], mapping["dimension_value"]) == ("account_t_d", dimension, value)
    assert kpi["formula"]["from_fact"] == "100 * value" and kpi["unit"] == "percent"
    assert value in kpi["denominator"]["population"]
    assert "findex_2025_glossary_account" in kpi["verification"]["evidence"]
    # urbanicity n'est observe que pour la vague 2024 dans le fichier brut
    assert kpi["valid_years"] == ([2024] if dimension == "urbanicity" else [2011, 2014, 2017, 2021, 2022, 2024])
    # les ecarts du catalogue restent la difference de deux de ces sous-groupes
    for gap_id, (gap_dimension, first, second, *_) in {**GAPS, **GAPS_EXTENDED}.items():
        if gap_dimension == dimension:
            assert value in (first, second)


@pytest.mark.parametrize("kpi_id", BARRIERS)
def test_barriers_state_their_all_adults_denominator(catalog, kpi_id):
    code, row = BARRIERS[kpi_id]
    kpi = catalog["kpis"][kpi_id]
    assert kpi["verification"]["status"] == "verified"
    reference = catalog["references"][kpi["verification"]["evidence"][0]]
    assert reference["locator"].startswith(f"Glossary!A{row}:C{row}, {code} ")
    assert "(%, age 15+)" in reference["evidence"] and "bank or similar financial institution account" in reference["evidence"]
    assert code in load_config()["sources"]["findex"]["indicators"]
    # denominateur = tous les adultes 15+, compte bancaire seulement, raisons non additives
    assert kpi["denominator"]["population"] == "all surveyed adults aged 15+"
    assert "all adults" in kpi["definition"] and "mobile-money" in kpi["definition"]
    assert any("do not add up to 100%" in text for text in kpi["verification"]["uncertainties"])
    assert kpi["valid_years"] == [2024] and kpi["unit"] == "percent"
    assert kpi["formula"]["from_fact"] == "100 * value"
    assert "unbanked_share" in kpi["not_equivalent_to"]
