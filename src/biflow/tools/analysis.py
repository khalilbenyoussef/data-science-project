"""Deterministic Route 2 analysis dataset built on the Semantic & KPI contracts.

Every number comes from ``SemanticKpiTools``; this module never generates SQL,
never recalculates an indicator from the wide tables, never fills gaps and never
approves publication. Missing observations remain null with an explicit status.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Literal

import duckdb
from pydantic import Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from biflow.config import resolve
from biflow.tools.kpi import CONTRACTS, DEFAULT_CATALOG, KpiResult
from biflow.tools.semantic_kpi import (
    CalculateKpiRequest, CompareCountriesRequest, Contract, LatestAvailableKpiRequest,
    ListKpisRequest, SemanticKpiTools,
)
from biflow.utils.countries import is_country, normalize_iso3
from biflow.utils.io import sha256_file

SCHEMA_VERSION = "1.0"
DEFAULT_KPIS = tuple(CONTRACTS)
PERCENT_UNIT = "percent"
PERCENTAGE_POINTS = "percentage_points"
RANKING_RULE = "latest_common_catalog_year"

SEVERITY_ORDER = {"review": 0, "warning": 1, "info": 2}

ISSUE_MESSAGES = {
    "raw_source_unavailable": (
        "La source brute enregistrée dans la lineage est inaccessible : aucune "
        "vérification d'empreinte n'a pu être effectuée."
    ),
    "raw_source_hash_mismatch": (
        "L'empreinte de la source brute diffère de celle enregistrée dans la lineage."
    ),
    "source_metadata_missing": "La lineage ne décrit pas la source utilisée par ce KPI.",
    "source_version_incomplete": (
        "La lineage ne fournit pas le chemin et l'empreinte complets de la source."
    ),
    "lineage_run_id_missing": "La lineage n'identifie pas de run.",
    "lineage_warehouse_path_missing": "La lineage n'enregistre pas le chemin du warehouse.",
    "lineage_warehouse_path_mismatch": (
        "Le chemin du warehouse enregistré diffère du warehouse interrogé "
        "(artefact déplacé ou reconstruit)."
    ),
    "lineage_warehouse_path_invalid": "Le chemin du warehouse enregistré est invalide.",
    "warehouse_content_binding_unverified": (
        "La lineage ne contient pas d'empreinte du warehouse : le lien de contenu "
        "n'est pas vérifié."
    ),
    "warehouse_hash_mismatch": "L'empreinte du warehouse diffère de celle enregistrée.",
    "quality_provenance_mismatch": "Le rapport qualité ne correspond pas au run de lineage.",
    "quality_provenance_unverified": "Le rapport qualité n'est pas rattaché au run de lineage.",
    "quality_gate_failed": "Le gate qualité est en échec.",
    "quality_gate_unknown": "Le statut du gate qualité est inconnu.",
    "quality_diagnostics_invalid": "Les diagnostics du rapport qualité sont invalides.",
    "quality_issues_invalid": "La liste d'anomalies du rapport qualité est invalide.",
    "quality_series_identity_inconsistent": (
        "Une série FAS du rapport qualité est incohérente."
    ),
    "quality_indicator_mapping_unresolved": (
        "Un indicateur du rapport qualité n'a pas de correspondance catalogue."
    ),
    "quality_diagnostic_identity_incomplete": (
        "Un diagnostic qualité est dépourvu d'identité pays/année/indicateur."
    ),
}


def evidence_id(kpi_id: str, iso3: str, year: int | None) -> str:
    return f"EV-{kpi_id}-{iso3}-{year if year is not None else 'NA'}"


def trend_id(kpi_id: str, iso3: str, from_year: int | None, to_year: int | None) -> str:
    left = from_year if from_year is not None else "NA"
    right = to_year if to_year is not None else "NA"
    return f"TR-{kpi_id}-{iso3}-{left}-{right}"


def comparison_id(kpi_id: str, iso3: str, reference_iso3: str, year: int | None) -> str:
    return f"CMP-{kpi_id}-{iso3}-vs-{reference_iso3}-{year if year is not None else 'NA'}"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


class AnalysisRequest(Contract):
    """Validated scope for one deterministic analysis run."""

    action: Literal["analyze"] = "analyze"
    iso3: tuple[StrictStr, ...]
    kpi_ids: tuple[StrictStr, ...] = DEFAULT_KPIS
    mode: Literal["latest", "year"] = "latest"
    year: StrictInt | None = None
    reference_iso3: StrictStr | None = None
    include_series: StrictBool = True
    series_iso3: tuple[StrictStr, ...] | None = Field(default=None, exclude=True)
    include_trends: StrictBool = Field(default=True, exclude=True)
    include_rankings: StrictBool = Field(default=True, exclude=True)
    include_comparisons: StrictBool = Field(default=True, exclude=True)
    trend_years: tuple[StrictInt, ...] | None = None
    top_n: StrictInt = Field(default=10, ge=1, le=100)

    @field_validator("iso3")
    @classmethod
    def _countries(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        codes: list[str] = []
        for item in value:
            code = normalize_iso3(item)
            if not code or not is_country(code):
                raise ValueError(f"unsupported country or aggregate: {item}")
            if code not in codes:
                codes.append(code)
        if not codes:
            raise ValueError("at least one country is required")
        return tuple(codes)

    @field_validator("kpi_ids")
    @classmethod
    def _kpis(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        unknown = [item for item in value if item not in CONTRACTS]
        if unknown:
            raise ValueError("unknown KPI: " + ", ".join(unknown))
        kpis = tuple(dict.fromkeys(value))
        if not kpis:
            raise ValueError("at least one KPI is required")
        return kpis

    @field_validator("reference_iso3")
    @classmethod
    def _reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        code = normalize_iso3(value)
        if not code or not is_country(code):
            raise ValueError("reference_iso3 must identify a country")
        return code

    @field_validator("series_iso3")
    @classmethod
    def _series_countries(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        codes: list[str] = []
        for item in value:
            code = normalize_iso3(item)
            if not code or not is_country(code):
                raise ValueError(f"unsupported country or aggregate: {item}")
            if code not in codes:
                codes.append(code)
        if not codes:
            raise ValueError("series_iso3 cannot be empty")
        return tuple(codes)

    @field_validator("trend_years")
    @classmethod
    def _trend_years(cls, value: tuple[int, ...] | None) -> tuple[int, ...] | None:
        if value is None:
            return None
        if not value:
            raise ValueError("trend_years cannot be empty")
        if any(type(year) is not int or not 1 <= year <= 9999 for year in value):
            raise ValueError("trend_years must contain valid years")
        if len(set(value)) != len(value):
            raise ValueError("trend_years contains duplicates")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def _consistent(self) -> "AnalysisRequest":
        if self.mode == "year":
            if self.year is None:
                raise ValueError("year is required when mode='year'")
            if not 1 <= self.year <= 9999:
                raise ValueError("year must be between 1 and 9999")
        elif self.year is not None:
            raise ValueError("year must be omitted when mode='latest'")
        if self.reference_iso3 is not None and self.reference_iso3 not in self.iso3:
            raise ValueError("reference_iso3 must be part of iso3")
        if self.series_iso3 is not None and not set(self.series_iso3) <= set(self.iso3):
            raise ValueError("series_iso3 must be part of iso3")
        return self


# Ordre conservateur : un tableau n'est jamais "approuve" si une ligne ne l'est pas
PUBLICATION_ORDER = ("blocked", "not_evaluated", "approved_with_review_note", "approved")


def audited_publication_statuses(warehouse_path) -> dict[tuple[str, str, int], str]:
    """Statuts de kpi_values fixes par l'Auditor ; vide s'il n'y a pas d'audit."""
    path = Path(warehouse_path)
    if not path.is_file():
        return {}
    try:
        with duckdb.connect(str(path), read_only=True) as con:
            rows = con.execute("SELECT kpi_id, iso3, year, publication_status FROM kpi_values "
                               "WHERE publication_status <> 'not_evaluated'").fetchall()
    except duckdb.Error:  # pas de table kpi_values ou ancienne table sans statut
        return {}
    return {(kpi_id, iso3, int(year)): status for kpi_id, iso3, year, status in rows}


def aggregate_publication_status(statuses) -> str:
    """Statut d'un ensemble : le plus restrictif ; not_evaluated sans audit."""
    found = set(statuses)
    return next((status for status in PUBLICATION_ORDER if status in found), "not_evaluated")


