"""Explicit comparisons preserve operands and never perform year fallback."""
from dataclasses import asdict
import hashlib
import logging

import duckdb
import pytest
from pydantic import ValidationError

from biflow.agents import SemanticKpiAgent
from biflow.tools.semantic_kpi import (
    CompareCountriesRequest, CompareYearsRequest, RESPONSE_ADAPTER,
)
from test_kpi import warehouse, provenance_files, change
from test_semantic_kpi import agent


@pytest.fixture
def comparison_agent(agent, warehouse):
    change(warehouse, "DELETE FROM fact WHERE iso3='XKX'")
    change(warehouse, "INSERT INTO fact SELECT 'XKX',year,source,indicator_code,dimension,dimension_value,"
                      "CASE WHEN unit='fraction' THEN value+.1 ELSE value+3 END,unit FROM fact WHERE iso3='TUN'")
    change(warehouse, "INSERT INTO fact SELECT iso3,2017,source,indicator_code,dimension,dimension_value,"
                      "CASE WHEN unit='fraction' THEN value-.1 ELSE value-2 END,unit FROM fact WHERE iso3='TUN'")
    return agent


@pytest.mark.parametrize("kpi_id,unit,delta", [
    ("account_ownership", "percentage_points", 10),
    ("digital_payment_rate", "percentage_points", 10),
    ("saving_rate", "percentage_points", 10),
    ("borrowing_rate", "percentage_points", 10),
    ("unbanked_share", "percentage_points", -10),
    ("branch_density", "per_100k_adults", 3),
])
def test_country_differences_all_six(comparison_agent, kpi_id, unit, delta):
    r = comparison_agent.compare_countries(CompareCountriesRequest(
        kpi_id=kpi_id, left_iso3="TUN", right_iso3="KOS", year=2024))
    assert r.comparison_status == "complete" and r.difference == pytest.approx(delta)
    assert r.difference_unit == unit and r.difference_formula == "right.value - left.value"
    assert r.left.iso3 == "TUN" and r.right.iso3 == "XKX"
    assert r.left.observation_year == r.right.observation_year == 2024
    assert r.publication_status == r.left.publication_status == r.right.publication_status == "not_evaluated"
    assert asdict(RESPONSE_ADAPTER.validate_json(r.model_dump_json()).left) == asdict(r.left)
    if kpi_id in {"saving_rate", "borrowing_rate"}:
        assert r.left.verification_status == r.right.verification_status == "verified"
        assert "provisional_definition" not in r.review_reasons


@pytest.mark.parametrize("kpi_id,delta,unit", [("account_ownership", 10, "percentage_points"),
    ("branch_density", 2, "per_100k_adults"), ("unbanked_share", -10, "percentage_points")])
def test_year_differences_are_not_relative_growth(comparison_agent, kpi_id, delta, unit):
    r = comparison_agent.compare_years(CompareYearsRequest(
        kpi_id=kpi_id, iso3="TUN", left_year=2017, right_year=2024))
    assert r.difference == pytest.approx(delta) and r.difference_unit == unit
    assert (r.left.observation_year, r.right.observation_year) == (2017, 2024)
    if kpi_id == "unbanked_share":
        assert r.left.dependency_results[0].observation_year == 2017
        assert r.right.dependency_results[0].observation_year == 2024
    reverse = comparison_agent.compare_years(CompareYearsRequest(
        kpi_id=kpi_id, iso3="TUN", left_year=2024, right_year=2017))
    assert reverse.difference == pytest.approx(-delta)


