"""Deterministic analysis dataset; temporary databases only, no network or LLM."""
import hashlib
import json

import duckdb
import pytest
from pydantic import ValidationError

from biflow.tools.analysis import (
    AnalysisRequest, AnalysisService, comparison_id, evidence_id, trend_id,
)
from test_kpi import warehouse, provenance_files


def service_for(warehouse):
    return AnalysisService(
        warehouse,
        lineage_path=warehouse.with_name("lineage.json"),
        quality_report_path=warehouse.with_name("quality_report.json"),
    )


@pytest.fixture
def service(warehouse, provenance_files):
    _, _, write = provenance_files
    write()
    return service_for(warehouse)


def request(**payload):
    return AnalysisRequest.model_validate(payload)


def observation(dataset, iso3, kpi_id):
    return next(
        row for row in dataset["observations"]
        if row["iso3"] == iso3 and row["kpi_id"] == kpi_id
    )


def test_latest_dataset_preserves_contract_statuses_and_never_fills_zero(service):
    dataset = service.build(request(iso3=("TUN", "XKX")))
    assert dataset["schema_version"] == "1.0"
    assert dataset["publication_status"] == "not_evaluated"
    assert dataset["scope"]["ranking_rule"] == "latest_common_catalog_year"
    assert [item["iso3"] for item in dataset["scope"]["countries"]] == ["TUN", "XKX"]

    tun = observation(dataset, "TUN", "saving_rate")
    assert tun["year"] == 2024 and tun["value"] == pytest.approx(23)
    # catalogue 1.3.0 : epargne verifiee (glossaire Findex 2025), provenance liee
    assert tun["definition_status"] == "verified"
    assert tun["requires_review"] is False
    assert tun["publication_status"] == "not_evaluated"  # aucun audit dans ce warehouse
    assert set(tun["review_reasons"]) == set()

    missing = observation(dataset, "XKX", "saving_rate")
    assert missing["value"] is None and missing["year"] is None
    assert missing["availability_status"] == "unavailable"
    assert missing["reason"] == "no_available_observation"
    assert missing["selection"] == "unavailable"
    assert missing["evidence_id"] == evidence_id("saving_rate", "XKX", None)

    unbanked = observation(dataset, "TUN", "unbanked_share")
    assert unbanked["value"] == pytest.approx(58)
    assert unbanked["dependencies"] == ["account_ownership"]


def test_explicit_missing_and_out_of_catalog_years_stay_null(service):
    dataset = service.build(request(
        iso3=("TUN",), kpi_ids=("account_ownership",), mode="year", year=2021,
    ))
    row = observation(dataset, "TUN", "account_ownership")
    assert row["value"] is None and row["year"] == 2021
    assert row["selection"] == "explicit_year"
    assert row["availability_status"] == "unavailable"
    assert row["reason"] == "missing_observation"

    dataset = service.build(request(
        iso3=("TUN",), kpi_ids=("account_ownership",), mode="year", year=2023,
    ))
    row = observation(dataset, "TUN", "account_ownership")
    assert row["value"] is None
    assert row["selection"] == "out_of_catalog_year"
    assert row["reason"] == "out_of_catalog_year"


def test_latest_discloses_actual_year_instead_of_substituting(warehouse, service):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("DELETE FROM fact WHERE indicator_code='account_t_d' AND iso3='TUN'")
        con.execute("INSERT INTO fact VALUES ('TUN', 2021, 'findex', 'account_t_d', "
                    "'all', 'all', .40, 'fraction')")
    fresh = service_for(warehouse)
    dataset = fresh.build(request(iso3=("TUN",), kpi_ids=("account_ownership",)))
    row = observation(dataset, "TUN", "account_ownership")
    assert row["year"] == 2021 and row["value"] == pytest.approx(40)
    assert row["selection"] == "latest_available"
    assert row["evidence_id"] == evidence_id("account_ownership", "TUN", 2021)


def test_rankings_use_latest_common_year_and_iso_tiebreak(warehouse, service):
    dataset = service.build(request(iso3=("TUN", "XKX", "PSE"), kpi_ids=("account_ownership",)))
    ranking, = dataset["rankings"]
    assert ranking["year"] == 2024 and ranking["status"] == "complete"
    assert ranking["rule"] == "latest_common_catalog_year"
    assert [(row["iso3"], row["rank"], row["value"]) for row in ranking["rows"]] == [
        ("PSE", 1, pytest.approx(70)),
        ("XKX", 2, pytest.approx(60)),
        ("TUN", 3, pytest.approx(42)),
    ]

    with duckdb.connect(str(warehouse)) as con:
        con.execute("UPDATE fact SET value=.42 WHERE indicator_code='account_t_d' AND iso3='XKX'")
    tied = service_for(warehouse).build(
        request(iso3=("XKX", "TUN"), kpi_ids=("account_ownership",)))
    rows = tied["rankings"][0]["rows"]
    assert [row["iso3"] for row in rows] == ["TUN", "XKX"]
    assert [row["rank"] for row in rows] == [1, 2]


