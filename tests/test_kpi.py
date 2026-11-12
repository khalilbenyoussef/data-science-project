"""KPI calculations use temporary databases only; no production writes or network."""
from dataclasses import FrozenInstanceError
import hashlib
import os
import json

import duckdb
import pytest
import yaml
from pathlib import Path

from biflow.tools.kpi import CatalogError, KpiCalculator, load_catalog


@pytest.fixture
def warehouse(tmp_path):
    path = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("CREATE TABLE country_dim (iso3 VARCHAR, is_country BOOLEAN, is_aggregate BOOLEAN)")
        con.execute("INSERT INTO country_dim VALUES ('TUN', true, false), ('XKX', true, false), ('PSE', true, false)")
        con.execute("CREATE TABLE fact (iso3 VARCHAR, year INTEGER, source VARCHAR, indicator_code VARCHAR, "
                    "dimension VARCHAR, dimension_value VARCHAR, value DOUBLE, unit VARCHAR)")
        con.executemany("INSERT INTO fact VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            ("TUN", 2024, "findex", "account_t_d", "all", "all", .42, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "gender", "female", .11, "fraction"),
            ("TUN", 2024, "findex", "g20_any", "all", "all", .35, "fraction"),
            ("TUN", 2024, "findex", "dig_acc", "all", "all", .99, "fraction"),
            ("TUN", 2024, "findex", "save_any_t_d", "all", "all", .23, "fraction"),
            ("TUN", 2024, "findex", "borrow_any_t_d", "all", "all", .31, "fraction"),
            ("TUN", 2024, "findex", "fin17a", "all", "all", .21, "fraction"),
            ("TUN", 2024, "findex", "fin22a", "all", "all", .04, "fraction"),
            ("TUN", 2024, "findex", "fin17a", "gender", "men", .29, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "gender", "men", .55, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "gender", "women", .30, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "income", "richest 60%", .50, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "income", "poorest 40%", .20, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "age_cat", "age 25+", .48, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "age_cat", "ages 15-24", .12, "fraction"),
            ("TUN", 2024, "findex", "save_any_t_d", "gender", "female", .91, "fraction"),
            ("TUN", 2024, "findex", "borrow_any_t_d", "gender", "male", .92, "fraction"),
            ("TUN", 2024, "fas", "branch_density", "bank_type", "commercial_banks", 12.5, "per_100k_adults"),
            ("TUN", 2024, "fas", "branch_density", "bank_type", "other_banks", 99, "per_100k_adults"),
            ("TUN", 2024, "fas", "loans_pct_gdp", "bank_type", "commercial_banks", 20000, "percent_of_gdp"),
            # catalogue 1.4.0 : series FAS et Findex ajoutees, sous-groupes de detention de compte
            ("TUN", 2024, "fas", "atm_density", "bank_type", "commercial_banks", 35.4, "per_100k_adults"),
            ("TUN", 2024, "fas", "depositors_per_1k", "bank_type", "commercial_banks", 1063.3, "per_1k_adults"),
            ("TUN", 2024, "fas", "borrowers_per_1k", "bank_type", "commercial_banks", 253.7, "per_1k_adults"),
            ("TUN", 2024, "fas", "deposit_accounts_per_1k", "bank_type", "commercial_banks", 1500.0, "per_1k_adults"),
            ("TUN", 2024, "fas", "loan_accounts_per_1k", "bank_type", "commercial_banks", 400.0, "per_1k_adults"),
            ("TUN", 2024, "fas", "deposits_pct_gdp", "bank_type", "commercial_banks", 71.7, "percent_of_gdp"),
            ("TUN", 2024, "findex", "fin24aP", "all", "all", .88, "fraction"),
            ("TUN", 2024, "findex", "fin24sav", "all", "all", .19, "fraction"),
            ("TUN", 2024, "findex", "fin24bor", "all", "all", .06, "fraction"),
            ("TUN", 2024, "findex", "mobileaccount_t_d", "all", "all", .03, "fraction"),
            ("TUN", 2024, "findex", "inactive_t_d", "all", "all", .03, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "education", "prim edu or less", .29, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "education", "secondary edu or more", .46, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "laborforce", "out of laborforce", .25, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "laborforce", "in laborforce", .52, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "urbanicity", "rural", .30, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "urbanicity", "urban", .47, "fraction"),
            # catalogue 1.5.0 : barrieres fin11a-f (part de tous les adultes)
            *[("TUN", 2024, "findex", code, "all", "all", value, "fraction") for code, value in (
                ("fin11a", .09), ("fin11b", .12), ("fin11c", .13), ("fin11d", .46),
                ("fin11e", .22), ("fin11f", .16))],
            ("XKX", 2024, "findex", "account_t_d", "all", "all", .6, "fraction"),
            ("PSE", 2024, "findex", "account_t_d", "all", "all", .7, "fraction"),
        ])
    return path


