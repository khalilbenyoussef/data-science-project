"""Calcul par lot des KPI du catalogue (pays focus + pairs) -> table kpi_values.

Lecture seule des faits via SemanticKpiTools ; aucune valeur n'est imputee :
une observation absente reste NULL / unavailable, jamais 0. La ligne PEERS est
la moyenne simple (non ponderee) des pairs disponibles, methode nommee
simple_mean_<n>_peers ; elle n'est signalee pour revue que si un pair manque
(ou si un pair inclus porte lui-meme une raison de revue).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

import duckdb

from biflow.tools.semantic_kpi import CalculateKpiRequest, ListKpisRequest, SemanticKpiTools
from biflow.utils.countries import normalize_iso3

PEERS_ISO3 = "PEERS"


def peer_method(n_peers: int) -> str:
    """Nom explicite de la methode, ex. simple_mean_4_peers."""
    return f"simple_mean_{n_peers}_peers"

COLUMNS = (
    "kpi_id", "iso3", "year", "value", "unit", "availability_status", "reason",
    "definition_status", "requires_review", "review_reasons", "publication_status", "peer_status",
    "peers_included", "missing_peers", "aggregation_method",
    "catalog_version", "catalog_sha256", "snapshot_id", "run_id",
)
KPI_VALUES_DDL = """
CREATE OR REPLACE TABLE kpi_values (
    kpi_id VARCHAR NOT NULL,
    iso3 VARCHAR NOT NULL,
    year INTEGER NOT NULL,
    value DOUBLE,
    unit VARCHAR NOT NULL,
    availability_status VARCHAR NOT NULL,
    reason VARCHAR,
    definition_status VARCHAR NOT NULL,
    requires_review BOOLEAN NOT NULL,
    review_reasons VARCHAR[] NOT NULL,
    publication_status VARCHAR NOT NULL,
    peer_status VARCHAR,
    peers_included VARCHAR[],
    missing_peers VARCHAR[],
    aggregation_method VARCHAR,
    catalog_version VARCHAR NOT NULL,
    catalog_sha256 VARCHAR NOT NULL,
    snapshot_id VARCHAR,
    run_id VARCHAR NOT NULL,
    PRIMARY KEY (kpi_id, iso3, year)
)
"""


def peer_codes(focus: Any, peers: Iterable[Any] | None) -> tuple[str, list[str]]:
    """Normalise le pays focus et les pairs (alias ISO3, doublons et focus retires)."""
    code = normalize_iso3(focus)
    if not code:
        raise ValueError("kpi.focus doit etre un code ISO3 de pays")
    normalized = []
    for peer in peers or []:
        peer_code = normalize_iso3(peer)
        if not peer_code:
            raise ValueError(f"code pair invalide : {peer!r}")
        if peer_code != code and peer_code not in normalized:
            normalized.append(peer_code)
    return code, normalized


def _country_row(result, run_id: str, snapshot_id: str | None) -> dict[str, Any]:
    available = result.availability_status == "available" and result.value is not None
    return {
        "kpi_id": result.kpi_id, "iso3": result.iso3, "year": result.observation_year,
        "value": float(result.value) if available else None, "unit": result.unit,
        "availability_status": result.availability_status, "reason": result.reason,
        "definition_status": result.verification_status,
        "requires_review": bool(result.requires_review),
        "review_reasons": list(result.review_reasons),
        "publication_status": "not_evaluated",  # decide par l'Auditor
        "peer_status": None, "peers_included": None, "missing_peers": None,
        "aggregation_method": None, "catalog_version": result.catalog_version,
        "catalog_sha256": result.catalog_sha256, "snapshot_id": snapshot_id, "run_id": run_id,
    }


def _peer_row(kpi, year: int, results: list, catalog, run_id: str,
              snapshot_id: str | None = None) -> dict[str, Any]:
    included = [r for r in results if r.availability_status == "available" and r.value is not None]
    missing = [r.iso3 for r in results if r not in included]
    if not included:
        status, reason = "none", "no_peer_observation"
    elif missing:
        status, reason = "partial", "partial_peer_coverage"
    else:
        status, reason = "complete", None
    review = [reason for r in included for reason in r.review_reasons]
    if reason:  # au moins un pair manquant
        review.append(reason)
    review = list(dict.fromkeys(review))
    return {
        "kpi_id": kpi.kpi_id, "iso3": PEERS_ISO3, "year": year,
        "value": sum(r.value for r in included) / len(included) if included else None,
        "unit": kpi.unit, "availability_status": "available" if included else "unavailable",
        "reason": reason, "definition_status": kpi.verification_status,
        "requires_review": bool(review), "review_reasons": review,
        "publication_status": "not_evaluated", "peer_status": status, "peers_included": [r.iso3 for r in included],
        "missing_peers": missing, "aggregation_method": peer_method(len(results)),
        "catalog_version": catalog.catalog_version, "catalog_sha256": catalog.catalog_sha256,
        "snapshot_id": snapshot_id, "run_id": run_id,
    }


def compute_kpi_values(tools: SemanticKpiTools, focus: str, peers: list[str],
                       run_id: str, snapshot_id: str | None = None) -> list[dict[str, Any]]:
    """Chaque KPI x pays (focus + pairs) x annee valide du catalogue, plus PEERS."""
    catalog = tools.list_kpis(ListKpisRequest())
    rows: list[dict[str, Any]] = []
    for kpi in catalog.kpis:
        for year in kpi.valid_years:
            peer_results = []
            for iso3 in [focus, *peers]:
                result = tools.calculate_kpi(CalculateKpiRequest(
                    kpi_id=kpi.kpi_id, iso3=iso3, year=year)).result
                rows.append(_country_row(result, run_id, snapshot_id))
                if iso3 != focus:
                    peer_results.append(result)
            if peers:
                rows.append(_peer_row(kpi, year, peer_results, catalog, run_id, snapshot_id))
    return rows


def write_kpi_values(rows: list[dict[str, Any]], warehouse_path: str | Path,
                     parquet_path: str | Path) -> int:
    """Remplace la table kpi_values (transaction) puis exporte le Parquet (atomique)."""
    parquet_path = Path(parquet_path)
    placeholders = ", ".join("?" for _ in COLUMNS)
    conn = duckdb.connect(str(warehouse_path))
    try:
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute(KPI_VALUES_DDL)
            if rows:
                conn.executemany(f"INSERT INTO kpi_values VALUES ({placeholders})",
                                 [tuple(row[c] for c in COLUMNS) for row in rows])
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        tmp = parquet_path.with_name(f".{parquet_path.name}.tmp")
        target = str(tmp).replace("'", "''")
        conn.execute(
            f"COPY (SELECT * FROM kpi_values ORDER BY kpi_id, iso3, year) "
            f"TO '{target}' (FORMAT PARQUET)"
        )
    finally:
        conn.close()
    os.replace(tmp, parquet_path)
    return len(rows)


__all__ = ["COLUMNS", "PEERS_ISO3", "compute_kpi_values", "peer_codes",
           "peer_method", "write_kpi_values"]
