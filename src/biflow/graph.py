"""Graphe LangGraph du pipeline BIFlow (S6 -> S12)."""

from __future__ import annotations

import time
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
    AuditorAgent,
    CollectorAgent,
    EtlAgent,
    ProfilerAgent,
    QualityAgent,
    SemanticKpiAgent,
    SnapshotAgent,
)
from biflow.config import load_config
from biflow.state import PipelineState, new_state
from biflow.tools.snapshots import SnapshotStore
from biflow.utils.io import save_json
from biflow.utils.logger import get_logger

log = get_logger("biflow.graph")

AGENT_CLASSES = {
    "collector": CollectorAgent,
    "snapshot": SnapshotAgent,          # versionne data/raw ; "no_change" -> fin du run
    "profiler": ProfilerAgent,
    "quality": QualityAgent,
    "etl": EtlAgent,
    "semantic_kpi": SemanticKpiAgent,   # mode pipeline : table kpi_values
    "auditor": AuditorAgent,            # verification independante, verdict d'audit
}
STEP_ORDER = list(AGENT_CLASSES)


class StepFailedError(AgentError):
    """Echec d'une etape apres toutes ses tentatives (chaque tentative conservee)."""

    def __init__(self, step: str, failures: list[str]) -> None:
        super().__init__("; ".join(failures))
        self.step = step
        self.failures = failures


def _retry_settings(cfg: dict[str, Any]) -> tuple[int, float]:
    orchestrator = cfg.get("orchestrator") or {}
    retries = max(0, int(orchestrator.get("max_retries", 1)))
    backoff = max(0.0, float(orchestrator.get("retry_backoff_s", 1.0)))
    return retries, backoff


