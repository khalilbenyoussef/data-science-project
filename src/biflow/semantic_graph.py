"""Opt-in semantic orchestration. Never runs data-processing agents or an LLM."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from biflow import graph as pipeline_graph
from biflow.agents.semantic_kpi import SemanticKpiAgent
from biflow.config import load_config, resolve
from biflow.state import PipelineState, new_state
from biflow.tools.kpi import DEFAULT_CATALOG
from biflow.tools.semantic_kpi import REQUEST_ADAPTER, RESPONSE_ADAPTER, SemanticKpiRequest
from biflow.utils.io import save_json


def run_semantic_request(
    request: SemanticKpiRequest | Mapping[str, Any],
    cfg: dict[str, Any] | None = None,
    run_id: str | None = None,
    objective: str | None = None,
    *,
    warehouse_path: str | Path | None = None,
    lineage_path: str | Path | None = None,
    quality_report_path: str | Path | None = None,
    catalog_path: str | Path = DEFAULT_CATALOG,
) -> PipelineState:
    """Validate and route one request through one SemanticKpiAgent.run call.

    Invalid request envelopes fail before agent execution. Accepted requests run
    once on either backend; runtime failures never trigger retries or pipelines.
    Writes standard agent/run reports only. Data and provenance inputs are read.
    Availability/review statuses are preserved independently of execution status.
    """
    cfg = deepcopy(cfg if cfg is not None else load_config())
    cfg.setdefault("llm", {})["enabled"] = False
    run_id = run_id or datetime.now().strftime("semantic_%Y%m%dT%H%M%S%f")
    state = new_state(objective or "Semantic KPI request", run_id)
    paths = cfg.get("paths") or {}

    def invoke(current: PipelineState) -> dict[str, Any]:
        agent = SemanticKpiAgent(
            cfg=cfg, run_id=run_id, warehouse_path=current["warehouse_path"],
            lineage_path=current["lineage_path"],
            quality_report_path=current["quality_paths"]["json"], catalog_path=catalog_path,
        )
        report = agent.run(current)
        if report["status"] != "success":
            return {"status": "failed", "errors": report.get("errors") or ["Semantic agent failed"],
                    "warnings": report.get("warnings") or []}
        outputs = report.get("outputs") or {}
        response = RESPONSE_ADAPTER.validate_python(outputs.get("semantic_kpi_response"))
        if response.action != current["semantic_kpi_request"]["action"]:
            raise ValueError("Semantic response action does not match the request")
        return {"status": "success", "semantic_kpi_response": response.model_dump(mode="json"),
                "warnings": list(outputs.get("warnings") or [])}

    try:
        validated = REQUEST_ADAPTER.validate_python(request)
        state["semantic_kpi_request"] = validated.model_dump(mode="json")
        state["warehouse_path"] = str(resolve(warehouse_path if warehouse_path is not None
            else Path(paths.get("processed", "data/processed")) / "warehouse.duckdb"))
        state["lineage_path"] = str(resolve(lineage_path if lineage_path is not None
            else Path(state["warehouse_path"]).with_name("lineage.json")))
        state["quality_paths"] = {"json": str(resolve(quality_report_path if quality_report_path is not None
            else Path(paths.get("quality", "data/quality")) / "quality_report.json"))}
        if pipeline_graph.LANGGRAPH_AVAILABLE:
            graph = pipeline_graph.StateGraph(PipelineState)
            graph.add_node("semantic_kpi", invoke)
            graph.add_edge(pipeline_graph.START, "semantic_kpi")
            graph.add_edge("semantic_kpi", pipeline_graph.END)
            state = graph.compile().invoke(state, config={"recursion_limit": 5})
        else:
            pipeline_graph._merge_updates(state, invoke(state))
    except Exception as exc:
        state["status"] = "failed"
        state["errors"] = list(state.get("errors") or []) + [f"{type(exc).__name__}: {exc}"]

    summary = pipeline_graph._summary(state)
    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    save_json(summary, Path(paths.get("reports", "outputs/reports")) / run_id / "run.json")
    return state


__all__ = ["run_semantic_request"]