def change(warehouse, sql, parameters=None):
    with duckdb.connect(str(warehouse)) as con:
        con.execute(sql, parameters or [])


@pytest.mark.parametrize("kpi,expected,unit,source,indicator", [
    ("account_ownership", 42, "percent", "findex", "account_t_d"),
    ("branch_density", 12.5, "per_100k_adults", "fas", "FA26N.PHTADLT_NUM"),
    ("digital_payment_rate", 35, "percent", "findex", "g20_any"),
])
def test_verified_values_subgroups_units_and_metadata(warehouse, kpi, expected, unit, source, indicator):
    result = KpiCalculator(warehouse).calculate(" tun ", 2024, kpi)
    assert result.value == pytest.approx(expected)
    assert result.unit == unit and result.source == source
    assert result.source_indicator == indicator
    assert result.iso3 == "TUN" and result.observation_year == 2024
    assert result.availability_status == "available" and result.reason is None
    assert result.definition == load_catalog()["kpis"][kpi]["definition"]
    assert result.catalog_version == "1.7.0" and result.definition_version == "1.0.0"
    assert len(result.catalog_sha256) == 64
    assert result.publication_status == "not_evaluated"
    with pytest.raises(FrozenInstanceError):
        result.value = 0


@pytest.mark.parametrize("code,expected", [("KOS", 60), ("WBG", 70)])
def test_existing_country_aliases(warehouse, code, expected):
    assert KpiCalculator(warehouse).calculate(code, 2024, "account_ownership").value == expected


@pytest.mark.parametrize("iso3,year,kpi,reason", [
    ("TUN", 2021, "account_ownership", "missing_observation"),
    ("TUN", 2023, "account_ownership", "out_of_catalog_year"),
    ("TUN", 2011, "digital_payment_rate", "out_of_catalog_year"),
    ("FRA", 2024, "account_ownership", "country_not_in_warehouse"),
])
def test_missing_observations_are_not_zero_or_imputed(warehouse, iso3, year, kpi, reason):
    r = KpiCalculator(warehouse).calculate(iso3, year, kpi)
    assert r.value is None and r.availability_status == "unavailable" and r.reason == reason
    assert r.observation_year == year


@pytest.mark.parametrize("value,status,reason", [
    (None, "unavailable", "missing_or_nonfinite_input"),
    (float("nan"), "unavailable", "missing_or_nonfinite_input"),
    (float("inf"), "unavailable", "missing_or_nonfinite_input"),
    (-float("inf"), "unavailable", "missing_or_nonfinite_input"),
    (-.01, "requires_review", "out_of_range_input"),
    (1.01, "requires_review", "out_of_range_input"),
])
def test_bad_observations_are_not_calculated(warehouse, value, status, reason):
    change(warehouse, "UPDATE fact SET value=? WHERE indicator_code='account_t_d'", [value])
    r = KpiCalculator(warehouse).calculate("TUN", 2024, "account_ownership")
    assert r.value is None and r.availability_status == status and r.reason == reason


@pytest.mark.parametrize("kpi,indicator,value,expected", [
    ("account_ownership", "account_t_d", 0, 0),
    ("account_ownership", "account_t_d", 1, 100),
    ("digital_payment_rate", "g20_any", 0, 0),
    ("branch_density", "branch_density", 0, 0),
    ("branch_density", "branch_density", 1200, 1200),
])
def test_zero_boundaries_and_no_fas_percentage_cap(warehouse, kpi, indicator, value, expected):
    change(warehouse, "UPDATE fact SET value=? WHERE indicator_code=?", [value, indicator])
    r = KpiCalculator(warehouse).calculate("TUN", 2024, kpi)
    assert r.availability_status == "available" and r.value == expected


@pytest.mark.parametrize("unit", [None, "percent", "percent_of_gdp"])
def test_unit_mismatch_requires_review(warehouse, unit):
    change(warehouse, "UPDATE fact SET unit=? WHERE indicator_code='account_t_d'", [unit])
    r = KpiCalculator(warehouse).calculate("TUN", 2024, "account_ownership")
    assert r.value is None and r.reason == "unexpected_input_unit"


def test_duplicate_facts_require_review_even_if_identical(warehouse):
    change(warehouse, "INSERT INTO fact SELECT * FROM fact WHERE indicator_code='g20_any'")
    r = KpiCalculator(warehouse).calculate("TUN", 2024, "digital_payment_rate")
    assert r.value is None and r.availability_status == "requires_review"
    assert r.reason == "duplicate_observations"


def test_other_subgroup_is_never_a_fallback(warehouse):
    change(warehouse, "DELETE FROM fact WHERE indicator_code='account_t_d' AND dimension='all'")
    assert KpiCalculator(warehouse).calculate("TUN", 2024, "account_ownership").reason == "missing_observation"