def findex_survey_years(dataset: dict[str, Any], iso3: str) -> list[int]:
    """Vagues Findex observees pour un pays : annees ou un KPI Findex a une valeur."""
    findex = {row["kpi_id"] for row in dataset.get("observations") or []
              if row.get("source") == "findex"}
    return sorted({
        int(point["year"])
        for row in dataset.get("series") or []
        if row.get("iso3") == iso3 and row.get("kpi_id") in findex
        for point in row.get("points") or []
        if point.get("availability_status") == "available" and point.get("value") is not None
    })


def findex_wave(survey_years: list[int], year: int) -> int | None:
    """Derniere vague au plus tard a l'annee demandee ; jamais une vague posterieure."""
    earlier = [wave for wave in survey_years if wave <= year]
    return max(earlier) if earlier else None


def build_with_findex_wave(service: "AnalysisService",
                           request: "AnalysisRequest | dict[str, Any]") -> dict[str, Any]:
    """Dataset en mode annee : les KPI Findex sont lus a la derniere vague au plus tard
    a l'annee demandee (pays principal), les autres KPI (FAS) a l'annee demandee.

    ``scope.findex_wave`` = {year_requested, year_used, survey_years} ; year_used vaut
    None sans vague anterieure (les KPI Findex restent alors indisponibles)."""
    request = AnalysisRequest.model_validate(request)
    dataset = service.build(request)
    if request.mode != "year":
        return dataset
    years = findex_survey_years(dataset, request.iso3[0])
    wave = findex_wave(years, request.year)
    dataset["scope"]["findex_wave"] = {
        "year_requested": request.year, "year_used": wave, "survey_years": years,
    }
    if wave is None or wave == request.year:
        return dataset
    at_wave = service.build(request.model_copy(update={"year": wave}))
    findex = {row["kpi_id"] for row in at_wave["observations"] if row.get("source") == "findex"}
    wave_rows = {(row["iso3"], row["kpi_id"]): row for row in at_wave["observations"]}
    dataset["observations"] = [
        wave_rows.get((row["iso3"], row["kpi_id"]), row) if row["kpi_id"] in findex else row
        for row in dataset["observations"]
    ]
    for key in ("coverage", "rankings"):
        wave_items = {item.get("kpi_id"): item for item in at_wave.get(key) or []}
        dataset[key] = [
            wave_items.get(item.get("kpi_id"), item) if item.get("kpi_id") in findex else item
            for item in dataset.get(key) or []
        ]
    seen = {(notice.get("code"), notice.get("message")) for notice in dataset["notices"]}
    dataset["notices"] += [notice for notice in at_wave.get("notices") or []
                           if (notice.get("code"), notice.get("message")) not in seen]
    dataset["publication_status"] = aggregate_publication_status(
        row["publication_status"] for row in dataset["observations"])
    return dataset


