"""Typed, reusable Semantic & KPI tools. No LLM, collection or SQL generation.

Direct use: tools.calculate_kpi(CalculateKpiRequest(iso3='TUN', year=2024,
kpi_id='account_ownership')). LangChain callers can use tools.as_tools().
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Annotated, Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, TypeAdapter, field_validator

from biflow.config import resolve
from biflow.tools.kpi import CatalogError, DEFAULT_CATALOG, KpiCalculator, KpiResult, load_catalog
from biflow.tools.kpi_provenance import QualityWarning
from biflow.utils.countries import is_country, normalize_iso3


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ListKpisRequest(Contract):
    action: Literal["list"] = "list"


class DescribeKpiRequest(Contract):
    action: Literal["describe"] = "describe"
    kpi_id: StrictStr = Field(min_length=1)


class CalculateKpiRequest(Contract):
    action: Literal["calculate"] = "calculate"
    kpi_id: StrictStr = Field(min_length=1)
    iso3: StrictStr
    year: StrictInt = Field(ge=1, le=9999)

    @field_validator("iso3")
    @classmethod
    def country_code(cls, value: str) -> str:
        code = normalize_iso3(value)
        if not code or not is_country(code):
            raise ValueError("iso3 must identify a country; aggregates are excluded")
        return code


class LatestAvailableKpiRequest(Contract):
    action: Literal["latest_available"] = "latest_available"
    kpi_id: StrictStr = Field(min_length=1)
    iso3: StrictStr

    @field_validator("iso3")
    @classmethod
    def country_code(cls, value: str) -> str:
        return CalculateKpiRequest.country_code(value)


class CompareCountriesRequest(Contract):
    action: Literal["compare_countries"] = "compare_countries"
    kpi_id: StrictStr = Field(min_length=1)
    left_iso3: StrictStr
    right_iso3: StrictStr
    year: StrictInt = Field(ge=1, le=9999)

    @field_validator("left_iso3", "right_iso3")
    @classmethod
    def country_code(cls, value: str) -> str:
        return CalculateKpiRequest.country_code(value)


class CompareYearsRequest(Contract):
    action: Literal["compare_years"] = "compare_years"
    kpi_id: StrictStr = Field(min_length=1)
    iso3: StrictStr
    left_year: StrictInt = Field(ge=1, le=9999)
    right_year: StrictInt = Field(ge=1, le=9999)

    @field_validator("iso3")
    @classmethod
    def country_code(cls, value: str) -> str:
        return CalculateKpiRequest.country_code(value)


SemanticKpiRequest = Annotated[
    ListKpisRequest | DescribeKpiRequest | CalculateKpiRequest | LatestAvailableKpiRequest
    | CompareCountriesRequest | CompareYearsRequest,
    Field(discriminator="action")
]
REQUEST_ADAPTER = TypeAdapter(SemanticKpiRequest)


class KpiSummary(Contract):
    kpi_id: str
    name: str
    unit: str
    verification_status: str
    subgroup: str
    valid_years: tuple[int, ...]
    dependencies: tuple[str, ...]


class ListKpisResponse(Contract):
    action: Literal["list"] = "list"
    catalog_version: str
    catalog_sha256: str
    kpis: tuple[KpiSummary, ...]


class DescribeKpiResponse(Contract):
    action: Literal["describe"] = "describe"
    catalog_version: str
    catalog_sha256: str
    kpi_id: str
    # Preserve the complete validated catalog entry, including uncertainties,
    # policy references and future descriptive fields, without rewriting it.
    definition: dict[str, Any]
    policies: dict[str, Any]
    references: dict[str, Any]


class CalculateKpiResponse(Contract):
    action: Literal["calculate"] = "calculate"
    result: KpiResult


class LatestAvailableKpiResponse(Contract):
    action: Literal["latest_available"] = "latest_available"
    kpi_id: str
    iso3: str
    catalog_version: str
    catalog_sha256: str
    availability_status: Literal["available", "unavailable"]
    observation_year: int | None
    reason: str | None
    result: KpiResult | None
    skipped_observations: tuple[KpiResult, ...]


class KpiComparisonResponse(Contract):
    action: Literal["compare_countries", "compare_years"]
    kpi_id: str
    left: KpiResult
    right: KpiResult
    comparison_status: Literal["complete", "incomplete"]
    difference: float | None
    difference_unit: str
    difference_formula: Literal["right.value - left.value"] = "right.value - left.value"
    reason: str | None
    requires_review: bool
    review_reasons: tuple[str, ...]
    quality_warnings: tuple[QualityWarning, ...]
    source_warnings: tuple[QualityWarning, ...]
    publication_status: Literal["not_evaluated"] = "not_evaluated"


SemanticKpiResponse = Annotated[
    ListKpisResponse | DescribeKpiResponse | CalculateKpiResponse | LatestAvailableKpiResponse
    | KpiComparisonResponse,
    Field(discriminator="action")
]
RESPONSE_ADAPTER = TypeAdapter(SemanticKpiResponse)


class SemanticKpiTools:
    """Catalog discovery plus an unchanged, lazy read-only KpiCalculator.

    Invalid inputs/unknown KPIs raise ValueError (Pydantic validation errors
    subclass ValueError). Database and sidecar behavior stays with the calculator.
    Availability and publication review are distinct; no method grants approval.
    """

    def __init__(self, warehouse_path: str | Path,
                 catalog_path: str | Path = DEFAULT_CATALOG, *,
                 lineage_path: str | Path | None = None,
                 quality_report_path: str | Path | None = None):
        self.catalog_path = resolve(catalog_path)
        self._catalog = load_catalog(self.catalog_path)
        self._catalog_hash = hashlib.sha256(self.catalog_path.read_bytes()).hexdigest()
        self._calculator_args = dict(warehouse_path=warehouse_path, catalog_path=self.catalog_path,
                                     lineage_path=lineage_path, quality_report_path=quality_report_path)

    def list_kpis(self, request: ListKpisRequest) -> ListKpisResponse:
        ListKpisRequest.model_validate(request)
        return ListKpisResponse(
            catalog_version=self._catalog["catalog_version"], catalog_sha256=self._catalog_hash,
            kpis=tuple(KpiSummary(kpi_id=key, name=k["name"], unit=k["unit"],
                                  verification_status=k["verification"]["status"], subgroup=k["subgroup"],
                                  valid_years=tuple(k["valid_years"]), dependencies=tuple(k["dependencies"]))
                       for key, k in self._catalog["kpis"].items()),
        )

    def describe_kpi(self, request: DescribeKpiRequest) -> DescribeKpiResponse:
        request = DescribeKpiRequest.model_validate(request)
        if request.kpi_id not in self._catalog["kpis"]:
            raise ValueError(f"Unknown KPI: {request.kpi_id}")
        return DescribeKpiResponse(
            catalog_version=self._catalog["catalog_version"], catalog_sha256=self._catalog_hash,
            kpi_id=request.kpi_id, definition=self._catalog["kpis"][request.kpi_id],
            policies={key: self._catalog[key] for key in ("missing_data_policy", "aggregation_policy",
                      "traceability_policy", "publication_review_policy")},
            references=self._catalog["references"],
        ).model_copy(deep=True)

    def calculate_kpi(self, request: CalculateKpiRequest) -> CalculateKpiResponse:
        request = CalculateKpiRequest.model_validate(request)
        if request.kpi_id not in self._catalog["kpis"]:
            raise ValueError(f"Unknown KPI: {request.kpi_id}")
        calculator = KpiCalculator(**self._calculator_args)
        result = calculator.calculate(request.iso3, request.year, request.kpi_id)
        if result.catalog_sha256 != self._catalog_hash:
            raise CatalogError("Catalog changed; recreate SemanticKpiTools before calculating")
        return CalculateKpiResponse(result=result)

    def latest_available(self, request: LatestAvailableKpiRequest) -> LatestAvailableKpiResponse:
        request = LatestAvailableKpiRequest.model_validate(request)
        if request.kpi_id not in self._catalog["kpis"]:
            raise ValueError(f"Unknown KPI: {request.kpi_id}")
        selection = KpiCalculator(**self._calculator_args).calculate_latest(request.iso3, request.kpi_id)
        results = ((selection.result,) if selection.result is not None else ()) + selection.skipped_observations
        if any(r.catalog_sha256 != self._catalog_hash for r in results):
            raise CatalogError("Catalog changed; recreate SemanticKpiTools before calculating")
        return LatestAvailableKpiResponse(
            kpi_id=request.kpi_id, iso3=request.iso3, catalog_version=self._catalog["catalog_version"],
            catalog_sha256=self._catalog_hash,
            availability_status="available" if selection.result is not None else "unavailable",
            observation_year=selection.result.observation_year if selection.result is not None else None,
            reason=None if selection.result is not None else "no_available_observation",
            result=selection.result, skipped_observations=selection.skipped_observations,
        )

    def compare_countries(self, request: CompareCountriesRequest) -> KpiComparisonResponse:
        request = CompareCountriesRequest.model_validate(request)
        return self._compare(request.action, request.kpi_id, request.left_iso3, request.year,
                             request.right_iso3, request.year)

    def compare_years(self, request: CompareYearsRequest) -> KpiComparisonResponse:
        request = CompareYearsRequest.model_validate(request)
        return self._compare(request.action, request.kpi_id, request.iso3, request.left_year,
                             request.iso3, request.right_year)

    def _compare(self, action, kpi_id, left_iso3, left_year, right_iso3, right_year):
        # Explicit-year calculation only. Never invoke latest_available here.
        left = self.calculate_kpi(CalculateKpiRequest(
            kpi_id=kpi_id, iso3=left_iso3, year=left_year)).result
        right = self.calculate_kpi(CalculateKpiRequest(
            kpi_id=kpi_id, iso3=right_iso3, year=right_year)).result
        missing = [label for label, result in (("left", left), ("right", right))
                   if result.availability_status != "available" or result.value is None]
        reason = "_and_".join(missing) + "_observation_unavailable" if missing else None
        identity = ("kpi_id", "unit", "source", "indicator_code", "subgroup",
                    "definition_version", "catalog_sha256")
        if any(getattr(left, key) != getattr(right, key) for key in identity):
            reason = "incompatible_observations"
        if (left.provenance and right.provenance
                and left.provenance.warehouse_sha256 != right.provenance.warehouse_sha256):
            reason = "warehouse_changed_between_observations"
        review = list(dict.fromkeys(left.review_reasons + right.review_reasons))
        if reason:
            review.append(reason)
        return KpiComparisonResponse(
            action=action, kpi_id=kpi_id, left=left, right=right,
            comparison_status="incomplete" if reason else "complete",
            difference=None if reason else right.value - left.value,
            difference_unit="percentage_points" if left.unit == "percent" else left.unit,
            reason=reason, requires_review=left.requires_review or right.requires_review or bool(reason),
            review_reasons=tuple(review),
            quality_warnings=tuple(dict.fromkeys(left.quality_warnings + right.quality_warnings)),
            source_warnings=tuple(dict.fromkeys(left.source_warnings + right.source_warnings)),
        )

    def as_tools(self) -> tuple[StructuredTool, ...]:
        """Callable tools with JSON schemas; invoking them never invokes an LLM."""
        def list_kpis(action: Literal["list"] = "list") -> dict:
            return self.list_kpis(ListKpisRequest(action=action)).model_dump(mode="json")

        def describe_kpi(kpi_id: str, action: Literal["describe"] = "describe") -> dict:
            return self.describe_kpi(DescribeKpiRequest(kpi_id=kpi_id, action=action)).model_dump(mode="json")

        def calculate_kpi(kpi_id: str, iso3: str, year: int,
                          action: Literal["calculate"] = "calculate") -> dict:
            return self.calculate_kpi(CalculateKpiRequest(
                kpi_id=kpi_id, iso3=iso3, year=year, action=action)).model_dump(mode="json")

        def latest_available(kpi_id: str, iso3: str,
                             action: Literal["latest_available"] = "latest_available") -> dict:
            return self.latest_available(LatestAvailableKpiRequest(
                kpi_id=kpi_id, iso3=iso3, action=action)).model_dump(mode="json")

        def compare_countries(kpi_id: str, left_iso3: str, right_iso3: str, year: int,
                              action: Literal["compare_countries"] = "compare_countries") -> dict:
            return self.compare_countries(CompareCountriesRequest(
                action=action, kpi_id=kpi_id, left_iso3=left_iso3, right_iso3=right_iso3,
                year=year)).model_dump(mode="json")

        def compare_years(kpi_id: str, iso3: str, left_year: int, right_year: int,
                          action: Literal["compare_years"] = "compare_years") -> dict:
            return self.compare_years(CompareYearsRequest(
                action=action, kpi_id=kpi_id, iso3=iso3, left_year=left_year,
                right_year=right_year)).model_dump(mode="json")

        return tuple(StructuredTool.from_function(func=func, name=name, description=description,
                                                  args_schema=schema)
                     for func, name, description, schema in (
                         (list_kpis, "list_kpis", "List catalog KPIs, units, definition status and years.", ListKpisRequest),
                         (describe_kpi, "describe_kpi", "Describe a KPI and its source definitions and review policies.", DescribeKpiRequest),
                         (calculate_kpi, "calculate_kpi", "Read a country/year KPI with full provenance and review warnings; never approve publication.", CalculateKpiRequest),
                         (latest_available, "latest_available", "Read the latest valid catalog-year observation, disclosing its actual year and skipped observations; never approve publication.", LatestAvailableKpiRequest),
                         (compare_countries, "compare_countries", "Compare two countries in one explicit year; difference is right minus left in percentage points or native density units, never relative growth.", CompareCountriesRequest),
                         (compare_years, "compare_years", "Compare one country at two explicit years; retain both inputs and their review flags. No year substitution or relative growth calculation.", CompareYearsRequest),
                     ))