@pytest.mark.parametrize("update", [
    "UPDATE country_dim SET is_country=NULL WHERE iso3='TUN'",
    "UPDATE country_dim SET is_aggregate=true WHERE iso3='TUN'",
    "INSERT INTO country_dim VALUES ('TUN',true,false)",
])
def test_invalid_entity_metadata_requires_review(warehouse, update):
    change(warehouse, update)
    assert KpiCalculator(warehouse).calculate("TUN", 2024, "branch_density").reason == "invalid_country_dimension"


@pytest.mark.parametrize("iso3", [None, float("nan"), "", "  ", "NAN", "ZZZ", "US", "WLD", "TUN' OR 1=1 --", 123])
def test_invalid_country_parameters(warehouse, iso3):
    with pytest.raises(ValueError, match="iso3"):
        KpiCalculator(warehouse).calculate(iso3, 2024, "account_ownership")


@pytest.mark.parametrize("year", [True, None, "2024", 2024.0, 0, 10000])
def test_invalid_year_parameters(warehouse, year):
    with pytest.raises(ValueError, match="year"):
        KpiCalculator(warehouse).calculate("TUN", year, "account_ownership")


@pytest.mark.parametrize("kpi", [None, [], "unknown", "g20_any", "account_ownership' --"])
def test_unknown_and_out_of_scope_kpis_rejected(warehouse, kpi):
    with pytest.raises(ValueError, match="unsupported KPI"):
        KpiCalculator(warehouse).calculate("TUN", 2024, kpi)


@pytest.mark.parametrize("mutation", [
    lambda c: c.update(schema_version=2),
    lambda c: c.update(catalog_version="invalid"),
    lambda c: c["kpis"].pop("account_ownership"),
    lambda c: c["kpis"]["digital_payment_rate"]["warehouse"].update(indicator_code="dig_acc"),
    lambda c: c["kpis"]["account_ownership"]["formula"].update(from_fact="value; DROP TABLE fact"),
    lambda c: c["kpis"]["branch_density"]["source"].update(indicator="OUTL_COMBANK.POGDP"),
    lambda c: c["kpis"]["account_ownership"]["verification"].update(status="provisional"),
    lambda c: c["kpis"]["branch_density"].update(valid_years=[2024, 2024]),
    lambda c: c["kpis"]["branch_density"].update(valid_years=[True]),
    lambda c: c["missing_data_policy"].update(zero_fill=True),
    lambda c: c["kpis"]["account_ownership"].update(missing_data_policy="unknown"),
    lambda c: c["kpis"]["saving_rate"]["verification"].update(status="provisional"),
    lambda c: c["kpis"]["borrowing_rate"]["warehouse"].update(dimension_value="female"),
    lambda c: c["kpis"]["unbanked_share"].update(dependencies=[]),
    lambda c: c["kpis"]["unbanked_share"].update(dependencies=["unbanked_share"]),
    lambda c: c["kpis"]["unbanked_share"].update(valid_years=[2024]),
    lambda c: c["kpis"]["unbanked_share"]["denominator"].update(population="different population"),
])
def test_invalid_catalog_is_rejected(tmp_path, warehouse, mutation):
    catalog = load_catalog()
    mutation(catalog)
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    with pytest.raises(CatalogError):
        load_catalog(path)
    with pytest.raises(CatalogError):
        KpiCalculator(warehouse, path)


@pytest.mark.parametrize("content", ["", "[]", "kpis: [", "null", "schema_version: true"])
def test_malformed_catalog(tmp_path, content):
    path = tmp_path / "bad.yaml"
    path.write_text(content)
    with pytest.raises(CatalogError):
        load_catalog(path)


