"""API de la page « Audit et confiance » (lecture seule, donnees officielles).

Lit data/audit/audit_report.json (verdict, controles, publication, audit des
insights), la table kpi_values (motifs de revue) et kpi_explanations (meme
lecture que ``main.py explain``) ainsi que l'evaluation par injection de fautes
deja enregistree (jamais executee depuis l'API). Les sources utilisateur ne sont
pas comptees : seules les lignes du catalogue officiel sont lues.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import duckdb
from fastapi import APIRouter, HTTPException, Query

from biflow.tools.insights import insights_from_finova
from biflow.tools.kpi import DEFAULT_CATALOG, load_catalog

AFFECTED_LIMIT = 200
ISO3 = re.compile(r"^([A-Z]{3}|PEERS)$")
KPI_ID = re.compile(r"^[a-z][a-z0-9_]{1,60}$")

# Ce que verifie chaque controle, en francais simple
CHECK_DESCRIPTIONS = {
    "A1_recomputed_values": "Chaque valeur publiée est recalculée à partir des faits de l'entrepôt avec la formule du catalogue : aucun écart toléré.",
    "A2_unavailable_rows_are_null": "Une valeur indisponible reste vide, et l'observation manque vraiment dans les données : rien n'est inventé.",
    "A3_peers_recomputed": "La moyenne des pairs est recalculée à partir des pays pairs observés (moyenne simple).",
    "A4_row_completeness": "Toutes les lignes attendues (indicateur × pays × année valide) sont présentes.",
    "A5_raw_to_fact": "Les valeurs d'entrée sont retrouvées à l'identique dans le fichier brut versionné (snapshot).",
    "A6_user_source_facts": "Concerne les sources utilisateur (page « Mes données ») : leurs faits correspondent au fichier et au mapping. Hors chiffres officiels.",
    "B1_one_unit_per_kpi": "Chaque indicateur garde l'unité définie dans le catalogue.",
    "B2_value_ranges": "Les valeurs restent dans des bornes possibles (une part entre 0 et 100 %, une densité positive…).",
    "B3_country_entities_only": "Seuls des pays portent des valeurs : aucun agrégat régional ne se glisse dans les données pays.",
    "B4_peers_are_configured_peers": "La moyenne des pairs porte exactement sur les pays pairs configurés.",
    "B5_snapshot_and_run_ids": "Version des données et identifiant de run identiques partout (index, lineage, qualité, indicateurs).",
    "B6_source_hashes": "Les empreintes SHA-256 des fichiers sources concordent d'une étape à l'autre.",
    "B7_warehouse_content_digest": "L'empreinte du contenu de l'entrepôt est recalculée indépendamment et concorde.",
    "B8_catalog_definitions": "Le catalogue utilisé n'a aucune définition provisoire et correspond à celui des indicateurs publiés.",
    "B9_quality_gate": "Le contrôle qualité des sources est réussi.",
    "C1_partial_survey_wave": "Signale les vagues d'enquête partielles (couverture pays incomplète).",
    "C2_partial_peer_coverage": "Signale les moyennes de pairs calculées sans tous les pairs (publiées avec réserve).",
    "C3_input_quality_findings": "Signale les constats du contrôle qualité qui touchent une valeur d'entrée d'un indicateur.",
    "C4_within_survey_noise": "Signale les variations d'une vague à l'autre plus petites que le bruit d'enquête (à présenter comme stables).",
}
USER_CHECKS = {"A6_user_source_facts"}
REASON_LABELS = {
    "partial_peer_coverage": "moyenne des pairs incomplète",
    "no_peer_observation": "aucun pair observé",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _stamp(value: str | None) -> float | None:
    try:
        return datetime.fromisoformat(value).timestamp() if value else None
    except ValueError:
        return None


def _name_fr(catalog: Mapping[str, Any], kpi_id: str) -> str:
    kpi = (catalog.get("kpis") or {}).get(kpi_id) or {}
    return kpi.get("name_fr") or kpi.get("name") or kpi_id


def create_audit_router(*, audit_dir: Path, warehouse: Path, spec_file: Path,
                        catalog_path: str | Path = DEFAULT_CATALOG) -> APIRouter:
    router = APIRouter(prefix="/api/audit", tags=["audit"])
    report_path = audit_dir / "audit_report.json"
    evaluation_path = audit_dir / "evaluation.json"

    def report() -> dict[str, Any]:
        data = _load(report_path)
        if not data:
            raise HTTPException(status_code=503, detail="Rapport d'audit indisponible : lancez le pipeline.")
        return data

    def official_kpis() -> set[str]:
        catalog = load_catalog(catalog_path)
        return {kpi_id for kpi_id, kpi in (catalog.get("kpis") or {}).items()
                if (kpi.get("verification") or {}).get("status") != "user_declared"}

    def review_reasons() -> list[dict[str, Any]]:
        if not warehouse.is_file():
            return []
        kpis = sorted(official_kpis())
        try:
            with duckdb.connect(str(warehouse), read_only=True) as con:
                rows = con.execute(
                    "SELECT reason, count(*) FROM (SELECT unnest(review_reasons) AS reason FROM kpi_values "
                    "WHERE publication_status = 'approved_with_review_note' AND list_contains(?, kpi_id)) "
                    "GROUP BY reason ORDER BY 2 DESC, 1", [kpis]).fetchall()
        except duckdb.Error:
            return []
        return [{"reason": r[0], "label": REASON_LABELS.get(r[0], r[0]), "rows": int(r[1])} for r in rows]

    def insight_details(audit: Mapping[str, Any]) -> list[dict[str, Any]]:
        spec = _load(spec_file)
        catalog = load_catalog(catalog_path)
        by_page = {page.get("id"): page.get("insights") or [] for page in spec.get("pages") or []}
        statements = {f"{page}:{item.get('id')}": item.get("statement") for page, items in by_page.items()
                      for item in items}
        claims, _ = insights_from_finova(by_page, spec.get("facts") or [], catalog["kpis"])
        cited = {claim["insight_id"]: [{"kpi_id": c["kpi_id"], "kpi": _name_fr(catalog, c["kpi_id"]),
                                        "iso3": c["iso3"], "year": c["year"]} for c in claim["claims"]]
                 for claim in claims}
        rows = [{"insight_id": item["insight_id"], "accepted": item["accepted"], "reasons": item.get("reasons") or [],
                 "statement": statements.get(item["insight_id"]), "cited": cited.get(item["insight_id"], [])}
                for item in audit.get("results") or []]
        rows += [{"insight_id": insight_id, "accepted": None, "reasons": ["non auditable"],
                  "statement": statements.get(insight_id), "cited": []}
                 for insight_id in audit.get("not_auditable_ids") or []]
        return rows

    @router.get("/summary")
    def summary() -> dict[str, Any]:
        data = report()
        catalog = load_catalog(catalog_path)
        insight = data.get("route2_insight_audit") or {}
        evaluation = _load(evaluation_path)
        evaluated_at = evaluation.get("created_at")
        if not evaluated_at and evaluation_path.is_file():
            evaluated_at = datetime.fromtimestamp(evaluation_path.stat().st_mtime).isoformat(timespec="seconds")
        audit_time, eval_time = _stamp(data.get("created_at")), _stamp(evaluated_at)
        return {
            "verdict": data.get("verdict"), "counts": data.get("counts"), "run_id": data.get("run_id"),
            "snapshot_id": data.get("snapshot_id"), "created_at": data.get("created_at"),
            "catalog_version": catalog.get("catalog_version"),
            "publication": (data.get("publication") or {}).get("by_status"),
            "review_reasons": review_reasons(),
            "insight_audit": {key: insight.get(key) for key in ("run_id", "created_at", "audited", "accepted",
                                                                "rejected", "not_auditable")}
            | {"insights": insight_details(insight)},
            "evaluation": {
                "available": bool(evaluation), "created_at": evaluated_at,
                "stale": bool(audit_time and eval_time and eval_time < audit_time),
                "detected": evaluation.get("detected"), "total": evaluation.get("total"),
                "baseline": evaluation.get("baseline"),
                "faults": [{key: fault.get(key) for key in ("id", "label", "expected_check", "detected",
                                                            "verdict", "failing_checks")}
                           for fault in evaluation.get("faults") or []],
            },
        }

    @router.get("/checks")
    def checks() -> dict[str, Any]:
        data = report()
        out = []
        for check in data.get("checks") or []:
            rows = check.get("affected_rows") or []
            out.append({
                "check_id": check.get("check_id"), "category": check.get("category"), "result": check.get("result"),
                "description": CHECK_DESCRIPTIONS.get(check.get("check_id"), check.get("detail")),
                "detail": check.get("detail"), "affects_publication": check.get("affects_publication"),
                "user_sources": check.get("check_id") in USER_CHECKS,
                "affected_count": len(rows), "affected_rows": rows[:AFFECTED_LIMIT],
                "truncated": len(rows) > AFFECTED_LIMIT,
            })
        return {"checks": out, "created_at": data.get("created_at")}

    @router.get("/explain")
    def explain(kpi_id: str = Query(..., max_length=61), iso3: str = Query(..., min_length=3, max_length=5),
                year: int = Query(..., ge=2000, le=2100)) -> dict[str, Any]:
        """Explication enregistree par l'Auditor (meme lecture que main.py explain)."""
        code = iso3.strip().upper()
        if not KPI_ID.fullmatch(kpi_id) or kpi_id not in official_kpis():
            raise HTTPException(status_code=400, detail=f"Indicateur inconnu du catalogue officiel : {kpi_id}")
        if not ISO3.fullmatch(code):
            raise HTTPException(status_code=400, detail="Pays invalide : code ISO3 ou PEERS attendu.")
        if not warehouse.is_file():
            raise HTTPException(status_code=503, detail="Entrepôt indisponible.")
        try:
            with duckdb.connect(str(warehouse), read_only=True) as con:
                row = con.execute("SELECT explanation FROM kpi_explanations WHERE kpi_id = ? AND iso3 = ? "
                                  "AND year = ?", [kpi_id, code, year]).fetchone()
        except duckdb.Error as exc:
            raise HTTPException(status_code=503, detail="Explications indisponibles : relancez l'Auditor.") from exc
        if row is None:
            raise HTTPException(status_code=404, detail=f"Aucune explication pour {kpi_id} / {code} / {year}.")
        record = json.loads(row[0])
        catalog = load_catalog(catalog_path)
        touching = {item["check_id"]: item for item in record.get("checks") or []}
        all_checks = [c for c in report().get("checks") or [] if c.get("check_id") not in USER_CHECKS]
        for item in record.get("inputs") or []:  # fichier local : nom seul, jamais le chemin complet
            raw = item.get("raw") or {}
            if raw.get("file"):
                raw["file"] = Path(raw["file"]).name
        return {
            **{key: record.get(key) for key in ("kpi_id", "iso3", "country", "year", "value", "unit",
                                                "availability_status", "reason", "definition", "formula",
                                                "transformation", "snapshot_id", "catalog_version",
                                                "publication_status", "review_reasons", "inputs",
                                                "dependencies", "quality_findings")},
            "kpi_name": _name_fr(catalog, kpi_id),
            "checks_touching": list(touching.values()),
            "checks_passed": [c["check_id"] for c in all_checks
                              if c["check_id"] not in touching and c.get("result") == "pass"],
            "narrative": (record.get("narrative") or {}).get("fr"),
        }

    @router.get("/options")
    def options() -> dict[str, Any]:
        """Indicateurs officiels (libelle francais), pays et annees disponibles pour l'explication."""
        catalog = load_catalog(catalog_path)
        kpis = sorted(official_kpis())
        years, countries = [], []
        if warehouse.is_file():
            try:
                with duckdb.connect(str(warehouse), read_only=True) as con:
                    years = [r[0] for r in con.execute(
                        "SELECT DISTINCT year FROM kpi_explanations ORDER BY 1").fetchall()]
                    countries = [r[0] for r in con.execute(
                        "SELECT DISTINCT iso3 FROM kpi_explanations ORDER BY 1").fetchall()]
            except duckdb.Error:
                pass
        return {"kpis": [{"kpi_id": k, "label": _name_fr(catalog, k)} for k in kpis],
                "countries": countries, "years": years}

    return router


__all__ = ["CHECK_DESCRIPTIONS", "create_audit_router"]
