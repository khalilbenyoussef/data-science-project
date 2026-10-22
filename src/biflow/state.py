"""Etat partage du pipeline BIFlow (transmis entre les noeuds LangGraph)."""

from __future__ import annotations

import operator
from copy import deepcopy
from datetime import datetime
from typing import Annotated, Any, TypedDict


class PipelineState(TypedDict, total=False):
    """Etat commun : chaque agent lit les cles existantes et ajoute les siennes."""

    run_id: str
    objective: str
    started_at: str
    status: str

    sources: dict[str, Any]            # configuration des sources
    raw_paths: dict[str, str]          # source -> fichier brut
    raw_meta: dict[str, Any]           # source -> hash, taille, lignes
    profiles: dict[str, Any]           # source -> profil (resume)
    quality: dict[str, Any]            # rapports + score + gate
    quality_paths: dict[str, str]      # artefacts du rapport qualite
    staging_paths: dict[str, str]      # source -> CSV long harmonise
    warehouse_path: str                # data/processed/warehouse.duckdb
    kpis: dict[str, Any]               # catalogue + valeurs calculees
    kpi_values_path: str
    insights: dict[str, Any]           # analyse et recommandations
    insights_path: str
    dashboard: dict[str, Any]          # specs de visualisation
    xai: dict[str, Any]                # lineage et explications
    llm_notes: dict[str, str]          # commentaires libres produits par les LLM

    warnings: Annotated[list[str], operator.add]
    errors: Annotated[list[str], operator.add]


def new_state(objective: str, run_id: str | None = None) -> PipelineState:
    """Etat initial d'un run."""
    return PipelineState(
        run_id=run_id or datetime.now().strftime("%Y%m%dT%H%M%S"),
        objective=objective,
        started_at=datetime.now().isoformat(timespec="seconds"),
        status="running",
        sources={},
        raw_paths={},
        raw_meta={},
        profiles={},
        quality={},
        quality_paths={},
        staging_paths={},
        warehouse_path="",
        kpis={},
        kpi_values_path="",
        insights={},
        insights_path="",
        dashboard={},
        xai={},
        llm_notes={},
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
