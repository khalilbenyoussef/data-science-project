"""Finova Route 2 orchestration: Semantic/KPI dataset -> Analyst || Dashboard.

Route 1 is untouched. ``prepare`` builds the analysis dataset and exports the
canonical facts once; ``analyst`` and ``dashboard`` then run in parallel (both
read-only, both deterministic); ``finalize`` merges the checked insights and
XAI card into the validated contract, then writes the public spec and history.
Without LangGraph the same steps run sequentially with identical outputs.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from biflow import graph as pipeline_graph
from biflow.agents.analyst import FinovaAnalystAgent
from biflow.agents.dashboard import DashboardSpecAgent
from biflow.config import load_config, path_of, resolve
from biflow.state import PipelineState, new_state
from biflow.tools.analysis import AnalysisRequest, AnalysisService
from biflow.tools.dashboard_spec import (
    DashboardSpec, PEERS, PRIMARY_COUNTRY, REFERENCE_PATH, build_finova_spec,
    load_reference, snapshot_from_spec,
)
from biflow.tools.kpi import DEFAULT_CATALOG
from biflow.tools.warehouse_reader import WarehouseReader
from biflow.utils.io import load_json, save_json


def _default_request(cfg: Mapping[str, Any]) -> dict[str, Any]:
    dashboard = cfg.get("dashboard") or {}
    primary = str(dashboard.get("default_country", PRIMARY_COUNTRY))
    year = int(dashboard.get("default_year", 2024))
    return {
        "iso3": [primary, *(code for code in PEERS if code != primary)],
        "mode": "year",
        "year": year,
    }


def _spec_file(state: Mapping[str, Any]) -> Path:
    path = state.get("finova_spec_path")
    if not path:
        raise RuntimeError("dashboard spec missing: the dashboard node did not run")
    return Path(path)


def _attach_analysis(
    spec_path: str | Path, insights: Mapping[str, Any] | None,
    xai: Mapping[str, Any] | None,
) -> DashboardSpec:
    data = load_json(spec_path)
    if not isinstance(data, dict):
        raise RuntimeError("invalid dashboard spec payload")
    insights = insights or {}
    for page in data.get("pages") or []:
        page["insights"] = [dict(item) for item in insights.get(page.get("id"), [])]
        if page.get("id") == "exclusion":
            if xai is not None:
                page["xai"] = dict(xai)
            else:
                page.pop("xai", None)
    return DashboardSpec.model_validate(data)


def run_route2(
    request: AnalysisRequest | Mapping[str, Any] | None = None,
    cfg: dict[str, Any] | None = None,
    run_id: str | None = None,
    objective: str | None = None,
    *,
    warehouse_path: str | Path | None = None,
    lineage_path: str | Path | None = None,
    quality_report_path: str | Path | None = None,
    catalog_path: str | Path = DEFAULT_CATALOG,
    use_llm: bool = False,
) -> PipelineState:
    """Run the Finova Route 2 graph and return the final state.

    Invalid requests fail before any agent runs. The graph never calls an LLM
    unless ``use_llm`` is true (optional checked narration) and never writes
    outside the reports, public data and history folders.
    """
    cfg = deepcopy(cfg if cfg is not None else load_config())
    cfg.setdefault("llm", {})["enabled"] = bool(use_llm)
    run_id = run_id or datetime.now().strftime("route2_%Y%m%dT%H%M%S%f")
    paths = cfg.get("paths") or {}
    warehouse = resolve(
        warehouse_path if warehouse_path is not None
        else Path(paths.get("processed", "data/processed")) / "warehouse.duckdb"
    )
    lineage = resolve(
        lineage_path if lineage_path is not None
        else warehouse.with_name("lineage.json")
    )
    quality = resolve(
        quality_report_path if quality_report_path is not None
        else Path(paths.get("quality", "data/quality")) / "quality_report.json"
    )
    reference_path = resolve(
        (cfg.get("dashboard") or {}).get("reference_path", REFERENCE_PATH)
    )
    public_path = resolve(
        (cfg.get("dashboard") or {}).get(
            "spec_output", "dashboard_app/public/data/finova.json")
    )
    history_dir = resolve(
        (cfg.get("dashboard") or {}).get("history_dir", "outputs/dashboard/history")
    )
    history_dir.mkdir(parents=True, exist_ok=True)

    state = new_state(objective or "Dashboard Finova déterministe", run_id)
    state["warehouse_path"] = str(warehouse)
    state["lineage_path"] = str(lineage)
    state["quality_paths"] = {"json": str(quality)}
    reports_dir = path_of(cfg, "reports") / run_id
    reports_dir.mkdir(parents=True, exist_ok=True)

    raw_request = request if request is not None else _default_request(cfg)
    try:
        validated = AnalysisRequest.model_validate(raw_request)
    except Exception as exc:  # noqa: BLE001 - invalid scope fails before any agent
        state["status"] = "failed"
        state["errors"] = [f"{type(exc).__name__}: {exc}"]
        summary = pipeline_graph._summary(state)
        summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
        save_json(summary, reports_dir / "run.json")
        return state
    state["analysis_request"] = validated.model_dump(mode="json")

    agent_kwargs = {
        "warehouse_path": str(warehouse),
        "catalog_path": catalog_path,
        "lineage_path": str(lineage),
        "quality_report_path": str(quality),
    }

    def prepare(current: Mapping[str, Any]) -> dict[str, Any]:
        validated = AnalysisRequest.model_validate(
            current.get("analysis_request") or _default_request(cfg)
        )
        dataset = AnalysisService(
            warehouse, catalog_path, lineage_path=lineage,
            quality_report_path=quality,
        ).build(validated)
        save_json(dataset, reports_dir / "analysis_dataset.json")
        reader = WarehouseReader(warehouse) if warehouse.is_file() else None
        spec = build_finova_spec(
            dataset, run_id=run_id, reader=reader,
            reference=load_reference(reference_path),
        )
        facts = [fact.model_dump(mode="json") for fact in spec.facts]
        save_json(facts, reports_dir / "facts.json")
        return {
            "analysis_request": validated.model_dump(mode="json"),
            "analysis_dataset_path": str(reports_dir / "analysis_dataset.json"),
            "facts": facts,
            "facts_path": str(reports_dir / "facts.json"),
            "country_name": spec.country.name,
        }

    def finalize(current: Mapping[str, Any]) -> dict[str, Any]:
        spec = _attach_analysis(
            _spec_file(current), current.get("insights"), current.get("xai"),
        )
        payload = spec.model_dump(mode="json")
        save_json(payload, reports_dir / "finova_spec.json")
        save_json(payload, public_path)
        history_path = save_json(
            snapshot_from_spec(spec), history_dir / f"{run_id}.json"
        )
        return {
            "finova_spec_path": str(reports_dir / "finova_spec.json"),
            "dashboard_public_path": str(public_path),
            "dashboard_history_path": str(history_path),
            "dashboard_spec_summary": {
                "schema_version": spec.schema_version,
                "pages": len(spec.pages),
                "facts": len(spec.facts),
                "notices": len(spec.notices),
                "year": spec.year,
                "country": spec.country.iso3,
                "publication_status": spec.publication_status,
            },
            "route2_summary": {
                "request": current.get("analysis_request"),
                "analyst": current.get("analyst_summary"),
                "dashboard": current.get("dashboard_spec_summary"),
                "spec_path": str(reports_dir / "finova_spec.json"),
                "public_path": str(public_path),
                "facts": len(spec.facts),
                "insights": sum(len(page.insights) for page in spec.pages),
                "xai": spec.page("exclusion").xai is not None,
                "publication_status": spec.publication_status,
            },
        }

    analyst_agent = FinovaAnalystAgent(cfg=cfg, run_id=run_id)
    dashboard_agent = DashboardSpecAgent(cfg=cfg, run_id=run_id, **agent_kwargs)

    try:
        if pipeline_graph.LANGGRAPH_AVAILABLE:
            graph = pipeline_graph.StateGraph(PipelineState)
            graph.add_node("prepare", prepare)
            graph.add_node("analyst", pipeline_graph._node(analyst_agent))
            graph.add_node("dashboard", pipeline_graph._node(dashboard_agent))
            graph.add_node("finalize", finalize)
            graph.add_edge(pipeline_graph.START, "prepare")
            graph.add_edge("prepare", "analyst")
            graph.add_edge("prepare", "dashboard")
            graph.add_edge("analyst", "finalize")
            graph.add_edge("dashboard", "finalize")
            graph.add_edge("finalize", pipeline_graph.END)
            state = graph.compile().invoke(state, config={"recursion_limit": 20})
        else:
            pipeline_graph._merge_updates(state, prepare(state))
            for agent in (analyst_agent, dashboard_agent):
                report = agent.run(state)
                if report["status"] != "success":
                    detail = "; ".join(report.get("errors") or ["erreur inconnue"])
                    raise RuntimeError(f"[{agent.name}] {detail}")
                pipeline_graph._merge_updates(state, report.get("outputs") or {})
            pipeline_graph._merge_updates(state, finalize(state))
        state["status"] = "success"
    except Exception as exc:  # noqa: BLE001 - the run report must capture the failure
        state["status"] = "failed"
        state["errors"] = list(state.get("errors") or []) + [
            f"{type(exc).__name__}: {exc}"
        ]

    summary = pipeline_graph._summary(state)
    summary.update({
        "analysis_request": state.get("analysis_request"),
        "route2_summary": state.get("route2_summary"),
        "dashboard_spec_summary": state.get("dashboard_spec_summary"),
        "analyst_summary": state.get("analyst_summary"),
        "facts_path": state.get("facts_path"),
        "finished_at": datetime.now().isoformat(timespec="seconds"),
    })
    save_json(summary, reports_dir / "run.json")
    return state


__all__ = ["run_route2"]