def test_read_only_database_and_parameterized_queries(warehouse, monkeypatch):
    original = duckdb.connect
    calls = []

    def connect(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", connect)
    digest = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    calculator = KpiCalculator(warehouse)
    calculator.calculate("TUN", 2024, "branch_density")
    assert calls == [{"read_only": True}]
    assert hashlib.sha256(warehouse.read_bytes()).hexdigest() == digest


def test_missing_database_is_not_created(tmp_path):
    missing = tmp_path / "absent.duckdb"
    with pytest.raises(FileNotFoundError):
        KpiCalculator(missing)
    assert not missing.exists()


def test_database_schema_errors_are_not_disguised_as_missing_data(tmp_path):
    path = tmp_path / "empty.duckdb"
    duckdb.connect(str(path)).close()
    with pytest.raises(duckdb.Error):
        KpiCalculator(path).calculate("TUN", 2024, "account_ownership")


NEW_KPIS = [
    ("saving_rate", "save_any_t_d", 23, "verified"),
    ("borrowing_rate", "borrow_any_t_d", 31, "verified"),
    ("unbanked_share", "account_t_d", 58, "derived_verified"),
    ("formal_saving_rate", "fin17a", 21, "verified"),
    ("formal_borrowing_rate", "fin22a", 4, "verified"),
]


@pytest.mark.parametrize("kpi,indicator,expected,status", NEW_KPIS)
def test_remaining_kpis_values_and_metadata(warehouse, kpi, indicator, expected, status):
    r = KpiCalculator(warehouse).calculate("TUN", 2024, kpi)
    assert r.value == pytest.approx(expected)
    assert r.unit == "percent" and r.input_unit == "fraction"
    assert r.source == "findex" and r.source_indicator == indicator
    assert r.iso3 == "TUN" and r.observation_year == 2024
    assert r.subgroup == "total_population" and r.verification_status == status
    assert r.availability_status == "available" and r.publication_status == "not_evaluated"
    assert r.definition == load_catalog()["kpis"][kpi]["definition"]
    if kpi != "unbanked_share":
        assert r.dependencies == r.dependency_results == ()


def test_unbanked_reuses_validated_account_result_and_preserves_dependency(warehouse, monkeypatch):
    calculator = KpiCalculator(warehouse)
    original = calculator.calculate
    calls = []

    def calculate(iso3, year, kpi):
        calls.append((iso3, year, kpi))
        return original(iso3, year, kpi)

    monkeypatch.setattr(calculator, "calculate", calculate)
    r = calculator.calculate(" tun ", 2024, "unbanked_share")
    assert calls == [(" tun ", 2024, "unbanked_share"), ("TUN", 2024, "account_ownership")]
    assert r.dependencies == ("account_ownership",)
    account, = r.dependency_results
    assert account == original("TUN", 2024, "account_ownership")
    assert r.value == 100 - account.value
    assert r.input_value == account.input_value == .42
    assert r.catalog_sha256 == account.catalog_sha256
    assert r.publication_status == account.publication_status == "not_evaluated"


@pytest.mark.parametrize("kpi,indicator,_,status", NEW_KPIS)
@pytest.mark.parametrize("value,availability,reason", [
    (None, "unavailable", "missing_or_nonfinite_input"),
    (float("nan"), "unavailable", "missing_or_nonfinite_input"),
    (float("inf"), "unavailable", "missing_or_nonfinite_input"),
    (-.01, "requires_review", "out_of_range_input"),
    (1.01, "requires_review", "out_of_range_input"),
])
def test_remaining_kpis_propagate_bad_inputs(warehouse, kpi, indicator, _, status, value, availability, reason):
    change(warehouse, "UPDATE fact SET value=? WHERE indicator_code=?", [value, indicator])
    r = KpiCalculator(warehouse).calculate("TUN", 2024, kpi)
    assert r.value is None and r.availability_status == availability and r.reason == reason
    assert r.verification_status == status and r.publication_status == "not_evaluated"
    if kpi == "unbanked_share":
        assert r.dependency_results[0].availability_status == availability


@pytest.mark.parametrize("kpi,indicator,_,status", NEW_KPIS)
@pytest.mark.parametrize("value", [0, 1])
def test_remaining_kpis_observed_zero_and_one(warehouse, kpi, indicator, _, status, value):
    change(warehouse, "UPDATE fact SET value=? WHERE indicator_code=?", [value, indicator])
    r = KpiCalculator(warehouse).calculate("TUN", 2024, kpi)
    assert r.value == (100 - 100 * value if kpi == "unbanked_share" else 100 * value)
    assert r.availability_status == "available"


@pytest.mark.parametrize("kpi,indicator,_,status", NEW_KPIS)
@pytest.mark.parametrize("condition,reason", [
    ("missing", "missing_observation"),
    ("duplicate", "duplicate_observations"),
    ("unit", "unexpected_input_unit"),
])
def test_remaining_kpis_reject_missing_totals_duplicates_and_wrong_units(warehouse, kpi, indicator, _, status, condition, reason):
    if condition == "missing":
        # Other subgroups remain and must never substitute for the total.
        change(warehouse, "DELETE FROM fact WHERE indicator_code=? AND dimension='all'", [indicator])
    elif condition == "duplicate":
        change(warehouse, "INSERT INTO fact SELECT * FROM fact WHERE indicator_code=? AND dimension='all'", [indicator])
    else:
        change(warehouse, "UPDATE fact SET unit='percent' WHERE indicator_code=?", [indicator])
    r = KpiCalculator(warehouse).calculate("TUN", 2024, kpi)
    assert r.value is None and r.reason == reason
    assert r.availability_status == ("unavailable" if condition == "missing" else "requires_review")
    assert r.verification_status == status
    if kpi == "unbanked_share":
        assert r.dependency_results[0].reason == reason


@pytest.mark.parametrize("kpi,indicator,_,status", NEW_KPIS)
def test_remaining_kpis_no_cross_year_or_country_substitution(warehouse, kpi, indicator, _, status):
    calc = KpiCalculator(warehouse)
    for iso3, year, reason in [("TUN", 2021, "missing_observation"),
                              ("TUN", 2023, "out_of_catalog_year"),
                              ("FRA", 2024, "country_not_in_warehouse")]:
        r = calc.calculate(iso3, year, kpi)
        assert r.value is None and r.reason == reason and r.availability_status == "unavailable"
        assert r.iso3 == iso3 and r.observation_year == year and r.verification_status == status


@pytest.mark.parametrize("kpi,indicator,_,status", NEW_KPIS)
def test_remaining_kpis_read_only_and_parameterized(warehouse, monkeypatch, kpi, indicator, _, status):
    original = duckdb.connect
    calls = []

    class ReadConnection:
        def __init__(self, con):
            self.con = con

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.con.close()

        def execute(self, sql, params):
            assert sql.startswith("SELECT ") and "TUN" not in sql
            assert sql.count("?") == len(params)
            calls.append(params)
            return self.con.execute(sql, params)

    def connect(*args, **kwargs):
        assert kwargs == {"read_only": True}
        return ReadConnection(original(*args, **kwargs))

    monkeypatch.setattr(duckdb, "connect", connect)
    digest = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    KpiCalculator(warehouse).calculate("TUN", 2024, kpi)
    assert calls == [["TUN"], ["TUN", 2024, "findex", indicator, "all", "all"]]
    assert hashlib.sha256(warehouse.read_bytes()).hexdigest() == digest


@pytest.fixture
def provenance_files(warehouse):
    raw = warehouse.with_name("source.csv")
    raw.write_text("temporary source snapshot")
    source = {"path": str(raw), "sha256": hashlib.sha256(raw.read_bytes()).hexdigest(), "rows": 9}
    lineage = {
        "run_id": "test_run", "created_at": "2026-10-22T12:00:00",
        "inputs": {"findex": dict(source), "fas": dict(source)},
        "outputs": {"warehouse": str(warehouse),
                    "warehouse_sha256": hashlib.sha256(warehouse.read_bytes()).hexdigest()},
    }
    quality = {"run_id": "test_run", "inputs": {"findex": dict(source), "fas": dict(source)},
               "passed": True, "issues": [], "diagnostics": []}
    lp, qp = warehouse.with_name("lineage.json"), warehouse.with_name("quality_report.json")

    def calculator():
        lp.write_text(json.dumps(lineage))
        qp.write_text(json.dumps(quality))
        return KpiCalculator(warehouse, lineage_path=lp, quality_report_path=qp)

    return lineage, quality, calculator


@pytest.mark.parametrize("kpi", list(load_catalog()["kpis"]))
def test_provenance_for_all_six_kpis(warehouse, provenance_files, kpi):
    lineage, quality, calculator = provenance_files
    r = calculator().calculate("TUN", 2024, kpi)
    p = r.provenance
    assert p.run_id == "test_run" and p.created_at == lineage["created_at"]
    assert p.raw_source_sha256 == p.observed_raw_sha256 == lineage["inputs"][r.source]["sha256"]
    assert p.raw_source_path == lineage["inputs"][r.source]["path"] and p.raw_source_rows == 9
    assert p.warehouse_sha256 == hashlib.sha256(warehouse.read_bytes()).hexdigest()
    assert p.quality_report_sha256 == hashlib.sha256(warehouse.with_name("quality_report.json").read_bytes()).hexdigest()
    assert p.lineage_sha256 == hashlib.sha256(warehouse.with_name("lineage.json").read_bytes()).hexdigest()
    assert p.quality_association_status == "matches_lineage" and p.quality_gate_passed is True
    assert not p.issues and not r.quality_warnings
    assert r.requires_review == (r.verification_status == "provisional")
    assert r.review_reasons == (("provisional_definition",) if r.requires_review else ())
    if kpi in GAPS:
        assert r.input_fact_key is None and len(r.component_inputs) == 2
    else:  # dimension et valeur du fait = celles declarees au catalogue (sous-groupes inclus)
        mapping = load_catalog()["kpis"][kpi]["warehouse"]
        assert r.input_fact_key == ("TUN", 2024, r.source, r.indicator_code,
                                    mapping["dimension"], mapping["dimension_value"])
        assert (mapping["dimension"], mapping["dimension_value"]) == (
            ("bank_type", "commercial_banks") if r.source == "fas"
            else ("all", "all") if r.subgroup == "total_population" else (mapping["dimension"], mapping["dimension_value"]))
    assert r.formula == load_catalog()["kpis"][kpi]["formula"]["from_fact"]
    assert r.publication_status == "not_evaluated"


def diagnostic(**changes):
    return {"source": "findex", "iso3": "TUN", "year": 2024, "indicator_code": "account_t_d",
            "code": "test_review", "reason": "Review this observation", **changes}


@pytest.mark.parametrize("kpi,indicator", [("account_ownership", "account_t_d"),
    ("digital_payment_rate", "g20_any"), ("saving_rate", "save_any_t_d"),
    ("borrowing_rate", "borrow_any_t_d"), ("unbanked_share", "account_t_d")])
def test_exact_findex_input_warnings_and_dependency_propagation(provenance_files, kpi, indicator):
    _, quality, calculator = provenance_files
    quality["diagnostics"] = [diagnostic(indicator_code=indicator)]
    r = calculator().calculate("TUN", 2024, kpi)
    assert len(r.quality_warnings) == 1 and r.requires_review
    assert r.quality_warnings[0].indicator_code == indicator
    assert r.quality_warnings[0].association_status == "matches_lineage"
    assert r.quality_warnings[0].reference.endswith("#/diagnostics/0")
    assert r.quality_warnings[0].message == "Review this observation"
    assert "unresolved_input_quality_warning" in r.review_reasons
    assert r.value is not None and r.availability_status == "available"
    assert r.publication_status == "not_evaluated"
    if kpi == "unbanked_share":
        parent, = r.dependency_results
        assert r.quality_warnings == parent.quality_warnings
        assert r.provenance == parent.provenance and r.review_reasons == parent.review_reasons


@pytest.mark.parametrize("changes", [
    {"iso3": "FRA"}, {"year": 2021}, {"source": "gdp"}, {"indicator_code": "dig_acc"},
    {"dimension": "gender", "dimension_value": "female"},
])
def test_unrelated_warning_never_attaches_to_input(provenance_files, changes):
    _, quality, calculator = provenance_files
    quality["diagnostics"] = [diagnostic(**changes)]
    r = calculator().calculate("TUN", 2024, "unbanked_share")
    assert not r.quality_warnings and not r.requires_review


@pytest.mark.parametrize("identity", [
    {"indicator_code": "branch_density"},
    {"indicator_code": "FA26N.PHTADLT_NUM"},
    {"series_code": "TUN.FA26N.PHTADLT_NUM.A", "indicator_code": None},
])
def test_fas_canonical_and_series_mappings(provenance_files, identity):
    _, quality, calculator = provenance_files
    quality["diagnostics"] = [diagnostic(source="fas", **identity)]
    r = calculator().calculate("TUN", 2024, "branch_density")
    assert len(r.quality_warnings) == 1
    assert r.quality_warnings[0].indicator_code == "branch_density"
    assert r.requires_review and r.value == 12.5


def test_deposits_loans_flags_are_not_branch_warnings(provenance_files):
    _, quality, calculator = provenance_files
    quality["diagnostics"] = [diagnostic(source="fas", indicator_code="deposits_pct_gdp",
                                           series_code="TUN.OUTD_COMBANK.POGDP.A")]
    quality["issues"] = [{"source": "fas", "code": "negative_values", "message": "Source-wide issue"}]
    r = calculator().calculate("TUN", 2024, "branch_density")
    assert not r.quality_warnings and not r.requires_review
    assert len(r.source_warnings) == 1 and r.source_warnings[0].iso3 is None


def test_alias_matching_and_scoped_quality_issues(provenance_files):
    _, quality, calculator = provenance_files
    quality["issues"] = [diagnostic(iso3="KOS", year="2024")]
    r = calculator().calculate("XKX", 2024, "unbanked_share")
    assert len(r.quality_warnings) == 1 and r.quality_warnings[0].iso3 == "XKX"
    assert r.quality_warnings[0].reference.endswith("#/issues/0")


@pytest.mark.parametrize("change,expected", [
    (lambda l, q: q.pop("run_id"), "quality_provenance_unverified"),
    (lambda l, q: q.pop("inputs"), "quality_provenance_unverified"),
    (lambda l, q: q.update(run_id="other_run"), "quality_provenance_mismatch"),
    (lambda l, q: q["inputs"]["findex"].update(sha256="0" * 64), "quality_provenance_mismatch"),
    (lambda l, q: l["inputs"]["findex"].pop("sha256"), "source_version_incomplete"),
    (lambda l, q: l["inputs"].pop("findex"), "source_metadata_missing"),
    (lambda l, q: l["outputs"].pop("warehouse_sha256"), "warehouse_content_binding_unverified"),
    (lambda l, q: l["outputs"].update(warehouse_sha256="0" * 64), "warehouse_hash_mismatch"),
    (lambda l, q: l["outputs"].update(warehouse="different.duckdb"), "lineage_warehouse_path_mismatch"),
    (lambda l, q: q.update(passed=False), "quality_gate_failed"),
    (lambda l, q: q.pop("passed"), "quality_gate_unknown"),
])
def test_inconsistent_or_missing_provenance_requires_review(provenance_files, change, expected):
    lineage, quality, calculator = provenance_files
    change(lineage, quality)
    r = calculator().calculate("TUN", 2024, "account_ownership")
    assert expected in r.provenance.issues and r.requires_review
    assert r.value == 42 and r.publication_status == "not_evaluated"


@pytest.mark.parametrize("name,content,expected", [
    ("lineage.json", None, "lineage_unavailable"),
    ("quality_report.json", None, "quality_report_unavailable"),
    ("lineage.json", "[]", "lineage_invalid"),
    ("quality_report.json", "broken", "quality_report_invalid"),
])
def test_missing_or_malformed_sidecars_do_not_invent_evidence(warehouse, provenance_files, name, content, expected):
    _, _, calculator = provenance_files
    calc = calculator()
    path = warehouse.with_name(name)
    if content is None:
        path.unlink()
    else:
        path.write_text(content)
    r = calc.calculate("TUN", 2024, "unbanked_share")
    assert expected in r.provenance.issues and r.requires_review
    assert r.value == 58 and r.publication_status == "not_evaluated"
    if name == "lineage.json":
        assert r.provenance.run_id is None and r.provenance.raw_source_sha256 is None
    else:
        assert r.provenance.quality_gate_passed is None


def test_changed_source_is_disclosed_without_replacing_recorded_hash(warehouse, provenance_files):
    lineage, _, calculator = provenance_files
    calc = calculator()
    warehouse.with_name("source.csv").write_text("changed snapshot")
    r = calc.calculate("TUN", 2024, "account_ownership")
    assert "raw_source_hash_mismatch" in r.provenance.issues
    assert r.provenance.raw_source_sha256 == lineage["inputs"]["findex"]["sha256"]
    assert r.provenance.observed_raw_sha256 != r.provenance.raw_source_sha256


@pytest.mark.parametrize("record", [None, diagnostic(year=True),
    diagnostic(source="fas", indicator_code="branch_density", series_code="TUN.OUTL_COMBANK.POGDP.A")])
def test_malformed_diagnostics_are_not_assigned_invented_identity(provenance_files, record):
    _, quality, calculator = provenance_files
    quality["diagnostics"] = [record]
    r = calculator().calculate("TUN", 2024, "branch_density" if isinstance(record, dict) and record["source"] == "fas" else "account_ownership")
    assert not r.quality_warnings and r.requires_review
    assert r.provenance.issues


def test_current_report_format_is_explicitly_unverified(provenance_files):
    _, quality, calculator = provenance_files
    quality.pop("run_id")
    quality.pop("inputs")
    quality["diagnostics"] = [diagnostic()]
    r = calculator().calculate("TUN", 2024, "unbanked_share")
    assert r.provenance.quality_association_status == "unverified"
    assert r.provenance.quality_gate_passed is True
    assert r.quality_warnings[0].association_status == "unverified"
    assert r.requires_review and r.publication_status == "not_evaluated"


GAPS = {
    "gender_gap": ("gender", "men", "women", 25),
    "income_gap": ("income", "richest 60%", "poorest 40%", 30),
    "age_gap": ("age_cat", "age 25+", "ages 15-24", 36),
    # catalogue 1.6.0
    "education_gap": ("education", "secondary edu or more", "prim edu or less", 17),
    "laborforce_gap": ("laborforce", "in laborforce", "out of laborforce", 27),
    "urban_gap": ("urbanicity", "urban", "rural", 17),
}


@pytest.mark.parametrize("kpi", GAPS)
def test_gap_is_same_year_subgroup_difference_in_points(warehouse, kpi):
    dimension, first, second, expected = GAPS[kpi]
    r = KpiCalculator(warehouse).calculate("TUN", 2024, kpi)
    assert r.value == pytest.approx(expected)
    assert r.unit == "percentage_points" and r.availability_status == "available"
    assert r.verification_status == "derived_verified" and r.input_unit == "fraction"
    keys = [key for key, _ in r.component_inputs]
    assert keys == [("TUN", 2024, "findex", "account_t_d", dimension, first),
                    ("TUN", 2024, "findex", "account_t_d", dimension, second)]
    assert r.input_value is None and r.input_fact_key is None


@pytest.mark.parametrize("kpi", GAPS)
@pytest.mark.parametrize("missing", [0, 1])
def test_gap_missing_subgroup_is_unavailable_never_zero(warehouse, kpi, missing):
    dimension, first, second, _ = GAPS[kpi]
    value = (first, second)[missing]
    change(warehouse, "DELETE FROM fact WHERE indicator_code='account_t_d' AND dimension=? "
           "AND dimension_value=?", [dimension, value])
    r = KpiCalculator(warehouse).calculate("TUN", 2024, kpi)
    assert r.value is None and r.availability_status == "unavailable"
    assert r.reason == "missing_observation" and not r.component_inputs


@pytest.mark.parametrize("kpi", GAPS)
def test_gap_never_mixes_years(warehouse, kpi):
    dimension, first, _, _ = GAPS[kpi]
    # Le premier sous-groupe en 2021 ne doit pas etre combine avec l'autre en 2024
    change(warehouse, "UPDATE fact SET year=2021 WHERE indicator_code='account_t_d' AND dimension=? "
           "AND dimension_value=?", [dimension, first])
    calc = KpiCalculator(warehouse)
    valid = load_catalog()["kpis"][kpi]["valid_years"]
    for year in (2021, 2024):
        r = calc.calculate("TUN", year, kpi)
        assert r.value is None
        assert r.reason == ("missing_observation" if year in valid else "out_of_catalog_year")


@pytest.mark.parametrize("kpi", GAPS)
def test_gap_bad_subgroup_input_requires_review(warehouse, kpi):
    dimension, _, second, _ = GAPS[kpi]
    change(warehouse, "UPDATE fact SET value=1.5 WHERE indicator_code='account_t_d' AND dimension=? "
           "AND dimension_value=?", [dimension, second])
    r = KpiCalculator(warehouse).calculate("TUN", 2024, kpi)
    assert r.value is None and r.availability_status == "requires_review"
    assert "out_of_range_input" in r.review_reasons


def test_gap_catalog_dependencies_must_match_subgroup_facts(tmp_path, warehouse):
    catalog = load_catalog()
    catalog["kpis"]["income_gap"]["fact_dependencies"][1]["dimension_value"] = "poorest 20%"
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    with pytest.raises(CatalogError):
        load_catalog(path)


def test_gap_years_must_match_its_subgroup_kpis(tmp_path):
    # urbanicity n'est observe qu'en 2024 : un ecart ne peut pas declarer 2021
    catalog = load_catalog()
    catalog["kpis"]["urban_gap"]["valid_years"] = [2021, 2024]
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    with pytest.raises(CatalogError, match="urban_gap"):
        load_catalog(path)


def test_pct_gdp_plausibility_flag_reviews_only_the_flagged_row(provenance_files):
    """Catalogue 1.4.0 : seule la ligne signalee (pays, annee, serie) requiert une revue."""
    _, quality, calculator = provenance_files
    quality["diagnostics"] = [diagnostic(
        source="fas", indicator_code="loans_pct_gdp", code="fas_pct_gdp_plausibility",
        series_code="TUN.OUTL_COMBANK.POGDP.A", value=20000.0, unit="percent_of_gdp",
        reason="Value exceeds diagnostic threshold of 1000% GDP")]
    calc = calculator()
    loans = calc.calculate("TUN", 2024, "loans_pct_gdp")
    assert loans.value == 20000 and loans.availability_status == "available"  # jamais plafonne
    assert "unresolved_input_quality_warning" in loans.review_reasons
    for other in ("deposits_pct_gdp", "branch_density", "atm_density"):  # aucune revue par association
        result = calc.calculate("TUN", 2024, other)
        assert not result.quality_warnings and not result.requires_review, other


# --------------------------------------------------------------- S7 : chemins de lineage
@pytest.mark.parametrize("outside", [
    lambda root: str(root.parent / "ailleurs" / "source.csv"),            # hors du projet
    lambda root: str(root / ".." / "ailleurs" / "source.csv"),            # remontee ..
    lambda root: "C:/Windows/win.ini" if os.name == "nt" else "/etc/passwd",
])
def test_lineage_paths_outside_the_project_are_never_read(warehouse, provenance_files, monkeypatch, outside):
    from biflow import config
    from biflow.tools import kpi_provenance

    monkeypatch.setenv("BIFLOW_ALLOWED_ROOTS", str(warehouse.parent))  # racine des fixtures uniquement
    read = []
    original = kpi_provenance.cached_sha256_file
    monkeypatch.setattr(kpi_provenance, "cached_sha256_file", lambda p: read.append(Path(p)) or original(p))
    lineage, _, calculator = provenance_files
    target = outside(config.ROOT)
    for source in lineage["inputs"].values():
        source["path"] = target
    lineage["outputs"]["warehouse"] = target
    p = calculator().calculate("TUN", 2024, "account_ownership").provenance
    assert "raw_source_path_outside_project" in p.issues and "lineage_warehouse_path_invalid" in p.issues
    assert p.observed_raw_sha256 is None
    assert all(Path(item).resolve() != Path(config.resolve(target)).resolve() for item in read)
    with pytest.raises(config.PathOutsideProject, match="hors du projet"):
        config.within_project(target)
