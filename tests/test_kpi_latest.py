"""Latest mode uses only catalog years and validated, same-year inputs."""
from dataclasses import asdict
import hashlib
import logging

import duckdb
import pytest
from pydantic import ValidationError

from biflow.agents import SemanticKpiAgent
from biflow.tools.kpi import KpiCalculator, load_catalog
from biflow.tools.semantic_kpi import (
    CalculateKpiRequest, LatestAvailableKpiRequest, RESPONSE_ADAPTER,
)
from test_kpi import warehouse, provenance_files, change
from test_semantic_kpi import agent


@pytest.mark.parametrize("kpi_id", list(load_catalog()["kpis"]))
def test_latest_all_six_preserves_explicit_result(agent, kpi_id):
    explicit = agent.calculate_kpi(CalculateKpiRequest(iso3="TUN", year=2024, kpi_id=kpi_id))
    latest = agent.latest_available(LatestAvailableKpiRequest(iso3=" tun ", kpi_id=kpi_id))
    assert asdict(latest.result) == asdict(explicit.result)
    assert latest.observation_year == latest.result.observation_year == 2024
    assert latest.availability_status == "available" and latest.reason is None
    assert not latest.skipped_observations
    assert latest.result.publication_status == "not_evaluated"
    restored = RESPONSE_ADAPTER.validate_json(latest.model_dump_json())
    assert asdict(restored.result) == asdict(latest.result)


@pytest.mark.parametrize("kpi_id,indicator,year", [
    ("account_ownership", "account_t_d", 2017),
    ("branch_density", "branch_density", 2019),
    ("digital_payment_rate", "g20_any", 2014),
    ("saving_rate", "save_any_t_d", 2021),
    ("borrowing_rate", "borrow_any_t_d", 2017),
    ("unbanked_share", "account_t_d", 2011),
])
def test_historical_observation_and_missing_waves(agent, warehouse, kpi_id, indicator, year):
    change(warehouse, "UPDATE fact SET year=? WHERE indicator_code=?", [year, indicator])
    latest = agent.latest_available(LatestAvailableKpiRequest(iso3="TUN", kpi_id=kpi_id))
    assert latest.observation_year == year
    assert latest.result.observation_year == year
    assert all(r.observation_year > year for r in latest.skipped_observations)
    assert latest.skipped_observations[0].observation_year == 2024
    explicit = agent.calculate_kpi(CalculateKpiRequest(iso3="TUN", year=2024, kpi_id=kpi_id)).result
    assert explicit.value is None and explicit.reason == "missing_observation"
    assert asdict(latest.result) == asdict(agent.calculate_kpi(
        CalculateKpiRequest(iso3="TUN", year=year, kpi_id=kpi_id)).result)
    if kpi_id == "unbanked_share":
        parent, = latest.result.dependency_results
        assert parent.observation_year == year
        assert latest.result.value == 100 - parent.value


@pytest.mark.parametrize("bad,reason", [
    (None, "missing_or_nonfinite_input"), (float("nan"), "missing_or_nonfinite_input"),
    (float("inf"), "missing_or_nonfinite_input"), (-.1, "out_of_range_input"),
    (1.1, "out_of_range_input"),
])
def test_invalid_recent_values_are_disclosed_not_used(agent, warehouse, bad, reason):
    change(warehouse, "INSERT INTO fact SELECT iso3,2021,source,indicator_code,dimension,dimension_value,.3,unit "
                      "FROM fact WHERE indicator_code='account_t_d' AND dimension='all' AND iso3='TUN'")
    change(warehouse, "UPDATE fact SET value=? WHERE year=2024 AND indicator_code='account_t_d' AND iso3='TUN'", [bad])
    response = agent.latest_available(LatestAvailableKpiRequest(iso3="TUN", kpi_id="unbanked_share"))
    assert response.observation_year == 2021 and response.result.value == 70
    assert response.skipped_observations[0].reason == reason
    assert response.skipped_observations[0].observation_year == 2024
    assert response.result.dependency_results[0].observation_year == 2021


@pytest.mark.parametrize("condition,reason", [("unit", "unexpected_input_unit"), ("duplicate", "duplicate_observations")])
def test_wrong_unit_and_duplicate_recent_year(agent, warehouse, condition, reason):
    change(warehouse, "INSERT INTO fact SELECT iso3,2021,source,indicator_code,dimension,dimension_value,value,unit "
                      "FROM fact WHERE indicator_code='save_any_t_d' AND dimension='all'")
    if condition == "unit":
        change(warehouse, "UPDATE fact SET unit='percent' WHERE indicator_code='save_any_t_d' AND year=2024")
    else:
        change(warehouse, "INSERT INTO fact SELECT * FROM fact WHERE indicator_code='save_any_t_d' AND year=2024")
    r = agent.latest_available(LatestAvailableKpiRequest(iso3="TUN", kpi_id="saving_rate"))
    assert r.observation_year == 2021 and r.result.verification_status == "provisional"
    assert r.skipped_observations[0].reason == reason


