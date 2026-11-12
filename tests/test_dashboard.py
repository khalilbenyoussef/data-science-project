"""Dashboard contract: copied values, fail-closed validation, atomic export."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from biflow.agents.bi_analyst import build_findings, build_report
from biflow.agents.dashboard import DashboardAgent
from biflow.tools.analysis import AnalysisRequest, AnalysisService
from biflow.tools.dashboard_contract import (
    build_dashboard_data, export_dashboard_json, validate_dashboard_data,
)
from test_kpi import warehouse, provenance_files


@pytest.fixture
def sources(warehouse, provenance_files):
    _, _, write = provenance_files
    write()
    service = AnalysisService(
        warehouse,
        lineage_path=warehouse.with_name("lineage.json"),
        quality_report_path=warehouse.with_name("quality_report.json"),
    )
    request = AnalysisRequest.model_validate({
        "iso3": ["TUN", "XKX"],
        "kpi_ids": ["account_ownership", "saving_rate"],
    })
    dataset = service.build(request)
    analyst = build_report(dataset, build_findings(dataset))
    return dataset, analyst


def test_contract_copies_dataset_values_and_analyst_findings(sources):
    dataset, analyst = sources
    data = build_dashboard_data(dataset, run_id="r1", analyst_report=analyst)
    assert data["schema_version"] == "1.0"
    assert data["run_id"] == "r1"
    assert data["publication_status"] == dataset["publication_status"] == "not_evaluated"
    assert len(data["cards"]) == len(dataset["observations"]) == len(data["table"])
    for card, observation in zip(data["cards"], dataset["observations"]):
        assert card["value"] == observation["value"]
        assert card["availability_status"] == observation["availability_status"]
        assert card["evidence_id"] == observation["evidence_id"]
        assert card["unit"] == observation["unit"]
    assert data["series"] == dataset["series"]
    assert data["rankings"] == dataset["rankings"]
    assert data["comparisons"] == dataset["comparisons"]
    assert data["notices"] == dataset["notices"]
    assert data["summary"] == analyst["summary"]
    assert data["limitations"] == analyst["limitations"]
    assert [item["id"] for item in data["insights"]] == [
        item["id"] for item in analyst["findings"]
    ]

    unavailable = next(card for card in data["cards"] if card["iso3"] == "XKX"
                       and card["kpi_id"] == "saving_rate")
    assert unavailable["value"] is None and unavailable["availability_status"] == "unavailable"


def test_contract_without_analyst_has_no_invented_insights(sources):
    dataset, _ = sources
    data = build_dashboard_data(dataset, run_id="r1")
    assert data["insights"] == [] and data["summary"] is None and data["limitations"] == []


@pytest.mark.parametrize("mutation,match", [
    (lambda data: data.update(schema_version="2.0"), "schema_version"),
    (lambda data: data.pop("cards"), "must be a list: cards"),
    (lambda data: data.update(cards={}), "must be a list: cards"),
    (lambda data: data["cards"][0].update(availability_status="available", value=None),
     "available observation without a numeric value"),
    (lambda data: data["cards"][0].update(availability_status="unavailable", value=0),
     "unavailable observation must keep a null value"),
    (lambda data: data["cards"][0].update(value="37.8"), "must be a number or null"),
    (lambda data: data["cards"][0].update(value=True), "must be a number or null"),
    # S5 : tableaux imbriques verifies valeur par valeur
    (lambda data: data["table"][0].update(value=float("nan")), r"table\[0\]: value must be finite"),
    (lambda data: data["series"][0]["points"][0].update(availability_status="available", value=None),
     r"series\[0\]\.points\[0\]: available observation"),
    (lambda data: data["series"][0]["points"].append({"availability_status": "unavailable", "value": 0.0}),
     "unavailable observation must keep a null value"),
    (lambda data: data["series"][0].pop("points"), "points list"),
    (lambda data: data["rankings"][0]["rows"][0].update(value=float("inf")), "finite or null"),
    (lambda data: data["rankings"][0]["rows"][0].update(rank=1.5), "rank must be an integer"),
    (lambda data: data["comparisons"][0]["rows"][0].update(comparison_status="complete", difference=None),
     "complete comparison without"),
    (lambda data: data["comparisons"][0]["rows"][0].update(comparison_status="unavailable", difference=1.0),
     "incomplete comparison must keep a null difference"),
    (lambda data: data["cards"][0].update(value=float("nan")), "finite or null"),
    (lambda data: data["cards"][0].update(value=float("inf")), "finite or null"),
    (lambda data: data["cards"].append(deepcopy(data["cards"][0])), "duplicate evidence_id"),
    (lambda data: data["cards"].append("card"), "card must be an object"),
])
def test_validation_fails_closed(sources, mutation, match):
    dataset, analyst = sources
    data = build_dashboard_data(dataset, run_id="r1", analyst_report=analyst)
    tampered = deepcopy(data)
    mutation(tampered)
    with pytest.raises(ValueError, match=match):
        validate_dashboard_data(tampered)


def test_export_is_atomic_and_round_trips(sources, tmp_path):
    dataset, analyst = sources
    data = build_dashboard_data(dataset, run_id="r1", analyst_report=analyst)
    path = tmp_path / "public" / "data" / "dashboard.json"
    written = export_dashboard_json(data, path)
    assert written == path and path.is_file()
    assert not path.with_name("dashboard.json.tmp").exists()
    assert json.loads(path.read_text(encoding="utf-8")) == data
    export_dashboard_json(data, path)
    assert json.loads(path.read_text(encoding="utf-8")) == data


def test_export_falls_back_when_target_is_locked(sources, tmp_path, monkeypatch):
    dataset, analyst = sources
    data = build_dashboard_data(dataset, run_id="r1", analyst_report=analyst)
    path = tmp_path / "public" / "dashboard.json"

    def locked(self, target):
        raise PermissionError(5, "locked by a reader", str(self))

    monkeypatch.setattr(Path, "replace", locked)
    written = export_dashboard_json(data, path)
    assert written == path
    assert json.loads(path.read_text(encoding="utf-8")) == data
    assert not path.with_name("dashboard.json.tmp").exists()


def test_agent_exports_reports_and_public_payload(warehouse, provenance_files, tmp_path, monkeypatch):
    _, _, write = provenance_files
    write()

    def forbidden(*args, **kwargs):
        raise AssertionError("Dashboard agent must not instantiate an LLM")

    monkeypatch.setattr("biflow.agents.base.build_agent_llm", forbidden)
    cfg = {
        "paths": {"reports": str(tmp_path / "reports")},
        "dashboard": {"data_output": str(tmp_path / "public" / "dashboard.json")},
    }
    agent = DashboardAgent(
        cfg=cfg, run_id="dash",
        warehouse_path=warehouse,
        lineage_path=warehouse.with_name("lineage.json"),
        quality_report_path=warehouse.with_name("quality_report.json"),
    )
    report = agent.run({"analysis_request": {
        "iso3": ["TUN", "XKX"], "kpi_ids": ["account_ownership", "saving_rate"],
    }})
    assert report["status"] == "success" and not report["errors"]
    assert report["llm_usage"] == {}
    outputs = report["outputs"]
    assert Path(outputs["dashboard_paths"]["data"]).is_file()
    public = Path(outputs["dashboard_paths"]["public"])
    assert public.is_file()
    data = json.loads(public.read_text(encoding="utf-8"))
    assert data["run_id"] == "dash" and data["schema_version"] == "1.0"
    assert json.loads(Path(outputs["dashboard_paths"]["data"]).read_text(
        encoding="utf-8")) == data
    summary = outputs["dashboard_summary"]
    assert summary == {
        "cards": len(data["cards"]),
        "series": len(data["series"]),
        "comparisons": len(data["comparisons"]),
        "insights": 0,
        "notices": len(data["notices"]),
        "publication_status": "not_evaluated",
    }
    assert any(notice["severity"] in {"review", "warning"} for notice in data["notices"])
    assert outputs["warnings"] == [
        notice["message"] for notice in data["notices"]
        if notice["severity"] in {"warning", "review"}
    ]
    saved = json.loads(Path(tmp_path, "reports", "dash", "dashboard.json").read_text(
        encoding="utf-8"))
    assert saved["status"] == "success"
    assert saved["outputs"]["dashboard_paths"] == outputs["dashboard_paths"]


def test_agent_reuses_existing_dataset(warehouse, provenance_files, tmp_path, monkeypatch):
    _, _, write = provenance_files
    write()
    cfg = {
        "paths": {"reports": str(tmp_path / "reports")},
        "dashboard": {"data_output": str(tmp_path / "public" / "dashboard.json")},
    }
    kwargs = {
        "warehouse_path": warehouse,
        "lineage_path": warehouse.with_name("lineage.json"),
        "quality_report_path": warehouse.with_name("quality_report.json"),
    }
    payload = {"iso3": ["TUN"], "kpi_ids": ["account_ownership"]}
    first = DashboardAgent(cfg=cfg, run_id="first", **kwargs).run(
        {"analysis_request": payload})
    path = Path(cfg["paths"]["reports"], "first", "analysis_dataset.json")
    assert first["status"] == "success" and path.is_file()

    monkeypatch.setattr(
        AnalysisService, "build",
        lambda *args, **k: (_ for _ in ()).throw(AssertionError("must not rebuild")),
    )
    second = DashboardAgent(cfg=cfg, run_id="second", **kwargs).run({
        "analysis_request": payload,
        "analysis_dataset_path": str(path),
    })
    assert second["status"] == "success"
    data = json.loads(Path(cfg["dashboard"]["data_output"]).read_text(encoding="utf-8"))
    assert data["run_id"] == "second"


def test_agent_invalid_request_fails_without_export(tmp_path):
    cfg = {
        "paths": {"reports": str(tmp_path / "reports")},
        "dashboard": {"data_output": str(tmp_path / "public" / "dashboard.json")},
    }
    report = DashboardAgent(cfg=cfg, run_id="bad").run(
        {"analysis_request": {"iso3": ["TUN"], "kpi_ids": ["unknown"]}})
    assert report["status"] == "failed" and report["errors"]
    assert report["outputs"] == {}
    assert not Path(cfg["dashboard"]["data_output"]).exists()