def _run_with_retry(
    step: str,
    agent,
    state: PipelineState,
    cfg: dict[str, Any],
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Execute un agent ; une erreur est retentee (orchestrator.max_retries).

    Un quality gate FAIL n'est pas une erreur (statut success, passed=false) :
    il n'est jamais retente. Apres le dernier echec, StepFailedError arrete le
    pipeline sans toucher aux sorties deja publiees.
    """
    max_retries, backoff = _retry_settings(cfg)
    total = max_retries + 1
    failures: list[str] = []
    for attempt in range(1, total + 1):
        report = agent.run(state)
        attempts.append({
            "step": step,
            "attempt": attempt,
            "status": report.get("status"),
            "started_at": report.get("started_at"),
            "duration_s": report.get("duration_s"),
            "errors": list(report.get("errors") or []),
        })
        if report.get("status") == "success":
            outputs = dict(report.get("outputs") or {})
            if failures:
                outputs["warnings"] = list(outputs.get("warnings") or []) + [
                    f"[{step}] reussi a la tentative {attempt}/{total} apres : {failure}"
                    for failure in failures
                ]
            return outputs
        detail = "; ".join(report.get("errors") or ["erreur inconnue"])
        failures.append(f"[{step}] tentative {attempt}/{total} : {detail}")
        if attempt < total:
            delay = backoff * attempt
            log.warning("[%s] echec tentative %d/%d, nouvel essai dans %.1f s : %s",
                        step, attempt, total, delay, detail)
            time.sleep(delay)
    log.error("[%s] echec apres %d tentative(s) : arret du pipeline", step, total)
    raise StepFailedError(step, failures)


def _node(
    agent,
    cfg: dict[str, Any] | None = None,
    attempts: list[dict[str, Any]] | None = None,
) -> Callable[[PipelineState], dict[str, Any]]:
    cfg = cfg or {}
    attempts = attempts if attempts is not None else []

    def run(state: PipelineState) -> dict[str, Any]:
        return _run_with_retry(agent.name, agent, state, cfg, attempts)

    return run


def _gate(state: PipelineState) -> str:
    quality = state.get("quality") or {}
    return "etl" if quality.get("passed") else END


def _no_change(state: PipelineState) -> bool:
    return (state.get("snapshot") or {}).get("status") == "no_change"


def _snapshot_gate(following: str) -> Callable[[PipelineState], str]:
    """Aucune donnee nouvelle : les etapes suivantes (ETL, KPI) sont ignorees."""
    def route(state: PipelineState) -> str:
        return END if _no_change(state) else following

    return route


def build_graph(
    cfg: dict[str, Any],
    run_id: str,
    steps: list[str] | None = None,
    attempts: list[dict[str, Any]] | None = None,
):
    if not LANGGRAPH_AVAILABLE:
        raise AgentError(
            "LangGraph indisponible dans cet environnement (DLL bloquee) : "
            "utiliser l'execution sequentielle"
        )
    steps = steps or STEP_ORDER
    graph = StateGraph(PipelineState)
    for step in steps:
        graph.add_node(step, _node(AGENT_CLASSES[step](cfg=cfg, run_id=run_id), cfg, attempts))

    graph.add_edge(START, steps[0])
    for current, following in zip(steps, steps[1:]):
        if current == "quality" and following == "etl":
            graph.add_conditional_edges(current, _gate, {"etl": "etl", END: END})
        elif current == "snapshot":
            graph.add_conditional_edges(
                current, _snapshot_gate(following), {following: following, END: END}
            )
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
    attempts: list[dict[str, Any]] | None = None,
) -> PipelineState:
    """Execution sequentielle (fallback sans LangGraph), meme politique de retry."""
    attempts = attempts if attempts is not None else []
    for step in steps:
        agent = AGENT_CLASSES[step](cfg=cfg, run_id=run_id)
        _merge_updates(state, _run_with_retry(step, agent, state, cfg, attempts))
        if step == "snapshot" and _no_change(state):
            log.info("aucune donnee nouvelle : arret apres le snapshot")
            return state
        if step == "quality" and not (state.get("quality") or {}).get("passed"):
            state["status"] = "quality_failed"
            log.warning("quality gate FAIL : arret avant l'ETL")
            return state
    return state


def _summary(state: PipelineState) -> dict[str, Any]:
    quality = state.get("quality") or {}
    profiles = state.get("profiles") or {}
    summary = {
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
        "snapshot": state.get("snapshot"),
        "audit": {key: (state.get("audit") or {}).get(key)
                  for key in ("verdict", "counts", "publication")} if state.get("audit") else None,
        "warehouse": state.get("warehouse_path"),
        "staging_paths": state.get("staging_paths"),
        "kpi": {"summary": state.get("kpi_summary"), "paths": state.get("kpi_paths")},
        "llm_notes": state.get("llm_notes"),
        "warnings": state.get("warnings"),
        "errors": state.get("errors"),
    }
    if "attempts" in state:
        summary["attempts"] = state["attempts"]
    if "semantic_kpi_request" in state:
        summary["semantic_kpi_request"] = state["semantic_kpi_request"]
        summary["semantic_kpi_response"] = state.get("semantic_kpi_response")
        summary["lineage_path"] = state.get("lineage_path")
    return summary


def _finalize_snapshot(cfg: dict[str, Any], state: PipelineState, steps: list[str]) -> None:
    """Apres l'Auditor : un nouveau snapshot n'est publie que si l'audit a 0 echec ;
    sinon not_published et la version publiee precedente reste en place.
    Chaque audit est consigne dans l'entree de l'index (audits)."""
    snapshot = state.get("snapshot") or {}
    if snapshot.get("status") not in ("new", "rebuild"):
        return
    audit = state.get("audit") or {}
    passed = audit.get("verdict") in ("pass", "pass_with_warnings")
    publish = state.get("status") == "success" and "auditor" in steps and passed
    reason = None if publish else (
        "partial_run" if state.get("status") == "success" else state.get("status")
    )
    store = SnapshotStore((cfg.get("snapshots") or {}).get("root", "data/snapshots"))
    try:
        if audit.get("verdict"):
            entry = store.record_audit(snapshot["snapshot_id"], state.get("run_id"), audit["verdict"])
        if snapshot["status"] == "rebuild":
            if not audit.get("verdict"):
                return
            state["snapshot"] = {**snapshot, "status": entry["status"], "audit": audit["verdict"]}
            return
        entry = store.finalize(snapshot["snapshot_id"], publish, reason)
    except (OSError, KeyError, ValueError) as exc:
        state["status"] = "failed"
        state["errors"] = list(state.get("errors") or []) + [f"[snapshot] finalisation : {exc}"]
        return
    state["snapshot"] = {**snapshot, "status": entry["status"], "reason": entry.get("reason")}
    if publish:
        log.info("snapshot %s publie", snapshot["snapshot_id"])
    else:
        log.warning("snapshot %s non publie (%s) : version precedente conservee",
                    snapshot["snapshot_id"], reason)


_NO_SEMANTIC_REQUEST = object()


def run_pipeline(
    objective: str | None = None,
    only: str | None = None,
    start: str | None = None,
    stop: str | None = None,
    cfg: dict[str, Any] | None = None,
    run_id: str | None = None,
    use_llm: bool = True,
    *,
    semantic_kpi_request: Any = _NO_SEMANTIC_REQUEST,
    rebuild: bool = False,
) -> dict[str, Any]:
    if semantic_kpi_request is not _NO_SEMANTIC_REQUEST:
        if any(selection is not None for selection in (only, start, stop)):
            raise ValueError("semantic_kpi_request cannot be combined with only, start or stop")
        from biflow.semantic_graph import run_semantic_request

        return run_semantic_request(semantic_kpi_request, cfg=cfg, run_id=run_id, objective=objective)
    cfg = deepcopy(cfg or load_config())
    if not use_llm:
        cfg.setdefault("llm", {})["enabled"] = False
    objective = objective or (cfg.get("project") or {}).get("objective", "Pipeline BI BIFlow")
    run_id = run_id or datetime.now().strftime("%Y%m%dT%H%M%S")
    state = new_state(objective=objective, run_id=run_id)
    state["sources"] = cfg.get("sources") or {}
    attempts: list[dict[str, Any]] = []
    if rebuild:
        # Rejoue snapshot -> auditor sur les blobs du snapshot publie (sans collecte)
        if only or start:
            raise ValueError("--rebuild ne se combine pas avec --only ou --from")
        state["rebuild"] = True
        start = "snapshot"

    if only:
        if only not in AGENT_CLASSES:
            raise ValueError(f"agent inconnu : {only} (choix : {', '.join(STEP_ORDER)})")
        steps = [only]
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
        last_good: PipelineState = state
        try:
            if LANGGRAPH_AVAILABLE:
                # stream "values" : dernier etat complet apres chaque etape reussie
                for snapshot in build_graph(cfg, run_id, steps, attempts).stream(
                    state, config={"recursion_limit": 30}, stream_mode="values"
                ):
                    last_good = snapshot
                state = last_good
            else:
                log.warning("LangGraph indisponible : execution sequentielle des agents")
                state = run_steps(steps, cfg, run_id, state, attempts)
            quality = state.get("quality") or {}
            if _no_change(state):
                state["status"] = "no_change"
            elif "quality" in steps and not quality.get("passed"):
                state["status"] = "quality_failed"
            elif (state.get("audit") or {}).get("verdict") == "fail":
                state["status"] = "audit_failed"  # decision de l'Auditor, jamais retentee
            else:
                state["status"] = "success"
        except AgentError as exc:
            # Sorties des etapes deja reussies conservees ; chaque tentative tracee
            state = dict(last_good) if LANGGRAPH_AVAILABLE else state  # type: ignore[assignment]
            failures = exc.failures if isinstance(exc, StepFailedError) else [str(exc)]
            state["status"] = "failed"
            state["errors"] = list(state.get("errors") or []) + failures
    state["attempts"] = attempts
    _finalize_snapshot(cfg, state, steps)

    summary = _summary(state)
    summary["finished_at"] = datetime.now().isoformat(timespec="seconds")
    reports_dir = f"{(cfg.get('paths') or {}).get('reports', 'outputs/reports')}/{run_id}"
    save_json(summary, f"{reports_dir}/run.json")
    return state


__all__ = ["AGENT_CLASSES", "STEP_ORDER", "StepFailedError", "build_graph", "run_pipeline"]
