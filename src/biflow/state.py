"""Etat partage du pipeline BIFlow (transmis entre les noeuds LangGraph)."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, TypedDict


class PipelineState(TypedDict, total=False):
    """Etat commun : chaque agent lit les cles existantes et ajoute les siennes."""

    run_id: str
    objective: str
    started_at: str
    status: str

    sources: dict[str, Any]            # configuration des sources
    raw_paths: dict[str, str]          # source -> fichier brut
    profiles: dict[str, Any]           # source -> profil
    quality: dict[str, Any]            # rapports + score + gate
    staging_paths: dict[str, str]      # source -> CSV long harmonise
    warehouse_path: str                # data/processed/warehouse.duckdb
    kpis: dict[str, Any]               # catalogue + valeurs calculees
    insights: dict[str, Any]           # analyse et recommandations
    dashboard: dict[str, Any]          # specs de visualisation
    xai: dict[str, Any]                # lineage et explications

    warnings: list[str]
    errors: list[str]


def new_state(objective: str, run_id: str | None = None) -> PipelineState:
    """Etat initial d'un run."""
    return PipelineState(
        run_id=run_id or datetime.now().strftime("%Y%m%dT%H%M%S"),
        objective=objective,
        started_at=datetime.now().isoformat(timespec="seconds"),
        status="running",
        sources={},
        raw_paths={},
        profiles={},
        quality={},
        staging_paths={},
        warehouse_path="",
        kpis={},
        insights={},
        dashboard={},
        xai={},
        warnings=[],
        errors=[],
    )


def add_warning(state: PipelineState, message: str) -> None:
    state.setdefault("warnings", []).append(message)


def add_error(state: PipelineState, message: str) -> None:
    state.setdefault("errors", []).append(message)


def merge(state: PipelineState, updates: dict[str, Any]) -> PipelineState:
    """Fusionne les sorties d'un agent dans l'etat (copie profonde)."""
    merged: PipelineState = deepcopy(dict(state))  # type: ignore[assignment]
    merged.update(updates)
    return merged
