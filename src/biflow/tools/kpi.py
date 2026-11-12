"""Deterministic, read-only single-country KPI lookups (no publication approval).

Example: KpiCalculator(path).calculate("TUN", 2024, "account_ownership").
Only the supported catalog contracts below can execute; YAML is never SQL.
A KPI with a provisional definition is always flagged provisional_definition.
"""
from __future__ import annotations

from contextlib import contextmanager, nullcontext
import copy
from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import re
from typing import Any

import duckdb
import yaml

from biflow.config import resolve
from biflow.tools.dictionary import FINDEX_UNVERIFIED
from biflow.utils.countries import is_country, normalize_iso3
from biflow.tools.kpi_provenance import KpiProvenance, QualityWarning, evidence


DEFAULT_CATALOG = "config/kpi_catalog.v1.yaml"
# Catalogue des KPI declares par l'utilisateur (sources user:*), fusionne au chargement ;
# le catalogue officiel (version, hash) n'est jamais modifie.
DEFAULT_USER_CATALOG = "config/kpi_catalog.user.yaml"
USER_STATUS = "user_declared"
USER_REVIEW_REASON = "user_provided_source"
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
                    "total_population", "percent", "100 * value", "verified"),
    "borrowing_rate": ("findex", "borrow_any_t_d", "fraction", "all", "all",
                       "total_population", "percent", "100 * value", "verified"),
    "unbanked_share": ("findex", "account_t_d", "fraction", "all", "all",
                       "total_population", "percent", "100 * (1 - value)", "derived_verified"),
    "formal_saving_rate": ("findex", "fin17a", "fraction", "all", "all",
                           "total_population", "percent", "100 * value", "verified"),
    "formal_borrowing_rate": ("findex", "fin22a", "fraction", "all", "all",
                              "total_population", "percent", "100 * value", "verified"),
    # Ecarts : dimension_value = premier terme, GAP_SUBTRAHEND = terme soustrait.
    "gender_gap": ("findex", "account_t_d", "fraction", "gender", "men",
                   "gender_men_minus_women", "percentage_points",
                   "100 * (value[men] - value[women])", "derived_verified"),
    "income_gap": ("findex", "account_t_d", "fraction", "income", "richest 60%",
                   "income_richest_60_minus_poorest_40", "percentage_points",
                   "100 * (value[richest 60%] - value[poorest 40%])", "derived_verified"),
    "age_gap": ("findex", "account_t_d", "fraction", "age_cat", "age 25+",
                "age_25_plus_minus_15_24", "percentage_points",
                "100 * (value[age 25+] - value[ages 15-24])", "derived_verified"),
    # Catalogue 1.6.0 : memes ecarts pour l'education, le marche du travail et le milieu
    "education_gap": ("findex", "account_t_d", "fraction", "education", "secondary edu or more",
                      "education_secondary_or_more_minus_primary_or_less", "percentage_points",
                      "100 * (value[secondary edu or more] - value[prim edu or less])",
                      "derived_verified"),
    "laborforce_gap": ("findex", "account_t_d", "fraction", "laborforce", "in laborforce",
                       "laborforce_in_minus_out", "percentage_points",
                       "100 * (value[in laborforce] - value[out of laborforce])", "derived_verified"),
    "urban_gap": ("findex", "account_t_d", "fraction", "urbanicity", "urban",
                  "urbanicity_urban_minus_rural", "percentage_points",
                  "100 * (value[urban] - value[rural])", "derived_verified"),
}
GAP_SUBTRAHEND = {"gender_gap": "women", "income_gap": "poorest 40%", "age_gap": "ages 15-24",
                  "education_gap": "prim edu or less", "laborforce_gap": "out of laborforce",
                  "urban_gap": "rural"}

