"""Deterministic, read-only single-country KPI lookups (no publication approval).

Example: KpiCalculator(path).calculate("TUN", 2024, "account_ownership").
Only the six supported catalog contracts below can execute; YAML is never SQL.
Saving and borrowing calculations retain their provisional definitions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import re
from typing import Any

import duckdb
import yaml

from biflow.config import resolve
from biflow.utils.countries import is_country, normalize_iso3
from biflow.tools.kpi_provenance import KpiProvenance, QualityWarning, evidence


DEFAULT_CATALOG = "config/kpi_catalog.v1.yaml"
# source, fact indicator, input unit, dimension, dimension value, subgroup,
# output unit, formula, verification status
CONTRACTS = {
    "account_ownership": ("findex", "account_t_d", "fraction", "all", "all",
                          "total_population", "percent", "100 * value", "verified"),
    "branch_density": ("fas", "branch_density", "per_100k_adults", "bank_type",
                       "commercial_banks", "commercial_banks_all_adults",
                       "per_100k_adults", "value", "verified_metadata"),
    "digital_payment_rate": ("findex", "g20_any", "fraction", "all", "all",
                             "total_population", "percent", "100 * value", "verified"),
    "saving_rate": ("findex", "save_any_t_d", "fraction", "all", "all",
                    "total_population", "percent", "100 * value", "provisional"),
    "borrowing_rate": ("findex", "borrow_any_t_d", "fraction", "all", "all",
                       "total_population", "percent", "100 * value", "provisional"),
    "unbanked_share": ("findex", "account_t_d", "fraction", "all", "all",
                       "total_population", "percent", "100 * (1 - value)", "derived_verified"),
}


class CatalogError(ValueError):
    """Catalog is malformed or incompatible with the supported calculations."""


def _validate_catalog(catalog: Any) -> None:
    try:
        if (type(catalog["schema_version"]) is not int or catalog["schema_version"] != 1
                or not re.fullmatch(r"\d+\.\d+\.\d+", catalog["catalog_version"])
                or catalog["catalog_id"] != "biflow_core_kpis"):
            raise CatalogError("Unsupported catalog identity or version")
        kpis = catalog["kpis"]
        if not isinstance(kpis, dict) or not CONTRACTS.keys() <= kpis.keys():
            raise CatalogError("Catalog lacks supported KPIs")
        for kpi_id, kpi in kpis.items():
            if not re.fullmatch(r"\d+\.\d+\.\d+", kpi["definition_version"]):
                raise CatalogError(f"Invalid definition version: {kpi_id}")
            for field in ("name", "business_objective", "definition", "subgroup", "unit"):
                if not isinstance(kpi[field], str) or not kpi[field].strip():
                    raise CatalogError(f"Missing {field}: {kpi_id}")
            years = kpi["valid_years"]
            if (not isinstance(years, list) or not years
                    or any(type(y) is not int or not 1 <= y <= 9999 for y in years)
                    or years != sorted(set(years))):
                raise CatalogError(f"Invalid valid_years: {kpi_id}")
            for policy in ("missing_data_policy", "aggregation_policy",
                           "traceability_policy", "publication_review_policy"):
                if kpi[policy] != catalog[policy]["id"]:
                    raise CatalogError(f"Unknown policy: {kpi_id}/{policy}")
            if (not kpi["verification"]["evidence"] or any(
                    ref not in catalog["references"] for ref in kpi["verification"]["evidence"])
                    or any(dep not in kpis or dep == kpi_id for dep in kpi["dependencies"])):
                raise CatalogError(f"Invalid references: {kpi_id}")
        for kpi_id, expected in CONTRACTS.items():
            k = kpis[kpi_id]
            w = k["warehouse"]
            actual = (w["source"], w["indicator_code"], w["input_unit"], w["dimension"],
                      w["dimension_value"], k["subgroup"], k["unit"],
                      k["formula"]["from_fact"], k["verification"]["status"])
            if (actual != expected or w["fact_table"] != "fact"
                    or k["source"]["dataset"] != w["source"]
                    or k["dependencies"] != (["account_ownership"] if kpi_id == "unbanked_share" else [])
                    or k["source"]["indicator"] != (
                        "FA26N.PHTADLT_NUM" if kpi_id == "branch_density" else w["indicator_code"])):
                raise CatalogError(f"Unsupported calculation contract: {kpi_id}")
        # A complement must describe exactly the same observation/population.
        for field in ("warehouse", "valid_years", "denominator", "subgroup"):
            if kpis["unbanked_share"][field] != kpis["account_ownership"][field]:
                raise CatalogError(f"Incompatible unbanked dependency: {field}")
        policy = catalog["missing_data_policy"]
        if (any(policy[key] is not False for key in
                ("zero_fill", "interpolate", "forward_fill", "substitute_other_indicator"))
                or policy["zero_is_observed_value"] is not True):
            raise CatalogError("Unsupported missing-data policy")
    except (KeyError, TypeError, AttributeError) as exc:
        raise CatalogError("Malformed KPI catalog") from exc


def load_catalog(path: str | Path = DEFAULT_CATALOG) -> dict[str, Any]:
    """Load local YAML and validate its structure and executable contracts."""
    try:
        catalog = yaml.safe_load(resolve(path).read_bytes())
    except yaml.YAMLError as exc:
        raise CatalogError("Invalid catalog YAML") from exc
    _validate_catalog(catalog)
    return catalog


@dataclass(frozen=True)
class KpiResult:
    kpi_id: str
    iso3: str
    observation_year: int
    value: float | None
    unit: str
    source: str
    source_indicator: str
    definition: str
    availability_status: str
    reason: str | None
    subgroup: str
    input_value: float | None
    input_unit: str | None
    catalog_version: str
    catalog_sha256: str
    definition_version: str
    verification_status: str
    warehouse_path: str
    # Availability does not certify lineage, diagnostics review or publication.
    publication_status: str = "not_evaluated"
    dependencies: tuple[str, ...] = ()
    dependency_results: tuple[KpiResult, ...] = ()
    indicator_code: str = ""
    formula: str = ""
    input_fact_key: tuple[str | int, ...] | None = None
    provenance: KpiProvenance | None = None
    quality_warnings: tuple[QualityWarning, ...] = ()
    source_warnings: tuple[QualityWarning, ...] = ()
    review_reasons: tuple[str, ...] = ()
    requires_review: bool = False


@dataclass(frozen=True)
class LatestKpiResult:
    result: KpiResult | None
    skipped_observations: tuple[KpiResult, ...]


class KpiCalculator:
    """Open an existing DuckDB file read-only for each parameterized lookup.

    Invalid requests raise ValueError; missing observations return unavailable.
    Duplicate facts, inconsistent units/entities and out-of-range values return
    requires_review without a calculated value. Database/schema errors propagate.
    Sidecar evidence is read on each lookup. Metadata issues and matched quality
    warnings set the separate requires_review flag without changing availability
    or values. Defaults: adjacent lineage.json and ../quality/quality_report.json.
    Current ETL/quality metadata cannot prove warehouse/report content binding;
    recorded gate results must not be mistaken for publication certification.
    """

    def __init__(self, warehouse_path: str | Path,
                 catalog_path: str | Path = DEFAULT_CATALOG, *,
                 lineage_path: str | Path | None = None,
                 quality_report_path: str | Path | None = None):
        content = resolve(catalog_path).read_bytes()
        try:
            self._catalog = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise CatalogError("Invalid catalog YAML") from exc
        _validate_catalog(self._catalog)
        self._catalog_sha256 = hashlib.sha256(content).hexdigest()
        self.warehouse_path = resolve(warehouse_path).resolve()
        if not self.warehouse_path.is_file():
            raise FileNotFoundError(self.warehouse_path)
        self.lineage_path = (resolve(lineage_path) if lineage_path is not None
                             else self.warehouse_path.with_name("lineage.json"))
        self.quality_report_path = (resolve(quality_report_path) if quality_report_path is not None
                                    else self.warehouse_path.parent.parent / "quality" / "quality_report.json")

    def calculate_latest(self, iso3: str, kpi_id: str) -> LatestKpiResult:
        """Try catalog years newest first, retaining every skipped result.

        Reuse explicit-year validation and subgroup selection. A numeric result
        with provenance/diagnostic review flags stays eligible; review is never
        waived. Derived inputs are evaluated together by calculate() in one year.
        No result means no valid observation; no artificial year is assigned.
        """
        if not isinstance(kpi_id, str) or kpi_id not in CONTRACTS:
            raise ValueError("Unknown or unsupported KPI; supported: " + ", ".join(CONTRACTS))
        skipped = []
        for year in reversed(self._catalog["kpis"][kpi_id]["valid_years"]):
            result = self.calculate(iso3, year, kpi_id)
            if result.availability_status == "available":
                return LatestKpiResult(result=result, skipped_observations=tuple(skipped))
            skipped.append(result)
            if result.reason in {"country_not_in_warehouse", "invalid_country_dimension"}:
                break
        return LatestKpiResult(result=None, skipped_observations=tuple(skipped))

    def calculate(self, iso3: str, year: int, kpi_id: str) -> KpiResult:
        if not isinstance(kpi_id, str) or kpi_id not in CONTRACTS:
            raise ValueError("Unknown or unsupported KPI; supported: " + ", ".join(CONTRACTS))
        code = normalize_iso3(iso3)
        if not code or not re.fullmatch(r"[A-Z]{3}", code) or not is_country(code):
            raise ValueError("iso3 must identify a country (aggregates are excluded)")
        if type(year) is not int or not 1 <= year <= 9999:
            raise ValueError("year must be an integer between 1 and 9999")
        k = self._catalog["kpis"][kpi_id]
        w = k["warehouse"]

        def result(status, reason=None, value=None, input_value=None, input_unit=None,
                   dependency_results=()):
            if dependency_results:
                dependency = dependency_results[0]
                provenance = dependency.provenance
                warnings, notices = dependency.quality_warnings, dependency.source_warnings
                review = list(dependency.review_reasons)
            else:
                provenance, warnings, notices = evidence(
                    self.warehouse_path, self.lineage_path, self.quality_report_path,
                    source=w["source"], iso3=code, year=year, indicator=w["indicator_code"],
                    dimension=w["dimension"], dimension_value=w["dimension_value"],
                )
                review = list(provenance.issues)
            if k["verification"]["status"] == "provisional":
                review.append("provisional_definition")
            if warnings:
                review.append("unresolved_input_quality_warning")
            if status == "requires_review":
                review.append(reason)
            return KpiResult(
                kpi_id=kpi_id, iso3=code, observation_year=year, value=value,
                unit=k["unit"], source=w["source"], source_indicator=k["source"]["indicator"],
                definition=k["definition"], availability_status=status, reason=reason,
                subgroup=k["subgroup"], input_value=input_value, input_unit=input_unit,
                catalog_version=self._catalog["catalog_version"], catalog_sha256=self._catalog_sha256,
                definition_version=k["definition_version"], verification_status=k["verification"]["status"],
                warehouse_path=str(self.warehouse_path),
                dependencies=tuple(k["dependencies"]), dependency_results=dependency_results,
                indicator_code=w["indicator_code"], formula=k["formula"]["from_fact"],
                input_fact_key=(code, year, w["source"], w["indicator_code"], w["dimension"],
                                w["dimension_value"]) if input_value is not None else None,
                provenance=provenance, quality_warnings=warnings, source_warnings=notices,
                review_reasons=tuple(dict.fromkeys(review)), requires_review=bool(review),
            )

        if year not in k["valid_years"]:
            return result("unavailable", "out_of_catalog_year")
        if kpi_id == "unbanked_share":
            account = self.calculate(code, year, "account_ownership")
            return result(
                account.availability_status, reason=account.reason,
                value=100 - account.value if account.availability_status == "available" else None,
                input_value=account.input_value, input_unit=account.input_unit,
                dependency_results=(account,),
            )
        with duckdb.connect(str(self.warehouse_path), read_only=True) as con:
            entities = con.execute(
                "SELECT is_country, is_aggregate FROM country_dim WHERE iso3 = ?", [code]
            ).fetchmany(2)
            if not entities:
                return result("unavailable", "country_not_in_warehouse")
            if len(entities) != 1 or entities[0] != (True, False):
                return result("requires_review", "invalid_country_dimension")
            rows = con.execute(
                "SELECT value, unit FROM fact WHERE iso3 = ? AND year = ? "
                "AND source = ? AND indicator_code = ? AND dimension = ? AND dimension_value = ?",
                [code, year, w["source"], w["indicator_code"], w["dimension"], w["dimension_value"]],
            ).fetchmany(2)
        if not rows:
            return result("unavailable", "missing_observation")
        if len(rows) != 1:
            return result("requires_review", "duplicate_observations")
        raw, unit = rows[0]
        if unit != w["input_unit"]:
            return result("requires_review", "unexpected_input_unit", input_unit=unit)
        if raw is None or not math.isfinite(raw):
            return result("unavailable", "missing_or_nonfinite_input", input_unit=unit)
        raw = float(raw)
        if raw < 0 or (unit == "fraction" and raw > 1):
            return result("requires_review", "out_of_range_input", input_value=raw, input_unit=unit)
        value = raw * 100 if unit == "fraction" else raw
        return result("available", value=value, input_value=raw, input_unit=unit)