def test_no_common_year_disables_ranking_and_comparison_without_imputation(warehouse, service):
    with duckdb.connect(str(warehouse)) as con:
        con.execute("DELETE FROM fact WHERE indicator_code='account_t_d' AND iso3='TUN'")
        con.execute("INSERT INTO fact VALUES ('TUN', 2021, 'findex', 'account_t_d', "
                    "'all', 'all', .40, 'fraction')")
    fresh = service_for(warehouse)
    dataset = fresh.build(request(
        iso3=("TUN", "XKX"), kpi_ids=("account_ownership",), reference_iso3="TUN",
    ))
    ranking, = dataset["rankings"]
    assert ranking["status"] == "no_common_year" and ranking["year"] is None
    assert all(row["value"] is None and row["rank"] is None for row in ranking["rows"])
    comparison, = dataset["comparisons"]
    assert comparison["status"] == "no_comparable_year" and comparison["year"] is None
    assert comparison["comparison_id"] == comparison_id(
        "account_ownership", "TUN", "TUN", None)
    codes = {notice["code"] for notice in dataset["notices"]}
    assert "latest_years_differ" in codes
    assert "ranking_no_common_year" in codes


def test_comparison_is_right_minus_left_in_percentage_points(service):
    dataset = service.build(request(
        iso3=("TUN", "XKX"), kpi_ids=("account_ownership",), reference_iso3="TUN",
    ))
    comparison, = dataset["comparisons"]
    assert comparison["status"] == "complete"
    assert comparison["difference_formula"] == "right.value - left.value"
    row, = comparison["rows"]
    assert row["iso3"] == "XKX"
    assert row["reference_value"] == pytest.approx(42)
    assert row["value"] == pytest.approx(60)
    assert row["difference"] == pytest.approx(18)
    assert row["unit"] == "percentage_points"
    assert row["evidence_id"] == comparison_id("account_ownership", "XKX", "TUN", 2024)


def test_single_country_has_no_comparison_rows(service):
    dataset = service.build(request(iso3=("TUN",), kpi_ids=("account_ownership",)))
    comparison, = dataset["comparisons"]
    assert comparison["status"] == "single_country" and comparison["rows"] == []


def test_series_follows_catalog_years_without_interpolation(service):
    dataset = service.build(request(
        iso3=("TUN",), kpi_ids=("account_ownership",), trend_years=None,
    ))
    series, = dataset["series"]
    years = dataset["scope"]["kpis"][0]["valid_years"]
    assert [point["year"] for point in series["points"]] == years
    for point in series["points"]:
        expected = 42 if point["year"] == 2024 else None
        assert point["value"] == (pytest.approx(expected) if expected is not None else None)
        assert point["evidence_id"] == evidence_id("account_ownership", "TUN", point["year"])

    trimmed = service.build(request(
        iso3=("TUN",), kpi_ids=("account_ownership",), trend_years=(2017, 2024),
    ))
    assert [point["year"] for point in trimmed["series"][0]["points"]] == [2017, 2024]
    assert trimmed["trends"][0]["from_year"] == trimmed["trends"][0]["to_year"] == 2024
    assert trimmed["trends"][0]["status"] == "insufficient_observations"


def test_trend_insufficient_when_fewer_than_two_observations(service):
    dataset = service.build(request(iso3=("TUN",), kpi_ids=("account_ownership",)))
    trend, = dataset["trends"]
    assert trend["status"] == "insufficient_observations"
    assert trend["difference"] is None
    assert trend["requires_review"] is False
    assert trend["trend_id"] == trend_id("account_ownership", "TUN", 2024, 2024)
    assert trend["evidence_ids"] == [evidence_id("account_ownership", "TUN", 2024)]


def test_series_can_be_omitted(service):
    dataset = service.build(request(
        iso3=("TUN",), kpi_ids=("account_ownership",), include_series=False,
    ))
    assert dataset["series"] == []


def test_country_not_in_warehouse_is_unavailable_not_an_exception(service):
    dataset = service.build(request(
        iso3=("FRA",), kpi_ids=("account_ownership",),
    ))
    row, = dataset["observations"]
    assert row["iso3"] == "FRA" and row["value"] is None
    assert row["year"] is None and row["selection"] == "unavailable"
    assert row["availability_status"] == "unavailable"


