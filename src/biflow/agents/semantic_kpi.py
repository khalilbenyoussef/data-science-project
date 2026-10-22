"""Standalone deterministic Semantic & KPI Agent; not registered in the graph.

BaseAgent use: agent.run({'semantic_kpi_request': {'action': 'calculate',
'iso3': 'TUN', 'year': 2024, 'kpi_id': 'account_ownership'}}).
run() writes its usual agent report; direct methods and tools only read inputs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from biflow.agents.base import BaseAgent
from biflow.tools.kpi import DEFAULT_CATALOG
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

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
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
