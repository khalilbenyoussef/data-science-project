"""Standalone agent/tools contract tests; only temporary databases and reports."""
from dataclasses import asdict
import hashlib
import json
import logging

import duckdb
import pytest
from pydantic import ValidationError

from biflow.agents import SemanticKpiAgent
from biflow.agents.base import BaseAgent
from biflow.tools.kpi import KpiCalculator, load_catalog
from biflow.tools.semantic_kpi import (
    CalculateKpiRequest, DescribeKpiRequest, ListKpisRequest,
    REQUEST_ADAPTER, RESPONSE_ADAPTER, SemanticKpiTools,
)
from test_kpi import warehouse, provenance_files  # reusable temporary fixtures


@pytest.fixture
def agent(warehouse, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Semantic KPI requests must never use an LLM")

    monkeypatch.setattr("biflow.agents.base.build_agent_llm", forbidden)
    monkeypatch.setattr(BaseAgent, "ask_text", forbidden)
    monkeypatch.setattr(BaseAgent, "ask_json", forbidden)
    return SemanticKpiAgent(
        cfg={"llm": {"enabled": True}, "paths": {"reports": str(tmp_path / "reports"),
             "quality": str(tmp_path / "quality")}},
        run_id="semantic_test", log=logging.getLogger("semantic_test"), warehouse_path=warehouse,
    )


def test_catalog_discovery_needs_no_warehouse_or_duckdb(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Discovery must not connect to DuckDB")

    monkeypatch.setattr(duckdb, "connect", forbidden)
    tools = SemanticKpiTools(tmp_path / "absent.duckdb")
    response = tools.list_kpis(ListKpisRequest())
    catalog = load_catalog()
    assert response.catalog_version == "1.0.0"
    assert {k.kpi_id for k in response.kpis} == set(catalog["kpis"])
    for summary in response.kpis:
        entry = catalog["kpis"][summary.kpi_id]
        assert summary.unit == entry["unit"]
        assert summary.verification_status == entry["verification"]["status"]
        description = tools.describe_kpi(DescribeKpiRequest(kpi_id=summary.kpi_id))
        assert description.definition == entry
        assert description.policies["publication_review_policy"] == catalog["publication_review_policy"]
        assert description.references == catalog["references"]


def test_descriptions_cannot_mutate_service_catalog(agent):
    request = DescribeKpiRequest(kpi_id="saving_rate")
    description = agent.describe_kpi(request)
    description.definition["verification"]["status"] = "verified"
    assert agent.describe_kpi(request).definition["verification"]["status"] == "provisional"


@pytest.mark.parametrize("kpi_id", list(load_catalog()["kpis"]))
def test_all_six_results_preserved_and_json_roundtrip(agent, warehouse, kpi_id):
    request = CalculateKpiRequest(iso3=" tun ", year=2024, kpi_id=kpi_id)
    expected = KpiCalculator(warehouse, quality_report_path=agent.tools._calculator_args["quality_report_path"]).calculate("TUN", 2024, kpi_id)
    response = agent.calculate_kpi(request)
    assert asdict(response.result) == asdict(expected)
    restored = RESPONSE_ADAPTER.validate_json(response.model_dump_json())
    assert asdict(restored.result) == asdict(expected)
    assert response.result.publication_status == "not_evaluated"
    output = agent.execute({"semantic_kpi_request": request})
    assert output["semantic_kpi_response"] == response.model_dump(mode="json")
    assert output["warnings"] == list(expected.review_reasons)


@pytest.mark.parametrize("input_request", [
    {"action": "calculate", "kpi_id": "account_ownership", "iso3": "TUN", "year": "2024"},
    {"action": "calculate", "kpi_id": "account_ownership", "iso3": "TUN", "year": True},
    {"action": "calculate", "kpi_id": "account_ownership", "iso3": "WLD", "year": 2024},
    {"action": "calculate", "kpi_id": "account_ownership", "iso3": "TUN", "year": 2024, "publication_status": "approved"},
    {"action": "calculate", "kpi_id": "account_ownership", "iso3": "TUN", "year": 2024, "sql": "DROP TABLE fact"},
    {"action": "describe", "kpi_id": 123}, {"action": "unknown"}, {"action": "list", "year": 2024},
])
def test_invalid_typed_requests_rejected_before_queries(agent, monkeypatch, input_request):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid requests must not open DuckDB")

    monkeypatch.setattr(duckdb, "connect", forbidden)
    with pytest.raises(ValidationError):
        agent.execute({"semantic_kpi_request": input_request})


@pytest.mark.parametrize("action", ["calculate", "describe"])
def test_unsupported_kpis_rejected(agent, action):
    request = {"action": action, "kpi_id": "deposits_pct_gdp"}
    if action == "calculate":
        request.update(iso3="TUN", year=2024)
    with pytest.raises(ValueError, match="Unknown KPI"):
        agent.execute({"semantic_kpi_request": request})


@pytest.mark.parametrize("year,reason", [(2021, "missing_observation"), (2023, "out_of_catalog_year")])
def test_unavailable_is_a_successful_response_with_null_value(agent, year, reason):
    output = agent.execute({"semantic_kpi_request": {"action": "calculate", "kpi_id": "unbanked_share", "iso3": "TUN", "year": year}})
    result = output["semantic_kpi_response"]["result"]
    assert result["value"] is None and result["availability_status"] == "unavailable"
    assert result["reason"] == reason and result["observation_year"] == year
    assert result["dependencies"] == ["account_ownership"]


def test_exact_warning_and_lineage_propagation(warehouse, provenance_files):
    _, quality, calculator = provenance_files
    quality["diagnostics"] = [{"source": "findex", "iso3": "TUN", "year": 2024,
                               "indicator_code": "account_t_d", "code": "review_input", "reason": "Review required"}]
    calculator()  # writes temporary sidecars
    agent = SemanticKpiAgent(cfg={}, log=logging.getLogger("semantic_test"), warehouse_path=warehouse,
                             quality_report_path=warehouse.with_name("quality_report.json"))
    result = agent.calculate_kpi(CalculateKpiRequest(iso3="TUN", year=2024, kpi_id="unbanked_share")).result
    assert result.value == 58 and result.requires_review
    assert result.provenance.run_id == "test_run"
    assert len(result.quality_warnings) == 1
    assert result.quality_warnings == result.dependency_results[0].quality_warnings
    assert result.publication_status == "not_evaluated"
    assert result.provenance.quality_association_status == "matches_lineage"


def test_structured_tools_callable_and_strict(agent, warehouse, monkeypatch):
    tools = {tool.name: tool for tool in agent.get_tools()}
    assert set(tools) == {"list_kpis", "describe_kpi", "calculate_kpi", "latest_available",
                          "compare_countries", "compare_years"}
    assert len(tools["list_kpis"].invoke({})["kpis"]) == 6
    assert tools["describe_kpi"].invoke({"kpi_id": "borrowing_rate"})["definition"]["verification"]["status"] == "provisional"
    digest = hashlib.sha256(warehouse.read_bytes()).hexdigest()
    original = duckdb.connect
    calls = []

    def connect(*args, **kwargs):
        assert kwargs == {"read_only": True}
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", connect)
    result = tools["calculate_kpi"].invoke({"iso3": "TUN", "year": 2024, "kpi_id": "saving_rate"})["result"]
    assert result["value"] == pytest.approx(23) and result["verification_status"] == "provisional"
    assert result["publication_status"] == "not_evaluated" and result["requires_review"]
    assert len(calls) == 1 and hashlib.sha256(warehouse.read_bytes()).hexdigest() == digest
    with pytest.raises(ValidationError):
        tools["calculate_kpi"].invoke({"iso3": "TUN", "year": "2024", "kpi_id": "saving_rate"})
    with pytest.raises(ValueError, match="Unknown KPI"):
        tools["calculate_kpi"].invoke({"iso3": "TUN", "year": 2024, "kpi_id": "unknown"})


@pytest.mark.parametrize("input_request", [
    {"action": "list"}, {"action": "describe", "kpi_id": "account_ownership"},
    {"action": "calculate", "kpi_id": "digital_payment_rate", "iso3": "TUN", "year": 2024},
])
def test_base_agent_reports_serializable_typed_outputs(agent, input_request):
    assert isinstance(agent, BaseAgent) and agent.get_llm() is None
    report = agent.run({"semantic_kpi_request": input_request})
    assert report["status"] == "success" and report["llm_usage"] == {}
    response = report["outputs"]["semantic_kpi_response"]
    RESPONSE_ADAPTER.validate_python(response)
    assert json.loads(agent.report_path().read_text())["outputs"] == report["outputs"]


def test_base_agent_failed_requests_preserve_error_reporting(agent):
    report = agent.run({"semantic_kpi_request": {"action": "describe", "kpi_id": "unknown"}})
    assert report["status"] == "failed" and "Unknown KPI" in report["errors"][0]
    assert not report["outputs"]


def test_request_union_schema_and_no_orchestrator_registration():
    schema = REQUEST_ADAPTER.json_schema()
    assert schema["discriminator"]["propertyName"] == "action"
    from biflow.graph import AGENT_CLASSES
    assert set(AGENT_CLASSES) == {"collector", "profiler", "quality", "etl"}
