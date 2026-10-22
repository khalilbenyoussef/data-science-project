"""Graphe LangGraph du pipeline BIFlow (S6 -> S9)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Callable

try:  # l'import LangGraph peut echouer si une DLL est bloquee par une policy Windows
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:  # noqa: BLE001
    END = START = StateGraph = None  # type: ignore[assignment]
    LANGGRAPH_AVAILABLE = False

from biflow.agents import (
    AgentError,
    CollectorAgent,
    EtlAgent,
    ProfilerAgent,
    QualityAgent,
)
from biflow.config import load_config
from biflow.state import PipelineState, new_state
from biflow.utils.io import save_json
from biflow.utils.logger import get_logger

log = get_logger("biflow.graph")

AGENT_CLASSES = {
    "collector": CollectorAgent,
    "profiler": ProfilerAgent,
    "quality": QualityAgent,
    "etl": EtlAgent,
}
STEP_ORDER = list(AGENT_CLASSES)


def _node(agent) -> Callable[[PipelineState], dict[str, Any]]:
    def run(state: PipelineState) -> dict[str, Any]:
        report = agent.run(state)
        if report["status"] != "success":
            detail = "; ".join(report.get("errors") or ["erreur inconnue"])
            raise AgentError(f"[{agent.name}] {detail}")
        return report.get("outputs") or {}

    return run


def _gate(state: PipelineState) -> str:
    quality = state.get("quality") or {}
    return "etl" if quality.get("passed") else END


def build_graph(
    cfg: dict[str, Any],
    run_id: str,
    steps: list[str] | None = None,
):
    if not LANGGRAPH_AVAILABLE:
        raise AgentError(
            "LangGraph indisponible dans cet environnement (DLL bloquee) : "
            "utiliser l'execution sequentielle"
        )
    steps = steps or STEP_ORDER
    graph = StateGraph(PipelineState)
    for step in steps:
        graph.add_node(step, _node(AGENT_CLASSES[step](cfg=cfg, run_id=run_id)))

    graph.add_edge(START, steps[0])
    for current, following in zip(steps, steps[1:]):
        if current == "quality" and following == "etl":
            graph.add_conditional_edges(current, _gate, {"etl": "etl", END: END})
        else:
            graph.add_edge(current, following)
    graph.add_edge(steps[-1], END)
    return graph.compile()


def _merge_updates(state: PipelineState, updates: dict[str, Any]) -> None:
    """Fusionne les sorties d'un agent (listes warnings/errors en accumulation)."""
    updates = dict(updates or {})
    warnings = updates.pop("warnings", None)
    errors = updates.pop("errors", None)
    state.update(updates)
    if warnings:
        state["warnings"] = list(state.get("warnings") or []) + list(warnings)
    if errors:
        state["errors"] = list(state.get("errors") or []) + list(errors)


def run_steps(
    steps: list[str],
    cfg: dict[str, Any],
    run_id: str,
    state: PipelineState,
) -> PipelineState:
    """Execution sequentielle (fallback sans LangGraph)."""
    for step in steps:
        agent = AGENT_CLASSES[step](cfg=cfg, run_id=run_id)
        report = agent.run(state)
        if report["status"] != "success":
            detail = "; ".join(report.get("errors") or ["erreur inconnue"])
            raise AgentError(f"[{step}] {detail}")
        _merge_updates(state, report.get("outputs") or {})
        if step == "quality" and not (state.get("quality") or {}).get("passed"):
            state["status"] = "quality_failed"
            log.warning("quality gate FAIL : arret avant l'ETL")
            return state
    return state


def _summary(state: PipelineState) -> dict[str, Any]:
    quality = state.get("quality") or {}
    profiles = state.get("profiles") or {}
    return {
        "run_id": state.get("run_id"),
        "status": state.get("status"),
        "raw_paths": state.get("raw_paths"),
        "profiles": {
            name: {
                "rows": info.get("rows"),
                "cols": info.get("cols"),
                "format": info.get("format"),
                "missing_cells_pct": info.get("missing_cells_pct"),
                "path": info.get("path"),
            }
            for name, info in profiles.items()
        },
        "quality": {
            "score": quality.get("overall_score"),
            "passed": quality.get("passed"),
            "critical_issues": quality.get("critical_issues"),
            "paths": state.get("quality_paths"),
        },
        "warehouse": state.get("warehouse_path"),
        "staging_paths": state.get("staging_paths"),
        "llm_notes": state.get("llm_notes"),
        "warnings": state.get("warnings"),
        "errors": state.get("errors"),
    }


def run_pipeline(
    objective: str | None = None,
    only: str | None = None,
    start: str | None = None,
    stop: str | None = None,
    cfg: dict[str, Any] | None = None,
    run_id: str | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    cfg = deepcopy(cfg or load_config())
    if not use_llm:
        cfg.setdefault("llm", {})["enabled"] = False
    objective = objective or (cfg.get("project") or {}).get("objective", "Pipeline BI BIFlow")
    run_id = run_id or datetime.now().strftime("%Y%m%dT%H%M%S")
    state = new_state(objective=objective, run_id=run_id)
    state["sources"] = cfg.get("sources") or {}

    if only:
        if only not in AGENT_CLASSES:
            raise ValueError(f"agent inconnu : {only} (choix : {', '.join(STEP_ORDER)})")
        agent = AGENT_CLASSES[only](cfg=cfg, run_id=run_id)
        report = agent.run(state)
        _merge_updates(state, report.get("outputs") or {})
        state["status"] = "success" if report["status"] == "success" else "failed"
        if report["status"] != "success":
            state["errors"] = list(state.get("errors") or []) + list(report.get("errors") or [])
    else:
        start_index = STEP_ORDER.index(start) if start else 0
        stop_index = STEP_ORDER.index(stop) if stop else len(STEP_ORDER) - 1
        if start_index > stop_index:
            raise ValueError("--from doit preceder --to")
        steps = STEP_ORDER[start_index : stop_index + 1]
        try:
            if LANGGRAPH_AVAILABLE:
                state = build_graph(cfg, run_id, steps).invoke(
                    state, config={"recursion_limit": 30}
                )
            else:
                log.warning("LangGraph indisponible : execution sequentielle des agents")
                state = run_steps(steps, cfg, run_id, state)
            quality = state.get("quality") or {}
            if "quality" in steps and not quality.get("passed"):
                state["status"] = "quality_failed"
            else:
                state["status"] = "success"
        except AgentError as exc:
            state["status"] = "failed"
            state["errors"] = list(state.get("errors") or []) + [str(exc)]

    summary = _summary(state)
    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    reports_dir = f"{(cfg.get('paths') or {}).get('reports', 'outputs/reports')}/{run_id}"
    save_json(summary, f"{reports_dir}/run.json")
    return state


__all__ = ["AGENT_CLASSES", "STEP_ORDER", "build_graph", "run_pipeline"]