# Series FAS du catalogue 1.4.0 : KPI = indicateur canonique, code FAS publie, unite.
FAS_SERIES = {
    "branch_density": ("FA26N.PHTADLT_NUM", "per_100k_adults"),
    "atm_density": ("FA18N.PHTADLT_NUM", "per_100k_adults"),
    "depositors_per_1k": ("FA29N_COMBANK.PTADLT_NUM", "per_1k_adults"),
    "borrowers_per_1k": ("FA21N_COMBANK.PTADLT_NUM", "per_1k_adults"),
    "deposit_accounts_per_1k": ("FA30N_COMBANK.PTADLT_NUM", "per_1k_adults"),
    "loan_accounts_per_1k": ("LOANACCN_COMBANK.PTADLT_NUM", "per_1k_adults"),
    "deposits_pct_gdp": ("OUTD_COMBANK.POGDP", "percent_of_gdp"),
    "loans_pct_gdp": ("OUTL_COMBANK.POGDP", "percent_of_gdp"),
}
CONTRACTS.update({
    kpi_id: ("fas", kpi_id, unit, "bank_type", "commercial_banks", "commercial_banks_all_adults",
             unit, "value", "verified_metadata")
    for kpi_id, (_series, unit) in FAS_SERIES.items() if kpi_id != "branch_density"
})
# Findex, population totale : fraction x 100 (glossaire Findex 2025)
CONTRACTS.update({
    kpi_id: ("findex", code, "fraction", "all", "all", "total_population", "percent",
             "100 * value", "verified")
    for kpi_id, code in (
        ("emergency_funds", "fin24aP"), ("emergency_source_savings", "fin24sav"),
        ("emergency_source_borrowing", "fin24bor"), ("mobile_money_account", "mobileaccount_t_d"),
        ("inactive_accounts", "inactive_t_d"),
    )
})
# Raisons de ne pas avoir de compte bancaire (fin11a-f) : part de tous les adultes 15+.
BARRIER_KPIS = {
    "barrier_too_far": "fin11a", "barrier_too_expensive": "fin11b",
    "barrier_no_documents": "fin11c", "barrier_insufficient_funds": "fin11d",
    "barrier_family_has_account": "fin11e", "barrier_no_trust": "fin11f",
}
CONTRACTS.update({
    kpi_id: ("findex", code, "fraction", "all", "all", "total_population", "percent",
             "100 * value", "verified")
    for kpi_id, code in BARRIER_KPIS.items()
})
# Detention de compte par sous-groupe Findex : un KPI par valeur de sous-groupe.
SUBGROUP_KPIS = {
    "account_ownership_women": ("gender", "women"),
    "account_ownership_men": ("gender", "men"),
    "account_ownership_poorest_40": ("income", "poorest 40%"),
    "account_ownership_richest_60": ("income", "richest 60%"),
    "account_ownership_age_15_24": ("age_cat", "ages 15-24"),
    "account_ownership_age_25_plus": ("age_cat", "age 25+"),
    "account_ownership_primary_or_less": ("education", "prim edu or less"),
    "account_ownership_secondary_or_more": ("education", "secondary edu or more"),
    "account_ownership_out_of_laborforce": ("laborforce", "out of laborforce"),
    "account_ownership_in_laborforce": ("laborforce", "in laborforce"),
    "account_ownership_rural": ("urbanicity", "rural"),
    "account_ownership_urban": ("urbanicity", "urban"),
}
CONTRACTS.update({
    kpi_id: ("findex", "account_t_d", "fraction", dimension, value,
             f"{dimension}_{value.replace(' ', '_').replace('%', '').replace('+', '_plus').replace('-', '_')}",
             "percent", "100 * value", "verified")
    for kpi_id, (dimension, value) in SUBGROUP_KPIS.items()
})


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
            # catalogue 1.8.0 : definition et denominateur en francais pour chaque KPI officiel
            # (traduction de la source anglaise, conservee) ; facultatifs pour les KPI utilisateur
            official = not str((kpi.get("warehouse") or {}).get("source", "")).startswith("user:")
            if official and (kpi.get("verification") or {}).get("status") != USER_STATUS:
                for field in ("definition_fr", "denominator_fr"):
                    if not isinstance(kpi.get(field), str) or not kpi[field].strip():
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
            if kpi["warehouse"]["indicator_code"] in FINDEX_UNVERIFIED:
                raise CatalogError(f"Unverified source indicator: {kpi_id}")
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
                    or w.get("subtrahend_dimension_value") != GAP_SUBTRAHEND.get(kpi_id)
                    or k["dependencies"] != (["account_ownership"] if kpi_id == "unbanked_share" else [])
                    or k["source"]["indicator"] != (
                        FAS_SERIES[kpi_id][0] if kpi_id in FAS_SERIES else w["indicator_code"])):
                raise CatalogError(f"Unsupported calculation contract: {kpi_id}")
        for kpi_id, kpi in kpis.items():  # KPI utilisateur : contrat generique et restreint
            if kpi_id in CONTRACTS:
                continue
            w = kpi["warehouse"]
            if (kpi["verification"]["status"] != USER_STATUS or not str(w["source"]).startswith("user:")
                    or w["fact_table"] != "fact" or kpi["formula"]["from_fact"] != "value"
                    or kpi["unit"] != w["input_unit"] or kpi["dependencies"] != []
                    or not isinstance(w.get("dimension"), str) or not isinstance(w.get("dimension_value"), str)):
                raise CatalogError(f"Unsupported calculation contract: {kpi_id}")
        # A gap depends on exactly its two same-year subgroup facts, over the years
        # both subgroup KPIs are observed.
        subgroup_kpi = {group: kpi_id for kpi_id, group in SUBGROUP_KPIS.items()}
        for kpi_id, subtrahend in GAP_SUBTRAHEND.items():
            w = kpis[kpi_id]["warehouse"]
            expected = [{"source": w["source"], "indicator_code": w["indicator_code"],
                         "dimension": w["dimension"], "dimension_value": value}
                        for value in (w["dimension_value"], subtrahend)]
            sides = [kpis[subgroup_kpi[(w["dimension"], value)]]["valid_years"]
                     for value in (w["dimension_value"], subtrahend)]
            if (kpis[kpi_id]["fact_dependencies"] != expected
                    or any(kpis[kpi_id]["valid_years"] != years for years in sides)
                    or not set(kpis[kpi_id]["valid_years"]) <= set(kpis["account_ownership"]["valid_years"])):
                raise CatalogError(f"Invalid gap fact dependencies: {kpi_id}")
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