def test_subgroups_and_out_of_catalog_year_never_substitute(agent, warehouse):
    change(warehouse, "UPDATE fact SET year=2021 WHERE indicator_code='account_t_d' AND dimension='all'")
    change(warehouse, "INSERT INTO fact VALUES ('TUN',2025,'findex','account_t_d','all','all',.99,'fraction')")
    latest = agent.latest_available(LatestAvailableKpiRequest(iso3="TUN", kpi_id="account_ownership"))
    assert latest.observation_year == 2021 and latest.result.value == 42
    # Female 2024 and the 2025 total are not selected.
    assert latest.result.input_fact_key == ("TUN", 2021, "findex", "account_t_d", "all", "all")


@pytest.mark.parametrize("kpi_id", ["account_ownership", "branch_density", "unbanked_share"])
def test_no_observations_has_no_fabricated_year(agent, warehouse, kpi_id):
    change(warehouse, "DELETE FROM fact WHERE iso3='TUN' AND dimension IN ('all','bank_type')")
    response = agent.latest_available(LatestAvailableKpiRequest(iso3="TUN", kpi_id=kpi_id))
    assert response.result is None and response.observation_year is None
    assert response.availability_status == "unavailable" and response.reason == "no_available_observation"
    assert response.skipped_observations
    assert all(r.value is None and r.publication_status == "not_evaluated" for r in response.skipped_observations)


def test_absent_country_stops_search_without_substitution(agent):
    response = agent.latest_available(LatestAvailableKpiRequest(iso3="FRA", kpi_id="account_ownership"))
    assert response.result is None and len(response.skipped_observations) == 1
    assert response.skipped_observations[0].reason == "country_not_in_warehouse"


def test_observed_zero_is_latest_available(agent, warehouse):
    change(warehouse, "UPDATE fact SET value=0 WHERE indicator_code='account_t_d'")
    r = agent.latest_available(LatestAvailableKpiRequest(iso3="TUN", kpi_id="account_ownership"))
    assert r.observation_year == 2024 and r.result.value == 0


def test_warning_propagation_does_not_silently_choose_cleaner_year(warehouse, provenance_files):
    _, quality, calculator = provenance_files
    quality["diagnostics"] = [{"source": "findex", "iso3": "TUN", "year": 2024,
                               "indicator_code": "account_t_d", "code": "review", "reason": "Review"}]
    calculator()
    agent = SemanticKpiAgent(cfg={}, warehouse_path=warehouse, log=logging.getLogger("latest_test"),
                             quality_report_path=warehouse.with_name("quality_report.json"))
    response = agent.latest_available(LatestAvailableKpiRequest(iso3="TUN", kpi_id="unbanked_share"))
    r = response.result
    assert r.observation_year == r.dependency_results[0].observation_year == 2024
    assert r.requires_review and len(r.quality_warnings) == 1
    assert r.quality_warnings == r.dependency_results[0].quality_warnings
    assert r.publication_status == "not_evaluated"


@pytest.mark.parametrize("extra", [{"year": 2024}, {"iso3": "WLD"}, {"mode": "implicit"}])
def test_latest_request_is_explicit_and_rejects_ambiguous_parameters(agent, extra):
    request = {"action": "latest_available", "iso3": "TUN", "kpi_id": "account_ownership", **extra}
    with pytest.raises(ValidationError):
        agent.execute({"semantic_kpi_request": request})


def test_latest_tool_state_dispatch_and_read_only(agent, warehouse, monkeypatch):
    digest = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    original = duckdb.connect
    def connect(*args, **kwargs):
        assert kwargs == {"read_only": True}
        return original(*args, **kwargs)
    monkeypatch.setattr(duckdb, "connect", connect)
    tool = {t.name: t for t in agent.get_tools()}["latest_available"]
    request = {"iso3": "TUN", "kpi_id": "branch_density"}
    payload = tool.invoke(request)
    output = agent.execute({"semantic_kpi_request": {"action": "latest_available", **request}})
    assert payload == output["semantic_kpi_response"]
    assert payload["observation_year"] == 2024 and payload["result"]["value"] == 12.5
    assert hashlib.sha256(warehouse.read_bytes()).hexdigest() == digest
    with pytest.raises(ValueError, match="Unknown KPI"):
        tool.invoke({"iso3": "TUN", "kpi_id": "unknown"})


def test_calculator_latest_validates_parameters(warehouse):
    calc = KpiCalculator(warehouse)
    with pytest.raises(ValueError, match="iso3"):
        calc.calculate_latest("NAN", "account_ownership")
    with pytest.raises(ValueError, match="unsupported KPI"):
        calc.calculate_latest("TUN", "unknown")
