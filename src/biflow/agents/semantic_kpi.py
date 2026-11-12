"""Deterministic Semantic & KPI Agent.

Request mode: agent.run({'semantic_kpi_request': {'action': 'calculate',
'iso3': 'TUN', 'year': 2024, 'kpi_id': 'account_ownership'}}).
Pipeline mode (no request key, step after etl): every catalog KPI for kpi.focus
and kpi.peers over each valid catalog year -> warehouse table kpi_values and
kpi_values.parquet. Facts are only read; run() writes its usual agent report.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from biflow.agents.base import AgentError, BaseAgent
from biflow.config import resolve
from biflow.tools.kpi import DEFAULT_CATALOG, shared_read_only_connection
from biflow.tools.kpi_values import compute_kpi_values, peer_codes, write_kpi_values
from biflow.utils.io import remember_sha256
from biflow.tools.semantic_kpi import (
    CalculateKpiRequest, CalculateKpiResponse, DescribeKpiRequest, DescribeKpiResponse,
    ListKpisRequest, ListKpisResponse, REQUEST_ADAPTER, SemanticKpiTools,
    LatestAvailableKpiRequest, LatestAvailableKpiResponse,
    CompareCountriesRequest, CompareYearsRequest, KpiComparisonResponse,
)


class SemanticKpiAgent(BaseAgent):
    name = "semantic_kpi"

    def __init__(self, cfg=None, run_id=None, log=None, *,
                 warehouse_path: str | Path | None = None,
                 catalog_path: str | Path = DEFAULT_CATALOG,
                 lineage_path: str | Path | None = None,
                 quality_report_path: str | Path | None = None):
        super().__init__(cfg=cfg, run_id=run_id, log=log)
        paths = self.cfg.get("paths") or {}
        self.tools = SemanticKpiTools(
            warehouse_path if warehouse_path is not None else Path(paths.get("processed", "data/processed")) / "warehouse.duckdb",
            catalog_path=catalog_path, lineage_path=lineage_path,
            quality_report_path=(quality_report_path if quality_report_path is not None
                                 else Path(paths.get("quality", "data/quality")) / "quality_report.json"),
        )

    def get_llm(self):
        """This agent is deterministic, even when global LLM configuration is on."""
        self.llm_error = "Semantic KPI tools never use an LLM"
        return None

    def list_kpis(self, request: ListKpisRequest) -> ListKpisResponse:
        return self.tools.list_kpis(request)

    def describe_kpi(self, request: DescribeKpiRequest) -> DescribeKpiResponse:
        return self.tools.describe_kpi(request)

    def calculate_kpi(self, request: CalculateKpiRequest) -> CalculateKpiResponse:
        return self.tools.calculate_kpi(request)

    def latest_available(self, request: LatestAvailableKpiRequest) -> LatestAvailableKpiResponse:
        return self.tools.latest_available(request)

    def compare_countries(self, request: CompareCountriesRequest) -> KpiComparisonResponse:
        return self.tools.compare_countries(request)

    def compare_years(self, request: CompareYearsRequest) -> KpiComparisonResponse:
        return self.tools.compare_years(request)

    def get_tools(self):
        return self.tools.as_tools()

    def _execute_batch(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        """Mode pipeline : calcul par lot, lecture seule des faits."""
        kpi_cfg = self.cfg.get("kpi") or {}
        try:
            focus, peers = peer_codes(kpi_cfg.get("focus"), kpi_cfg.get("peers"))
        except ValueError as exc:
            raise AgentError(f"configuration kpi invalide : {exc}") from exc
        paths = self.cfg.get("paths") or {}
        warehouse = Path(ctx.get("warehouse_path") or resolve(
            Path(paths.get("processed", "data/processed")) / "warehouse.duckdb"))
        quality_json = (ctx.get("quality_paths") or {}).get("json") or resolve(
            Path(paths.get("quality", "data/quality")) / "quality_report.json")
        tools = SemanticKpiTools(warehouse, catalog_path=self.tools.catalog_path,
                                 lineage_path=warehouse.with_name("lineage.json"),
                                 quality_report_path=quality_json)
        # Hash des sources calcules une fois par run (collector) : pas de re-hachage
        # par lookup tant que taille et mtime du fichier sont inchanges.
        for meta in (ctx.get("raw_meta") or {}).values():
            if isinstance(meta, dict) and meta.get("path"):
                remember_sha256(meta["path"], meta.get("sha256"), meta.get("size_bytes"),
                                meta.get("mtime_ns"))
        self.log.info("[semantic_kpi] calcul des KPI : focus=%s, pairs=%s", focus, ", ".join(peers))
        snapshot_id = ctx.get("snapshot_id")
        if snapshot_id is None:  # ex. --only semantic_kpi : version enregistree par l'ETL
            try:
                snapshot_id = json.loads(warehouse.with_name("lineage.json").read_text(
                    encoding="utf-8")).get("snapshot_id")
            except (OSError, ValueError, AttributeError):
                snapshot_id = None
        # Une seule connexion lecture seule pour tous les lookups, fermee avant l'ecriture
        with shared_read_only_connection(warehouse):
            rows = compute_kpi_values(tools, focus, peers, self.run_id, snapshot_id)
        parquet = warehouse.with_name("kpi_values.parquet")
        write_kpi_values(rows, warehouse, parquet)

        focus_rows = [row for row in rows if row["iso3"] == focus]
        summary = {
            "focus": focus, "peers": peers, "rows": len(rows), "snapshot_id": snapshot_id,
            "kpis": len({row["kpi_id"] for row in rows}),
            "available": sum(row["availability_status"] == "available" for row in rows),
            "unavailable": sum(row["availability_status"] == "unavailable" for row in rows),
            "requires_review": sum(row["requires_review"] for row in rows),
            "partial_peer_rows": sum(row["peer_status"] == "partial" for row in rows),
            "catalog_version": rows[0]["catalog_version"] if rows else None,
        }
        warnings = []
        if not any(row["availability_status"] == "available" for row in focus_rows):
            warnings.append(f"[semantic_kpi] aucune valeur KPI disponible pour {focus}")
        self.log.info("[semantic_kpi] %d lignes -> table kpi_values, %s", len(rows), parquet)
        notes = dict(ctx.get("llm_notes") or {})
        notes["semantic_kpi"] = (
            f"{summary['rows']} valeurs KPI ({summary['available']} disponibles, "
            f"{summary['requires_review']} à revoir)"
        )
        return {
            "kpi_paths": {"table": "kpi_values", "warehouse": str(warehouse), "parquet": str(parquet)},
            "kpi_summary": summary,
            "llm_notes": notes,
            "warnings": warnings,
        }

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        if "semantic_kpi_request" not in ctx:
            return self._execute_batch(ctx)
        request = REQUEST_ADAPTER.validate_python(ctx.get("semantic_kpi_request"))
        if isinstance(request, ListKpisRequest):
            response = self.list_kpis(request)
        elif isinstance(request, DescribeKpiRequest):
            response = self.describe_kpi(request)
        elif isinstance(request, LatestAvailableKpiRequest):
            response = self.latest_available(request)
        elif isinstance(request, CompareCountriesRequest):
            response = self.compare_countries(request)
        elif isinstance(request, CompareYearsRequest):
            response = self.compare_years(request)
        else:
            response = self.calculate_kpi(request)
        if isinstance(response, LatestAvailableKpiResponse):
            results = ((response.result,) if response.result is not None else ()) + response.skipped_observations
            warnings = list(dict.fromkeys(reason for result in results for reason in result.review_reasons))
        elif isinstance(response, KpiComparisonResponse):
            warnings = list(response.review_reasons)
        else:
            warnings = list(response.result.review_reasons) if isinstance(response, CalculateKpiResponse) else []
        return {"semantic_kpi_response": response.model_dump(mode="json"), "warnings": warnings}