class AnalysisService:
    """Read-only analysis dataset; semantic contracts remain the only data path.

    A single instance memoizes explicit-year and latest lookups, so series,
    rankings, trends and comparisons reuse the same KPI results. Provenance and
    review flags are copied from each result and never upgraded.
    """

    def __init__(
        self,
        warehouse_path: str | Path,
        catalog_path: str | Path = DEFAULT_CATALOG,
        *,
        lineage_path: str | Path | None = None,
        quality_report_path: str | Path | None = None,
        tools: SemanticKpiTools | None = None,
    ) -> None:
        self.warehouse_path = resolve(warehouse_path)
        self.tools = tools or SemanticKpiTools(
            self.warehouse_path, catalog_path,
            lineage_path=lineage_path, quality_report_path=quality_report_path,
        )
        self.lineage_path = (
            resolve(lineage_path) if lineage_path is not None
            else Path(self.warehouse_path).with_name("lineage.json")
        )
        self.quality_report_path = (
            resolve(quality_report_path) if quality_report_path is not None
            else Path(self.warehouse_path).parent.parent / "quality" / "quality_report.json"
        )
        listing = self.tools.list_kpis(ListKpisRequest())
        self._meta = {item.kpi_id: item for item in listing.kpis}
        self._catalog = {
            "version": listing.catalog_version,
            "sha256": listing.catalog_sha256,
        }
        # Statut de publication fixe par l'Auditor (kpi_values), si un audit existe
        self._published = audited_publication_statuses(self.warehouse_path)
        self._observations: dict[tuple[str, int, str], KpiResult] = {}
        self._latest: dict[tuple[str, str], Any] = {}
        self._countries: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------ KPI cache
    def _valid_years(self, kpi_id: str) -> tuple[int, ...]:
        return tuple(self._meta[kpi_id].valid_years)

    def _calculate(self, kpi_id: str, iso3: str, year: int) -> KpiResult:
        key = (iso3, year, kpi_id)
        if key not in self._observations:
            self._observations[key] = self.tools.calculate_kpi(
                CalculateKpiRequest(kpi_id=kpi_id, iso3=iso3, year=year)
            ).result
        return self._observations[key]

    def _latest_for(self, iso3: str, kpi_id: str) -> Any:
        key = (iso3, kpi_id)
        if key not in self._latest:
            self._latest[key] = self.tools.latest_available(
                LatestAvailableKpiRequest(kpi_id=kpi_id, iso3=iso3)
            )
        return self._latest[key]

    @staticmethod
    def _is_available(result: KpiResult) -> bool:
        return result.availability_status == "available" and result.value is not None

    # ---------------------------------------------------------------------- build
    def build(self, request: AnalysisRequest | dict[str, Any]) -> dict[str, Any]:
        request = AnalysisRequest.model_validate(request)
        rows, selected, skips = self._observations_for(request)
        series = self._series_for(request)
        trends = self._trends_for(request) if request.include_trends else []
        rankings = self._rankings_for(request) if request.include_rankings else []
        comparisons = (
            self._comparisons_for(request, rankings)
            if request.include_comparisons and rankings else []
        )
        coverage = self._coverage(request, rows)
        notices = self._notices(request, rows, selected, skips, rankings)
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "request": request.model_dump(mode="json"),
            "catalog": dict(self._catalog),
            "scope": {
                "countries": [self._country_meta(code) for code in request.iso3],
                "kpis": [self._kpi_meta(kpi_id) for kpi_id in request.kpi_ids],
                "mode": request.mode,
                "year": request.year,
                "reference_iso3": request.reference_iso3 or request.iso3[0],
                "ranking_rule": RANKING_RULE,
            },
            "observations": rows,
            "series": series,
            "trends": trends,
            "rankings": rankings,
            "comparisons": comparisons,
            "coverage": coverage,
            "notices": notices,
            "provenance": self._provenance(selected),
            "publication_status": aggregate_publication_status(row["publication_status"] for row in rows),
        }

    # ------------------------------------------------------------------ metadata
    def _kpi_meta(self, kpi_id: str) -> dict[str, Any]:
        summary = self._meta[kpi_id]
        return {
            "kpi_id": kpi_id,
            "name": summary.name,
            "unit": summary.unit,
            "subgroup": summary.subgroup,
            "verification_status": summary.verification_status,
            "valid_years": list(summary.valid_years),
            "dependencies": list(summary.dependencies),
        }

    def _country_meta(self, iso3: str) -> dict[str, Any]:
        if iso3 in self._countries:
            return self._countries[iso3]

        def default() -> dict[str, Any]:
            return {"iso3": iso3, "name": iso3, "region": None, "income_group": None}

        meta = default()
        try:
            with duckdb.connect(str(self.warehouse_path), read_only=True) as con:
                rows = con.execute(
                    "SELECT country, region, income_group FROM country_dim WHERE iso3 = ?",
                    [iso3],
                ).fetchmany(2)
            if len(rows) == 1:
                name, region, income_group = rows[0]
                meta = {
                    "iso3": iso3,
                    "name": name or iso3,
                    "region": region,
                    "income_group": income_group,
                }
        except duckdb.Error:
            meta = default()
        self._countries[iso3] = meta
        return meta

    # -------------------------------------------------------------- observations
    def _observations_for(
        self, request: AnalysisRequest
    ) -> tuple[list[dict[str, Any]], list[KpiResult | None], list[dict[str, Any]]]:
        rows: list[dict[str, Any]] = []
        selected: list[KpiResult | None] = []
        skips: list[dict[str, Any]] = []
        for iso3 in request.iso3:
            for kpi_id in request.kpi_ids:
                if request.mode == "year":
                    result = self._calculate(kpi_id, iso3, request.year)
                    selection = (
                        "explicit_year" if request.year in self._valid_years(kpi_id)
                        else "out_of_catalog_year"
                    )
                    rows.append(self._observation(result, selection))
                    selected.append(result)
                    continue
                response = self._latest_for(iso3, kpi_id)
                for skipped in response.skipped_observations:
                    skips.append({
                        "kpi_id": kpi_id,
                        "iso3": iso3,
                        "year": skipped.observation_year,
                        "reason": skipped.reason,
                    })
                if response.result is not None:
                    rows.append(self._observation(response.result, "latest_available"))
                    selected.append(response.result)
                else:
                    fallback = response.skipped_observations[0]
                    rows.append(self._unavailable_observation(
                        kpi_id, iso3, fallback, response.reason
                    ))
                    selected.append(None)
        return rows, selected, skips

    def _observation(self, result: KpiResult, selection: str) -> dict[str, Any]:
        return {
            "kpi_id": result.kpi_id,
            "iso3": result.iso3,
            "year": result.observation_year,
            "selection": selection,
            "value": result.value,
            "unit": result.unit,
            "availability_status": result.availability_status,
            "reason": result.reason,
            "definition_status": result.verification_status,
            "requires_review": result.requires_review,
            "review_reasons": list(result.review_reasons),
            "evidence_id": evidence_id(result.kpi_id, result.iso3, result.observation_year),
            "source": result.source,
            "source_indicator": result.source_indicator,
            "indicator_code": result.indicator_code,
            "input_value": result.input_value,
            "input_unit": result.input_unit,
            "definition_version": result.definition_version,
            "formula": result.formula,
            "subgroup": result.subgroup,
            "dependencies": list(result.dependencies),
            "publication_status": self._published.get(
                (result.kpi_id, result.iso3, result.observation_year), result.publication_status),
            "provenance_issues": list(result.provenance.issues) if result.provenance else [],
            "quality_warning_codes": sorted({item.code for item in result.quality_warnings}),
            "source_warning_codes": sorted({item.code for item in result.source_warnings}),
        }

    def _unavailable_observation(
        self, kpi_id: str, iso3: str, fallback: KpiResult, reason: str | None
    ) -> dict[str, Any]:
        review = list(dict.fromkeys(fallback.review_reasons))
        return {
            "kpi_id": kpi_id,
            "iso3": iso3,
            "year": None,
            "selection": "unavailable",
            "value": None,
            "unit": self._meta[kpi_id].unit,
            "availability_status": "unavailable",
            "reason": reason or fallback.reason or "no_available_observation",
            "definition_status": fallback.verification_status,
            "requires_review": bool(review),
            "review_reasons": review,
            "evidence_id": evidence_id(kpi_id, iso3, None),
            "source": fallback.source,
            "source_indicator": fallback.source_indicator,
            "indicator_code": fallback.indicator_code,
            "input_value": None,
            "input_unit": None,
            "definition_version": fallback.definition_version,
            "formula": fallback.formula,
            "subgroup": fallback.subgroup,
            "dependencies": list(fallback.dependencies),
            "publication_status": fallback.publication_status,
            "provenance_issues": list(fallback.provenance.issues) if fallback.provenance else [],
            "quality_warning_codes": sorted({item.code for item in fallback.quality_warnings}),
            "source_warning_codes": sorted({item.code for item in fallback.source_warnings}),
        }

    # -------------------------------------------------------------------- series
    def _series_for(self, request: AnalysisRequest) -> list[dict[str, Any]]:
        if not request.include_series:
            return []
        series: list[dict[str, Any]] = []
        for iso3 in request.series_iso3 or request.iso3:
            for kpi_id in request.kpi_ids:
                years = request.trend_years or self._valid_years(kpi_id)
                points = []
                for year in years:
                    result = self._calculate(kpi_id, iso3, year)
                    points.append({
                        "year": year,
                        "value": result.value,
                        "availability_status": result.availability_status,
                        "reason": result.reason,
                        "requires_review": result.requires_review,
                        "evidence_id": evidence_id(kpi_id, iso3, year),
                    })
                series.append({
                    "kpi_id": kpi_id,
                    "iso3": iso3,
                    "unit": self._meta[kpi_id].unit,
                    "points": points,
                })
        return series

    # -------------------------------------------------------------------- trends
    def _trends_for(self, request: AnalysisRequest) -> list[dict[str, Any]]:
        trends: list[dict[str, Any]] = []
        for iso3 in request.iso3:
            for kpi_id in request.kpi_ids:
                years = request.trend_years or self._valid_years(kpi_id)
                available = []
                for year in years:
                    result = self._calculate(kpi_id, iso3, year)
                    if self._is_available(result):
                        available.append((year, result))
                unit = self._meta[kpi_id].unit
                excluded = [
                    year for year in years if year not in {item[0] for item in available}
                ]
                if len(available) >= 2:
                    from_year, first = available[0]
                    to_year, last = available[-1]
                    trends.append({
                        "trend_id": trend_id(kpi_id, iso3, from_year, to_year),
                        "kpi_id": kpi_id,
                        "iso3": iso3,
                        "from_year": from_year,
                        "to_year": to_year,
                        "difference": last.value - first.value,
                        "unit": PERCENTAGE_POINTS if unit == PERCENT_UNIT else unit,
                        "status": "complete",
                        "requires_review": first.requires_review or last.requires_review,
                        "evidence_ids": [
                            evidence_id(kpi_id, iso3, from_year),
                            evidence_id(kpi_id, iso3, to_year),
                        ],
                        "excluded_years": excluded,
                        "method": "first_and_last_available_catalog_observation",
                    })
                    continue
                from_year = available[0][0] if available else None
                to_year = available[-1][0] if available else None
                trends.append({
                    "trend_id": trend_id(kpi_id, iso3, from_year, to_year),
                    "kpi_id": kpi_id,
                    "iso3": iso3,
                    "from_year": from_year,
                    "to_year": to_year,
                    "difference": None,
                    "unit": PERCENTAGE_POINTS if unit == PERCENT_UNIT else unit,
                    "status": "insufficient_observations",
                    "requires_review": False,
                    "evidence_ids": [
                        evidence_id(kpi_id, iso3, from_year)
                        if from_year is not None else evidence_id(kpi_id, iso3, None)
                    ],
                    "excluded_years": excluded,
                    "method": "first_and_last_available_catalog_observation",
                })
        return trends

    # ------------------------------------------------------------------ rankings
    def _ranking_year(self, request: AnalysisRequest, kpi_id: str) -> tuple[int | None, str]:
        if request.mode == "year":
            status = (
                "complete" if request.year in self._valid_years(kpi_id)
                else "out_of_catalog_year"
            )
            return request.year, status
        available_years: list[set[int]] = []
        for iso3 in request.iso3:
            years = {
                year for year in self._valid_years(kpi_id)
                if self._is_available(self._calculate(kpi_id, iso3, year))
            }
            available_years.append(years)
        common = set.intersection(*available_years) if available_years else set()
        if not common:
            return None, "no_common_year"
        return max(common), "complete"

    def _rankings_for(self, request: AnalysisRequest) -> list[dict[str, Any]]:
        rankings: list[dict[str, Any]] = []
        for kpi_id in request.kpi_ids:
            year, status = self._ranking_year(request, kpi_id)
            rows: list[dict[str, Any]] = []
            for iso3 in request.iso3:
                if year is None:
                    rows.append({
                        "iso3": iso3,
                        "rank": None,
                        "value": None,
                        "unit": self._meta[kpi_id].unit,
                        "availability_status": "unavailable",
                        "reason": status,
                        "requires_review": False,
                        "review_reasons": [],
                        "evidence_id": evidence_id(kpi_id, iso3, None),
                    })
                    continue
                result = self._calculate(kpi_id, iso3, year)
                rows.append({
                    "iso3": iso3,
                    "rank": None,
                    "value": result.value,
                    "unit": result.unit,
                    "availability_status": result.availability_status,
                    "reason": result.reason,
                    "requires_review": result.requires_review,
                    "review_reasons": list(result.review_reasons),
                    "evidence_id": evidence_id(kpi_id, iso3, year),
                })
            ranked = sorted(
                (row for row in rows if row["value"] is not None),
                key=lambda row: (-row["value"], row["iso3"]),
            )
            for position, row in enumerate(ranked, 1):
                row["rank"] = position
            rankings.append({
                "kpi_id": kpi_id,
                "year": year,
                "status": status,
                "rule": RANKING_RULE,
                "rows": ranked + [row for row in rows if row["value"] is None],
            })
        return rankings

    # --------------------------------------------------------------- comparisons
    def _comparisons_for(
        self, request: AnalysisRequest, rankings: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        reference = request.reference_iso3 or request.iso3[0]
        others = [iso3 for iso3 in request.iso3 if iso3 != reference]
        years = {item["kpi_id"]: item["year"] for item in rankings}
        comparisons: list[dict[str, Any]] = []
        for kpi_id in request.kpi_ids:
            year = years[kpi_id]
            block = {
                "comparison_id": comparison_id(kpi_id, reference, reference, year),
                "kpi_id": kpi_id,
                "reference_iso3": reference,
                "year": year,
                "difference_formula": "right.value - left.value",
                "rows": [],
            }
            if not others:
                comparisons.append({**block, "status": "single_country"})
                continue
            if year is None:
                comparisons.append({**block, "status": "no_comparable_year"})
                continue
            rows = []
            for iso3 in others:
                response = self.tools.compare_countries(CompareCountriesRequest(
                    kpi_id=kpi_id, left_iso3=reference, right_iso3=iso3, year=year,
                ))
                rows.append({
                    "iso3": iso3,
                    "value": response.right.value,
                    "reference_value": response.left.value,
                    "difference": response.difference,
                    "unit": response.difference_unit,
                    "comparison_status": response.comparison_status,
                    "reason": response.reason,
                    "requires_review": response.requires_review,
                    "review_reasons": list(response.review_reasons),
                    "evidence_id": comparison_id(kpi_id, iso3, reference, year),
                })
            status = (
                "complete"
                if all(row["comparison_status"] == "complete" for row in rows)
                else "incomplete"
            )
            comparisons.append({**block, "status": status, "rows": rows})
        return comparisons

    # ------------------------------------------------------------------ coverage
    def _coverage(
        self, request: AnalysisRequest, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        coverage = []
        for kpi_id in request.kpi_ids:
            selected = [row for row in rows if row["kpi_id"] == kpi_id]
            available = sum(1 for row in selected if row["value"] is not None)
            coverage.append({
                "kpi_id": kpi_id,
                "selected_observations": len(selected),
                "available": available,
                "unavailable": len(selected) - available,
                "requires_review": sum(
                    1 for row in selected if row["requires_review"]
                ),
                "mode": request.mode,
                "year": request.year,
            })
        return coverage

    # ------------------------------------------------------------------- notices
    def _notices(
        self,
        request: AnalysisRequest,
        rows: list[dict[str, Any]],
        selected: list[KpiResult | None],
        skips: list[dict[str, Any]],
        rankings: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        notices: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        def add(code: str, severity: str, message: str, **extra: Any) -> None:
            key = (code, message)
            if key in seen:
                return
            seen.add(key)
            notices.append({"code": code, "severity": severity, "message": message, **extra})

        issues = {
            issue for row in rows for issue in row["provenance_issues"]
        }
        for result in selected:
            if result is not None and result.provenance is not None:
                issues.update(result.provenance.issues)
        for issue in sorted(issues):
            add(issue, "review", ISSUE_MESSAGES.get(issue, issue))

        for kpi_id in request.kpi_ids:
            if self._meta[kpi_id].verification_status == "provisional":
                add(
                    "provisional_definition", "review",
                    f"{self._meta[kpi_id].name} repose sur une définition provisoire.",
                    kpi_id=kpi_id,
                )

        review_rows = [row for row in rows if row["requires_review"]]
        if review_rows:
            reasons = sorted({
                reason for row in review_rows for reason in row["review_reasons"]
            })
            add(
                "observation_requires_review", "review",
                f"{len(review_rows)} observation(s) sélectionnée(s) exigent une revue "
                f"({', '.join(reasons[:5])}{'…' if len(reasons) > 5 else ''}).",
                observations=len(review_rows),
                reasons=reasons,
            )

        matched: dict[tuple[str, str], str] = {}
        for result in selected:
            if result is None:
                continue
            for warning in result.quality_warnings:
                matched.setdefault((warning.reference, warning.code), warning.message)
        for (reference, code), message in sorted(matched.items())[:20]:
            add(f"quality_warning:{code}", "review", message, reference=reference)

        source_wide: dict[tuple[str, str], str] = {}
        for result in selected:
            if result is None:
                continue
            for warning in result.source_warnings:
                source_wide.setdefault((warning.reference, warning.code), warning.message)
        for (reference, code), message in sorted(source_wide.items())[:20]:
            add(f"source_notice:{code}", "warning", message, reference=reference)

        if request.mode == "latest":
            for kpi_id in request.kpi_ids:
                years = sorted({
                    row["year"] for row in rows
                    if row["kpi_id"] == kpi_id and row["year"] is not None
                })
                if len(years) > 1:
                    add(
                        "latest_years_differ", "warning",
                        f"{self._meta[kpi_id].name} : les pays n'ont pas tous la même "
                        f"année la plus récente ({', '.join(str(year) for year in years)}).",
                        kpi_id=kpi_id, years=years,
                    )
            if skips:
                add(
                    "skipped_observations", "info",
                    f"{len(skips)} observation(s) plus récente(s) ignorée(s) faute de "
                    "valeur disponible.",
                    skipped=skips[:20],
                )

        for ranking in rankings:
            if ranking["status"] == "complete":
                continue
            add(
                f"ranking_{ranking['status']}", "warning",
                f"Classement indisponible pour {self._meta[ranking['kpi_id']].name} : "
                "aucune année commune exploitable.",
                kpi_id=ranking["kpi_id"],
            )

        notices.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item["code"]))
        return notices

    # ---------------------------------------------------------------- provenance
    def _provenance(self, selected: list[KpiResult | None]) -> dict[str, Any]:
        representative = next(
            (result for result in selected
             if result is not None and result.provenance is not None),
            None,
        )
        provenance = representative.provenance if representative is not None else None
        lineage = _load_json(self.lineage_path)
        quality = _load_json(self.quality_report_path)

        warehouse_hash = (
            provenance.warehouse_sha256 if provenance is not None
            else sha256_file(self.warehouse_path)
        )
        outputs = lineage.get("outputs") if isinstance(lineage.get("outputs"), dict) else {}
        warehouse_output = outputs.get("warehouse")
        recorded_path = None
        if isinstance(warehouse_output, str):
            recorded_path = _text(warehouse_output)
        elif isinstance(warehouse_output, dict):
            recorded_path = _text(warehouse_output.get("path"))
        recorded_hash = _text(outputs.get("warehouse_sha256"))
        if recorded_hash is None and isinstance(warehouse_output, dict):
            recorded_hash = _text(warehouse_output.get("sha256"))
        if recorded_hash is None:
            content_binding = "not_recorded"
        elif recorded_hash.lower() == warehouse_hash:
            content_binding = "recorded_and_verified"
        else:
            content_binding = "recorded_mismatch"

        sources = []
        inputs = lineage.get("inputs") if isinstance(lineage.get("inputs"), dict) else {}
        for name, meta in inputs.items():
            if not isinstance(meta, dict):
                continue
            raw_path = _text(meta.get("path"))
            observed = None
            if raw_path is not None:
                try:
                    observed = sha256_file(resolve(raw_path))
                except (OSError, ValueError):
                    observed = None
            recorded = _text(meta.get("sha256"))
            matched = None if observed is None or recorded is None else observed == recorded
            sources.append({
                "source": name,
                "path": raw_path,
                "sha256": recorded,
                "rows": meta.get("rows"),
                "observed_sha256": observed,
                "hash_match": matched,
            })

        passed = quality.get("passed")
        passed = passed if type(passed) is bool else None
        score = quality.get("overall_score")
        score = score if isinstance(score, (int, float)) and not isinstance(score, bool) else None

        issues = set(provenance.issues) if provenance is not None else set()
        return {
            "warehouse_path": str(self.warehouse_path),
            "warehouse_sha256": warehouse_hash,
            "warehouse_size_bytes": self.warehouse_path.stat().st_size,
            "lineage_path": str(self.lineage_path),
            "lineage_sha256": (
                sha256_file(self.lineage_path) if self.lineage_path.is_file() else None
            ),
            "lineage_run_id": _text(lineage.get("run_id")),
            "lineage_created_at": _text(lineage.get("created_at")),
            "quality_report_path": str(self.quality_report_path),
            "quality_report_sha256": (
                sha256_file(self.quality_report_path)
                if self.quality_report_path.is_file() else None
            ),
            "quality_gate_passed": passed,
            "quality_score": score,
            "quality_association_status": (
                provenance.quality_association_status if provenance is not None
                else "unverified"
            ),
            "content_binding": content_binding,
            "recorded_warehouse_path": recorded_path,
            "recorded_warehouse_sha256": recorded_hash,
            "sources": sources,
            "issues": sorted(issues),
        }


__all__ = [
    "AnalysisRequest",
    "AnalysisService",
    "DEFAULT_KPIS",
    "PERCENTAGE_POINTS",
    "RANKING_RULE",
    "SCHEMA_VERSION",
    "build_with_findex_wave",
    "comparison_id",
    "evidence_id",
    "findex_survey_years",
    "findex_wave",
    "trend_id",
]