@pytest.mark.parametrize("country", ["TUN", "FRA"])
def test_missing_side_never_uses_latest(agent, country, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Comparisons must never call latest_available")
    monkeypatch.setattr(agent.tools, "latest_available", forbidden)
    r = agent.compare_countries(CompareCountriesRequest(
        kpi_id="account_ownership", left_iso3=country, right_iso3="XKX", year=2021))
    assert r.comparison_status == "incomplete" and r.difference is None
    assert r.left.value is None and r.right.value is None
    assert r.left.observation_year == r.right.observation_year == 2021
    assert r.requires_review and r.reason == "left_and_right_observation_unavailable"


@pytest.mark.parametrize("left,right", [(2023,2024), (2024,2021), (2023,2021)])
def test_incomplete_year_comparisons_preserve_available_side(agent, left, right):
    r = agent.compare_years(CompareYearsRequest(
        kpi_id="account_ownership", iso3="TUN", left_year=left, right_year=right))
    assert r.difference is None and r.comparison_status == "incomplete"
    assert r.left.observation_year == left and r.right.observation_year == right
    if right == 2024:
        assert r.right.value == 42
    if left == 2024:
        assert r.left.value == 42


@pytest.mark.parametrize("value", [None, float("inf"), -.1, 1.1])
def test_invalid_input_gives_incomplete_comparison(agent, warehouse, value):
    change(warehouse, "UPDATE fact SET value=? WHERE iso3='XKX'", [value])
    r = agent.compare_countries(CompareCountriesRequest(
        kpi_id="account_ownership", left_iso3="TUN", right_iso3="XKX", year=2024))
    assert r.difference is None and r.comparison_status == "incomplete"
    assert r.left.value == 42 and r.right.value is None
    assert r.reason == "right_observation_unavailable"


def test_observed_zero_is_not_missing(agent, warehouse):
    change(warehouse, "UPDATE fact SET value=0 WHERE iso3 IN ('TUN','XKX') AND indicator_code='account_t_d'")
    r = agent.compare_countries(CompareCountriesRequest(
        kpi_id="account_ownership", left_iso3="TUN", right_iso3="XKX", year=2024))
    assert r.difference == 0 and r.comparison_status == "complete"


def test_exact_warnings_and_derived_dependencies_preserved(warehouse, provenance_files):
    _, quality, calculator = provenance_files
    quality["diagnostics"] = [{"source":"findex", "iso3":"XKX", "year":2024,
        "indicator_code":"account_t_d", "code":"review_input", "reason":"Check source"}]
    calculator()
    agent = SemanticKpiAgent(cfg={}, log=logging.getLogger("compare_test"), warehouse_path=warehouse,
                             quality_report_path=warehouse.with_name("quality_report.json"))
    r = agent.compare_countries(CompareCountriesRequest(
        kpi_id="unbanked_share", left_iso3="TUN", right_iso3="XKX", year=2024))
    assert r.difference == -18 and r.comparison_status == "complete"
    assert not r.left.quality_warnings and r.quality_warnings == r.right.quality_warnings
    assert r.right.quality_warnings == r.right.dependency_results[0].quality_warnings
    assert r.requires_review and "unresolved_input_quality_warning" in r.review_reasons
    assert r.left.provenance.run_id == r.right.provenance.run_id == "test_run"


@pytest.mark.parametrize("changes", [{"year":True}, {"year":"2024"}, {"left_iso3":"WLD"},
    {"right_year":2021}, {"mode":"latest_available"}, {"publication_status":"approved"}])
def test_country_request_rejects_invalid_or_ambiguous_fields(changes):
    with pytest.raises(ValidationError):
        CompareCountriesRequest.model_validate(dict(kpi_id="account_ownership", left_iso3="TUN",
            right_iso3="XKX", year=2024, **{}) | changes)


@pytest.mark.parametrize("changes", [{"left_year":"2021"}, {"right_year":False}, {"iso3":"NAN"}, {"year":2024}])
def test_year_request_rejects_invalid_fields(changes):
    with pytest.raises(ValidationError):
        CompareYearsRequest.model_validate(dict(kpi_id="account_ownership", iso3="TUN",
            left_year=2021, right_year=2024) | changes)


@pytest.mark.parametrize("action", ["compare_countries", "compare_years"])
def test_callable_tools_dispatch_reports_and_read_only(agent, warehouse, monkeypatch, action):
    original = duckdb.connect
    calls = []
    def connect(*args, **kwargs):
        assert kwargs == {"read_only":True}
        calls.append(args)
        return original(*args, **kwargs)
    monkeypatch.setattr(duckdb,"connect",connect)
    digest = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    params = ({"left_iso3":"TUN", "right_iso3":"XKX", "year":2024} if action=="compare_countries"
              else {"iso3":"TUN", "left_year":2021, "right_year":2024})
    params["kpi_id"] = "account_ownership"
    tools = {t.name:t for t in agent.get_tools()}
    payload = tools[action].invoke(params)
    report = agent.run({"semantic_kpi_request": {"action":action, **params}})
    assert report["status"] == "success" and report["outputs"]["semantic_kpi_response"] == payload
    assert len(calls) == 4 and hashlib.sha256(warehouse.read_bytes()).hexdigest() == digest
    assert report["outputs"]["warnings"] == payload["review_reasons"]
    with pytest.raises(ValueError, match="Unknown KPI"):
        tools[action].invoke({**params, "kpi_id":"unknown"})
