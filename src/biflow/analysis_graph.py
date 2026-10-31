"""Opt-in Route 2 orchestration: BI Semantic/KPI -> BI Analyst -> Dashboard.

Route 1 (Collector -> Profiler -> Quality -> ETL) is untouched: this module has
its own graph and never imports or invokes the data-processing agents. All KPI
access is read-only and every agent is deterministic (no LLM).
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from biflow import graph as pipeline_graph
from biflow.agents.bi_analyst import BiAnalystAgent
from biflow.agents.dashboard import DashboardAgent
from biflow.config import load_config, resolve
from biflow.state import PipelineState, new_state
from biflow.tools.analysis import AnalysisRequest
from biflow.tools.kpi import DEFAULT_CATALOG
from biflow.utils.io import save_json

STAGES: dict[str, tuple[str, ...]] = {
    "analyst": ("bi_analyst",),
    "dashboard": ("dashboard",),
    "all": ("bi_analyst", "dashboard"),
}
AGENTS = {"bi_analyst": BiAnalystAgent, "dashboard": DashboardAgent}


def run_analysis_pipeline(
    request: AnalysisRequest | Mapping[str, Any],
    cfg: dict[str, Any] | None = None,
    run_id: str | None = None,
    objective: str | None = None,
    *,
    stage: str = "all",
    warehouse_path: str | Path | None = None,
    lineage_path: str | Path | None = None,
    quality_report_path: str | Path | None = None,
    catalog_path: str | Path = DEFAULT_CATALOG,
) -> PipelineState:
    """Validate one analysis request and run the selected Route 2 agents.

    Invalid requests fail before any agent runs. Runtime failures never fall
    back to Route 1, never retry and never call an LLM. Availability/review
    statuses from the semantic layer are preserved unchanged.
    """
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage} (choices: {', '.join(STAGES)})")

    cfg = deepcopy(cfg if cfg is not None else load_config())
    cfg.setdefault("llm", {})["enabled"] = False
    run_id = run_id or datetime.now().strftime("analysis_%Y%m%dT%H%M%S%f")
    state = new_state(objective or "Analyse BI déterministe", run_id)
    paths = cfg.get("paths") or {}
    state["warehouse_path"] = str(resolve(
        warehouse_path if warehouse_path is not None
        else Path(paths.get("processed", "data/processed")) / "warehouse.duckdb"
    ))
    state["lineage_path"] = str(resolve(
        lineage_path if lineage_path is not None
        else Path(state["warehouse_path"]).with_name("lineage.json")
    ))
    state["quality_paths"] = {"json": str(resolve(
        quality_report_path if quality_report_path is not None
        else Path(paths.get("quality", "data/quality")) / "quality_report.json"
    ))}

    steps = STAGES[stage]
    agent_kwargs = {
        "warehouse_path": state["warehouse_path"],
        "catalog_path": catalog_path,
        "lineage_path": state["lineage_path"],
        "quality_report_path": state["quality_paths"]["json"],
    }

    try:
        validated = AnalysisRequest.model_validate(request)
        state["analysis_request"] = validated.model_dump(mode="json")
        if pipeline_graph.LANGGRAPH_AVAILABLE:
            graph = pipeline_graph.StateGraph(PipelineState)
            for step in steps:
                graph.add_node(
                    step,
                    pipeline_graph._node(
                        AGENTS[step](cfg=cfg, run_id=run_id, **agent_kwargs)
                    ),
                )
            graph.add_edge(pipeline_graph.START, steps[0])
            for current, following in zip(steps, steps[1:]):
                graph.add_edge(current, following)
            graph.add_edge(steps[-1], pipeline_graph.END)
            state = graph.compile().invoke(state, config={"recursion_limit": 10})
        else:
            for step in steps:
                report = AGENTS[step](cfg=cfg, run_id=run_id, **agent_kwargs).run(state)
                if report["status"] != "success":
                    detail = "; ".join(report.get("errors") or ["erreur inconnue"])
                    raise RuntimeError(f"[{step}] {detail}")
                pipeline_graph._merge_updates(state, report.get("outputs") or {})
        state["status"] = "success"
    except Exception as exc:
        state["status"] = "failed"
        state["errors"] = list(state.get("errors") or []) + [
            f"{type(exc).__name__}: {exc}"
        ]

    summary = pipeline_graph._summary(state)
    report = state.get("analysis_report") or {}
    summary.update({
        "analysis_request": state.get("analysis_request"),
        "analysis_summary": report.get("summary"),
        "analysis_findings": report.get("findings"),
        "analysis_dataset_path": state.get("analysis_dataset_path"),
        "dashboard_paths": state.get("dashboard_paths"),
        "dashboard_summary": state.get("dashboard_summary"),
        "stage": stage,
    })
    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    save_json(summary, Path(paths.get("reports", "outputs/reports")) / run_id / "run.json")
    return state


__all__ = ["AGENTS", "STAGES", "run_analysis_pipeline"]