# Parsed, validated catalogs keyed by (path, size, mtime_ns): a run parses the
# YAML once; any edit to the file changes the key and forces a new parse.
_CATALOG_CACHE: dict[tuple, tuple[dict[str, Any], str]] = {}


def user_catalog_path() -> Path:
    return resolve(os.getenv("BIFLOW_USER_CATALOG") or DEFAULT_USER_CATALOG)


def user_catalog_sha256() -> str | None:
    path = user_catalog_path()
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _merge_user_catalog(catalog: dict[str, Any], content: bytes) -> dict[str, Any]:
    """Ajoute les KPI et references utilisateur ; aucun identifiant officiel remplace."""
    try:
        user = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        raise CatalogError("Invalid user catalog YAML") from exc
    if not isinstance(user, dict) or not isinstance(user.get("kpis", {}), dict):
        raise CatalogError("Malformed user KPI catalog")
    merged = dict(catalog)
    clash = set(user.get("kpis") or {}) & set(catalog["kpis"]) | set(user.get("references") or {}) & set(catalog["references"])
    if clash:
        raise CatalogError(f"User catalog redefines official identifiers: {sorted(clash)}")
    merged["kpis"] = {**catalog["kpis"], **(user.get("kpis") or {})}
    merged["references"] = {**catalog["references"], **(user.get("references") or {})}
    return merged


def _catalog_and_hash(path: str | Path) -> tuple[dict[str, Any], str]:
    """Validated cached catalog (shared: treat as read-only) and SHA-256 of the
    official file. A user catalog, if present, is merged (its hash: user_catalog_sha256)."""
    target = resolve(path).resolve()
    stat = target.stat()
    user = user_catalog_path()
    user_stat = user.stat() if user.is_file() else None
    key = (str(target), stat.st_size, stat.st_mtime_ns,
           (str(user), user_stat.st_size, user_stat.st_mtime_ns) if user_stat else None)
    if key not in _CATALOG_CACHE:
        content = target.read_bytes()
        try:
            catalog = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise CatalogError("Invalid catalog YAML") from exc
        if user_stat is not None and isinstance(catalog, dict) and isinstance(catalog.get("kpis"), dict):
            catalog = _merge_user_catalog(catalog, user.read_bytes())
        _validate_catalog(catalog)
        _CATALOG_CACHE[key] = (catalog, hashlib.sha256(content).hexdigest())
    return _CATALOG_CACHE[key]


def load_catalog(path: str | Path = DEFAULT_CATALOG) -> dict[str, Any]:
    """Load local YAML and validate its structure and executable contracts."""
    return copy.deepcopy(_catalog_and_hash(path)[0])


# Batch mode: one read-only connection per warehouse, reused by every lookup.
_SHARED_CONNECTIONS: dict[str, Any] = {}


