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
    llm_notes: dict[str, str]          # commentaires libres produits par les LLM
    # Optional opt-in semantic channels; normal pipeline defaults are unchanged.
    semantic_kpi_request: dict[str, Any]
    semantic_kpi_response: dict[str, Any]
    lineage_path: str
    # Etape semantic_kpi du pipeline (absente tant que l'etape n'a pas tourne)
    kpi_paths: dict[str, str]          # table kpi_values + parquet
    kpi_summary: dict[str, Any]        # comptes disponibles / a revoir
    attempts: list[dict[str, Any]]     # tentatives par etape (retry de l'orchestrateur)
    snapshot: dict[str, Any]           # statut new / no_change / published / not_published
    snapshot_id: str                   # version des sources brutes (data/snapshots/vN)
    audit: dict[str, Any]              # verdict + controles de l'Auditor
    insights: list[dict[str, Any]]     # insights de l'agent Analyst (a venir), audites par l'Auditor
    excluded_sources: list[dict[str, Any]]  # sources utilisateur exclues (etape, raison, score qualite)
    rebuild: bool                      # --rebuild : sources lues depuis le snapshot publie

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
