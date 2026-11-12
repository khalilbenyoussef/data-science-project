"""Pistes de recommandation et rapports PDF de la plateforme (lecture seule).

``GET /api/recommendations`` applique les regles de config/recommendations.yaml aux
lignes kpi_values auditees du pays et de l'annee choisis.
``GET /api/reports/evaluation.pdf`` et ``GET /api/reports/insights.pdf`` construisent
les rapports a la demande, en memoire, depuis l'etat courant : les chiffres d'audit
sont ceux de /api/audit/summary, le statut des constats est recalcule contre
kpi_values. Aucun fichier n'est ecrit ; jamais genere par ``main.py run``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import duckdb
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from biflow.tools.audit_checks import read_kpi_rows
from biflow.tools.deliverables import Context, evaluation_freshness, load_context
from biflow.tools.insights import audit_insights, insight_details, insights_from_finova
from biflow.tools.kpi import DEFAULT_CATALOG, load_catalog
from biflow.tools.user_sources.comparisons import INDICATIVE, comparisons, official_kpis
from biflow.tools.user_sources.data import UserData
from biflow.tools.recommendations import (
    RULES_PATH, RulesError, load_rules, recommendations_for, user_recommendations,
)
from dashboard_app.api.audit import audit_views

SpecFor = Callable[[str, int], tuple[dict[str, Any], str]]

ISO3 = re.compile(r"^[A-Z]{3}$")

# Pages exclues des rapports telechargeables : leurs references (SMIG, pauvrete INS)
# ne proviennent pas de l'entrepot de donnees.
HIDDEN_REPORT_PAGES = {"poverty"}


def scope(iso3: str, year: int) -> tuple[str, int]:
    code = iso3.strip().upper()
    if not ISO3.fullmatch(code):
        raise HTTPException(status_code=400, detail="Pays invalide : code ISO3 attendu.")
    return code, int(year)


def _pdf(content: bytes, filename: str) -> Response:
    return Response(content=content, media_type="application/pdf", headers={
        "Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


def user_annex(user_data: UserData | None, warehouse: Path, iso3: str, year: int) -> dict[str, Any]:
    """Annexe « vos données » : valeurs utilisateur du pays (année choisie ou dernière
    année antérieure) et comparaisons déclarées ; jamais mélangées aux constats officiels."""
    if user_data is None:
        return {"values": [], "comparisons": {"rows": [], "note": INDICATIVE}}
    values = []
    for item in user_data.indicators():
        row = user_data.latest(item["code"], iso3, year)
        values.append({"label": item["label"], "unit": item["unit"], "row": row})
    return {"values": values, "comparisons": comparisons(user_data, warehouse, iso3, year, official_kpis())}


def create_reports_router(*, warehouse: Path, audit_dir: Path, spec_file: Path,
                          catalog_path: str | Path = DEFAULT_CATALOG,
                          rules_path: str | Path = RULES_PATH,
                          context: Callable[[], Context] | None = None,
                          spec_for: SpecFor | None = None,
                          user_data: UserData | None = None) -> APIRouter:
    router = APIRouter(tags=["reports"])
    views = audit_views(audit_dir=audit_dir, warehouse=warehouse, spec_file=spec_file, catalog_path=catalog_path)
    context = context or load_context

    def recommendations(iso3: str, year: int) -> dict[str, Any]:
        code, year = scope(iso3, year)
        try:
            result = recommendations_for(warehouse, code, year, load_catalog(catalog_path)["kpis"], rules_path)
        except RulesError as exc:
            raise HTTPException(status_code=503, detail=f"Règles de recommandation invalides : {exc}") from exc
        except duckdb.Error as exc:
            raise HTTPException(status_code=503, detail="Entrepôt indisponible.") from exc
        return result

    def user_recs(iso3: str, year: int) -> dict[str, Any]:
        """Pistes « à partir de vos données » (règle user_vs_official), séparées des officielles."""
        if user_data is None:
            return {"recommendations": [], "rejected": [], "rules_checked": 0}
        try:
            rules = load_rules(rules_path)
        except RulesError as exc:
            raise HTTPException(status_code=503, detail=f"Règles de recommandation invalides : {exc}") from exc
        return user_recommendations(comparisons(user_data, warehouse, iso3, year, official_kpis()), rules)

    @router.get("/api/recommendations")
    def get_recommendations(iso3: str = Query(..., min_length=3, max_length=3),
                            year: int = Query(..., ge=2000, le=2100)) -> dict[str, Any]:
        result = recommendations(iso3, year)
        mine = user_recs(result["iso3"], result["year"])
        return {**{k: result[k] for k in ("iso3", "year", "country", "rules_version", "rules_checked",
                                          "recommendations")},
                "rejected": len(result["rejected"]),
                "user_recommendations": mine["recommendations"], "user_rejected": len(mine["rejected"])}

    @router.get("/api/reports/evaluation.pdf")
    def evaluation_report() -> Response:
        from dashboard_app.api.pdf_reports import evaluation_pdf

        ctx = context()
        summary = views.summary()  # 503 si le rapport d'audit manque
        content = evaluation_pdf(ctx, summary, views.checks()["checks"], evaluation_freshness(ctx))
        return _pdf(content, f"finova_evaluation_{ctx.snapshot_id}.pdf")

    @router.get("/api/reports/insights.pdf")
    def insights_report(iso3: str = Query(..., min_length=3, max_length=3),
                        year: int = Query(..., ge=2000, le=2100),
                        annexe: bool = Query(False, description="ajoute « Annexe : vos données »")) -> Response:
        from dashboard_app.api.pdf_reports import insights_pdf

        code, year = scope(iso3, year)
        if spec_for is None:
            raise HTTPException(status_code=503, detail="Spec indisponible.")
        spec, _ = spec_for(code, year)
        code = str((spec.get("country") or {}).get("iso3") or code)
        year = int(spec.get("year") or year)
        kpis = load_catalog(catalog_path)["kpis"]
        # Hors entrepot : le SMIG et la pauvreté ne doivent pas reapparaitre dans le
        # rapport telechargeable, même si le contrat les porte encore.
        by_page = {page.get("id"): page.get("insights") or [] for page in spec.get("pages") or []
                   if page.get("id") not in HIDDEN_REPORT_PAGES}
        claims, not_auditable = insights_from_finova(by_page, spec.get("facts") or [], kpis)
        rows = []
        if warehouse.is_file():
            try:
                with duckdb.connect(str(warehouse), read_only=True) as con:
                    rows = read_kpi_rows(con)
            except duckdb.Error as exc:
                raise HTTPException(status_code=503, detail="Entrepôt indisponible.") from exc
        audit = {"results": audit_insights(claims, rows), "not_auditable_ids": not_auditable}
        titles = {page.get("id"): page.get("title") or page.get("id") for page in spec.get("pages") or []}
        insights = [{**item, "page": titles.get(item["insight_id"].split(":", 1)[0], "")}
                    for item in insight_details(spec, audit, kpis)]
        scope_info = {"iso3": code, "year": year, "country": (spec.get("country") or {}).get("name"),
                      "generated_at": spec.get("generated_at")}
        annex = user_annex(user_data, warehouse, code, year) if annexe else None
        if annex is not None:
            annex["recommendations"] = user_recs(code, year)["recommendations"]
        content = insights_pdf(context(), scope_info, insights, recommendations(code, year), annex=annex)
        suffix = "_avec_vos_donnees" if annexe else ""
        return _pdf(content, f"finova_constats_{code}_{year}{suffix}.pdf")

    return router


__all__ = ["create_reports_router"]
