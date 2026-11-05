"""Pistes de recommandation et rapports de la plateforme (lecture seule).

``GET /api/recommendations`` applique les regles de config/recommendations.yaml aux
lignes kpi_values auditees du pays et de l'annee choisis. Rien n'est ecrit : ni
l'entrepot, ni les rapports, ni le cache.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import duckdb
from fastapi import APIRouter, HTTPException, Query

from biflow.tools.kpi import DEFAULT_CATALOG, load_catalog
from biflow.tools.recommendations import RULES_PATH, RulesError, recommendations_for

ISO3 = re.compile(r"^[A-Z]{3}$")


def scope(iso3: str, year: int) -> tuple[str, int]:
    code = iso3.strip().upper()
    if not ISO3.fullmatch(code):
        raise HTTPException(status_code=400, detail="Pays invalide : code ISO3 attendu.")
    return code, int(year)


def create_reports_router(*, warehouse: Path, audit_dir: Path, spec_file: Path,
                          catalog_path: str | Path = DEFAULT_CATALOG,
                          rules_path: str | Path = RULES_PATH) -> APIRouter:
    router = APIRouter(tags=["reports"])

    def recommendations(iso3: str, year: int) -> dict[str, Any]:
        code, year = scope(iso3, year)
        try:
            result = recommendations_for(warehouse, code, year, load_catalog(catalog_path)["kpis"], rules_path)
        except RulesError as exc:
            raise HTTPException(status_code=503, detail=f"Règles de recommandation invalides : {exc}") from exc
        except duckdb.Error as exc:
            raise HTTPException(status_code=503, detail="Entrepôt indisponible.") from exc
        return result

    @router.get("/api/recommendations")
    def get_recommendations(iso3: str = Query(..., min_length=3, max_length=3),
                            year: int = Query(..., ge=2000, le=2100)) -> dict[str, Any]:
        result = recommendations(iso3, year)
        return {**{k: result[k] for k in ("iso3", "year", "country", "rules_version", "rules_checked",
                                          "recommendations")},
                "rejected": len(result["rejected"])}

    return router


__all__ = ["create_reports_router"]