def test_review_notices_and_provenance_are_never_upgraded(service):
    dataset = service.build(request(
        iso3=("TUN",), kpi_ids=("saving_rate", "borrowing_rate"),
    ))
    codes = {notice["code"] for notice in dataset["notices"]}
    # catalogue 1.3.0 : plus aucune definition provisoire, donc aucune notice de ce type
    assert "provisional_definition" not in codes
    assert "observation_requires_review" not in codes
    assert all(
        notice["severity"] in {"review", "warning", "info"} for notice in dataset["notices"]
    )
    provenance = dataset["provenance"]
    assert provenance["warehouse_sha256"] == hashlib.sha256(
        service.warehouse_path.read_bytes()).hexdigest()
    assert provenance["lineage_run_id"] == "test_run"
    assert provenance["quality_gate_passed"] is True
    assert provenance["content_binding"] == "recorded_and_verified"
    assert provenance["sources"] and all(item["hash_match"] for item in provenance["sources"])
    assert dataset["catalog"]["version"] == "1.6.0"


def test_review_notice_still_emitted_when_provenance_is_unbound(warehouse, provenance_files):
    _, quality, write = provenance_files
    quality.pop("run_id")  # rapport qualite non lie au run : revue requise
    write()
    dataset = service_for(warehouse).build(request(iso3=("TUN",), kpi_ids=("saving_rate", "borrowing_rate")))
    codes = {notice["code"] for notice in dataset["notices"]}
    assert "observation_requires_review" in codes
    assert all(row["requires_review"] for row in dataset["observations"])


def test_audited_publication_status_comes_from_kpi_values(warehouse, provenance_files):
    _, _, write = provenance_files
    write()
    with duckdb.connect(str(warehouse)) as con:
        con.execute("CREATE TABLE kpi_values (kpi_id VARCHAR, iso3 VARCHAR, year INTEGER, "
                    "publication_status VARCHAR)")
        con.execute("INSERT INTO kpi_values VALUES ('account_ownership', 'TUN', 2024, 'approved'), "
                    "('saving_rate', 'TUN', 2024, 'approved_with_review_note')")
    dataset = service_for(warehouse).build(request(
        iso3=("TUN",), kpi_ids=("account_ownership", "saving_rate")))
    assert observation(dataset, "TUN", "account_ownership")["publication_status"] == "approved"
    assert observation(dataset, "TUN", "saving_rate")["publication_status"] == "approved_with_review_note"
    assert dataset["publication_status"] == "approved_with_review_note"  # le plus restrictif
    mixed = service_for(warehouse).build(request(
        iso3=("TUN", "XKX"), kpi_ids=("account_ownership",)))
    assert mixed["publication_status"] == "not_evaluated"  # une ligne non auditee


def test_provenance_discloses_recorded_path_mismatch(warehouse, provenance_files):
    lineage, _, write = provenance_files
    lineage["outputs"]["warehouse"] = "C:/elsewhere/warehouse.duckdb"
    write()
    dataset = service_for(warehouse).build(
        request(iso3=("TUN",), kpi_ids=("account_ownership",)))
    provenance = dataset["provenance"]
    assert provenance["recorded_warehouse_path"] == "C:/elsewhere/warehouse.duckdb"
    assert "lineage_warehouse_path_mismatch" in provenance["issues"]
    assert dataset["publication_status"] == "not_evaluated"


def test_read_only_connections_and_warehouse_unchanged(service, warehouse, monkeypatch):
    original = duckdb.connect
    calls = []

    def connect(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", connect)
    digest = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    service.build(request(iso3=("TUN", "XKX"), kpi_ids=("account_ownership",)))
    assert calls and all(call == {"read_only": True} for call in calls)
    assert hashlib.sha256(warehouse.read_bytes()).hexdigest() == digest


@pytest.mark.parametrize("payload", [
    {"iso3": ()},
    {"iso3": ("WLD",)},
    {"iso3": ("TUN",), "kpi_ids": ("unknown",)},
    {"iso3": ("TUN",), "mode": "year"},
    {"iso3": ("TUN",), "year": 2024},
    {"iso3": ("TUN",), "mode": "year", "year": 0},
    {"iso3": ("TUN", "XKX"), "reference_iso3": "PSE"},
    {"iso3": ("TUN",), "top_n": 0},
    {"iso3": ("TUN",), "action": "other"},
    {"iso3": ("TUN",), "trend_years": (2024, 2024)},
    {"iso3": ("TUN",), "include_series": "yes"},
])
def test_invalid_requests_are_rejected_before_data_access(payload):
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(payload)


def test_request_normalizes_deduplicates_and_sorts(service):
    dataset = service.build(request(
        iso3=(" tun ", "TUN"),
        kpi_ids=("saving_rate", "account_ownership", "saving_rate"),
        mode="year", year=2024, trend_years=(2024, 2017),
    ))
    assert dataset["request"]["iso3"] == ["TUN"]
    assert dataset["request"]["kpi_ids"] == ["saving_rate", "account_ownership"]
    assert dataset["request"]["trend_years"] == [2017, 2024]


def test_dataset_is_json_serializable(service):
    dataset = service.build(request(iso3=("TUN",), kpi_ids=("account_ownership",)))
    encoded = json.dumps(dataset, allow_nan=False)
    assert json.loads(encoded)["observations"][0]["value"] == pytest.approx(42)