@contextmanager
def shared_read_only_connection(warehouse_path: str | Path):
    """Reuse one read-only DuckDB connection for all lookups inside the block.

    Close it (leave the block) before opening a write connection on the file.
    Outside the block each lookup opens and closes its own read-only connection.
    """
    path = str(resolve(warehouse_path).resolve())
    con = duckdb.connect(path, read_only=True)
    _SHARED_CONNECTIONS[path] = con
    try:
        yield con
    finally:
        _SHARED_CONNECTIONS.pop(path, None)
        con.close()


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
    # Gap KPIs: ((fact key, input value), ...) for both same-year subgroup facts.
    component_inputs: tuple[tuple[tuple[str | int, ...], float], ...] = ()


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
    Quality reports are bound to lineage by run_id and source hashes; the ETL
    still records no warehouse content digest. Recorded gate results must not be
    mistaken for publication certification.
    """

    def __init__(self, warehouse_path: str | Path,
                 catalog_path: str | Path = DEFAULT_CATALOG, *,
                 lineage_path: str | Path | None = None,
                 quality_report_path: str | Path | None = None):
        self._catalog, self._catalog_sha256 = _catalog_and_hash(catalog_path)
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
        if not isinstance(kpi_id, str) or kpi_id not in self._catalog["kpis"]:
            raise ValueError("Unknown or unsupported KPI; supported: " + ", ".join(self._catalog["kpis"]))
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
        if not isinstance(kpi_id, str) or kpi_id not in self._catalog["kpis"]:
            raise ValueError("Unknown or unsupported KPI; supported: " + ", ".join(self._catalog["kpis"]))
        code = normalize_iso3(iso3)
        if not code or not re.fullmatch(r"[A-Z]{3}", code) or not is_country(code):
            raise ValueError("iso3 must identify a country (aggregates are excluded)")
        if type(year) is not int or not 1 <= year <= 9999:
            raise ValueError("year must be an integer between 1 and 9999")
        k = self._catalog["kpis"][kpi_id]
        w = k["warehouse"]
        user_kpi = k["verification"]["status"] == USER_STATUS
        dimension_values = [w["dimension_value"]] + (
            [GAP_SUBTRAHEND[kpi_id]] if kpi_id in GAP_SUBTRAHEND else [])

        def result(status, reason=None, value=None, input_value=None, input_unit=None,
                   dependency_results=(), component_inputs=()):
            if dependency_results:
                dependency = dependency_results[0]
                provenance = dependency.provenance
                warnings, notices = dependency.quality_warnings, dependency.source_warnings
                review = list(dependency.review_reasons)
            else:
                warnings, notices = (), ()
                for dimension_value in dimension_values:
                    provenance, matched, source_notices = evidence(
                        self.warehouse_path, self.lineage_path, self.quality_report_path,
                        source=w["source"], iso3=code, year=year, indicator=w["indicator_code"],
                        dimension=w["dimension"], dimension_value=dimension_value,
                    )
                    warnings = tuple(dict.fromkeys(warnings + matched))
                    notices = tuple(dict.fromkeys(notices + source_notices))
                review = list(provenance.issues)
            if k["verification"]["status"] == "provisional":
                review.append("provisional_definition")
            if user_kpi:  # source fournie par l'utilisateur : toujours une note de revue
                review.append(USER_REVIEW_REASON)
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
                component_inputs=component_inputs,
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
        shared = _SHARED_CONNECTIONS.get(str(self.warehouse_path))
        with (nullcontext(shared) if shared is not None
              else duckdb.connect(str(self.warehouse_path), read_only=True)) as con:
            entities = con.execute(
                "SELECT is_country, is_aggregate FROM country_dim WHERE iso3 = ?", [code]
            ).fetchmany(2)
            if not entities:
                return result("unavailable", "country_not_in_warehouse")
            if len(entities) != 1 or entities[0] != (True, False):
                return result("requires_review", "invalid_country_dimension")
            observations = [self._observe(con, code, year, w, value, allow_negative=user_kpi)
                            for value in dimension_values]
        if kpi_id in GAP_SUBTRAHEND:
            # Both subgroup facts of the same year are required; never substituted.
            for status, reason, raw, unit in observations:
                if status != "available":
                    return result(status, reason, input_unit=unit)
            (_, _, first, unit), (_, _, second, _) = observations
            keys = [(code, year, w["source"], w["indicator_code"], w["dimension"], value)
                    for value in dimension_values]
            return result("available", value=100 * (first - second), input_unit=unit,
                          component_inputs=((keys[0], first), (keys[1], second)))
        status, reason, raw, unit = observations[0]
        if status != "available":
            return result(status, reason, input_value=raw, input_unit=unit)
        # KPI utilisateur : formule "value", aucune mise a l'echelle implicite
        value = raw if user_kpi else (raw * 100 if unit == "fraction" else raw)
        return result("available", value=value, input_value=raw, input_unit=unit)

    @staticmethod
    def _observe(con, code, year, w, dimension_value, allow_negative=False):
        """One parameterized fact lookup -> (status, reason, raw value, unit)."""
        rows = con.execute(
            "SELECT value, unit FROM fact WHERE iso3 = ? AND year = ? "
            "AND source = ? AND indicator_code = ? AND dimension = ? AND dimension_value = ?",
            [code, year, w["source"], w["indicator_code"], w["dimension"], dimension_value],
        ).fetchmany(2)
        if not rows:
            return "unavailable", "missing_observation", None, None
        if len(rows) != 1:
            return "requires_review", "duplicate_observations", None, None
        raw, unit = rows[0]
        if unit != w["input_unit"]:
            return "requires_review", "unexpected_input_unit", None, unit
        if raw is None or not math.isfinite(raw):
            return "unavailable", "missing_or_nonfinite_input", None, unit
        raw = float(raw)
        if (raw < 0 and not allow_negative) or (unit == "fraction" and not 0 <= raw <= 1):
            return "requires_review", "out_of_range_input", raw, unit
        return "available", None, raw, unit
