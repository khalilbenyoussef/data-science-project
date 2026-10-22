"""S9 - ETL Agent : harmonisation des 3 sources et modele en etoile (DuckDB)."""

from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Mapping

import duckdb
import numpy as np
import pandas as pd

from biflow.agents.base import AgentError, BaseAgent
from biflow.config import resolve
from biflow.tools.dictionary import (
    FAS_LABELS,
    FINDEX_LABELS,
    GDP_LABELS,
    unit_for,
)
from biflow.utils.countries import (
    country_name,
    invalid_iso3,
    is_aggregate,
    is_country,
    normalize_iso3,
)
from biflow.utils.io import load_source, save_json, write_csv

YEAR_RE = re.compile(r"^(19|20)\d{2}$")
FACT_COLUMNS = [
    "iso3",
    "country",
    "year",
    "source",
    "indicator_code",
    "indicator_label",
    "dimension",
    "dimension_value",
    "value",
    "unit",
]
FINDEX_REQUIRED = ("codewb", "year", "group", "group2")
FINDEX_OPTIONAL = (
    "countrynewwb",
    "regionwb24_hi",
    "incomegroupwb24",
    "pop_adult",
)
FAS_REQUIRED = ("SERIES_CODE",)
FAS_OPTIONAL = ("COUNTRY", "INDICATOR", "UNIT")
GDP_REQUIRED = ("iso3", "indicator_code", "year", "value")
GDP_OPTIONAL = ("country", "indicator_name")
FACT_KEY = (
    "iso3",
    "year",
    "source",
    "indicator_code",
    "dimension",
    "dimension_value",
)
PIVOT_KEY = ("iso3", "year", "indicator_code", "dimension_value")


def _new_report() -> dict[str, Any]:
    return {
        "input_rows": {},
        "output_rows": {},
        "rejected": {},
        "warnings": [],
        "checks": {},
    }


def _reject(report: dict[str, Any] | None, source: str, reason: str, count: int) -> None:
    if report is None or not count:
        return
    rejected = report.setdefault("rejected", {})
    source_bucket = rejected.setdefault(source, {})
    source_bucket[reason] = int(source_bucket.get(reason, 0)) + int(count)


def _warn(report: dict[str, Any] | None, message: str) -> None:
    if report is None:
        return
    warnings = report.setdefault("warnings", [])
    if message not in warnings:
        warnings.append(message)


def _require_columns(
    df: pd.DataFrame,
    source: str,
    required: tuple[str, ...],
    optional: tuple[str, ...] = (),
    report: dict[str, Any] | None = None,
) -> None:
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise AgentError(
            f"[{source}] colonnes obligatoires absentes : {', '.join(missing)}"
        )
    absent_optional = [column for column in optional if column not in df.columns]
    if absent_optional:
        _warn(
            report,
            f"[{source}] colonnes optionnelles absentes, repli applique : "
            f"{', '.join(absent_optional)}",
        )


def _add_input(report: dict[str, Any] | None, source: str, rows: int) -> None:
    if report is None:
        return
    report.setdefault("input_rows", {})[source] = int(rows)


def _clean_iso3(
    series: pd.Series, source: str, report: dict[str, Any] | None
) -> pd.Series:
    raw = series
    normalized = raw.map(normalize_iso3)
    valid = normalized.map(
        lambda value: isinstance(value, str) and bool(re.fullmatch(r"[A-Z]{3}", value))
    )
    missing = raw.isna()
    invalid = ~valid & ~missing
    _reject(report, source, "iso3_missing", int(missing.sum()))
    _reject(report, source, "iso3_invalid", int(invalid.sum()))
    if missing.any():
        _warn(report, f"[{source}] {int(missing.sum())} lignes sans code ISO3 rejetees")
    if invalid.any():
        _warn(report, f"[{source}] {int(invalid.sum())} codes ISO3 malformes rejetes")
    return normalized.where(valid)


def _year_series(
    series: pd.Series, source: str, report: dict[str, Any] | None
) -> pd.Series:
    raw = series
    numeric = pd.to_numeric(raw, errors="coerce")
    missing = raw.isna()
    non_numeric = numeric.isna() & ~missing
    array = numeric.astype("float64").to_numpy()
    non_finite = ~np.isfinite(array) & ~np.isnan(array)
    numeric = numeric.where(~non_finite)
    non_integer = numeric.notna() & (numeric % 1 != 0)
    numeric = numeric.where(~non_integer)
    _reject(report, source, "year_missing", int(missing.sum()))
    _reject(report, source, "year_non_numeric", int(non_numeric.sum()))
    _reject(report, source, "year_non_finite", int(non_finite.sum()))
    _reject(report, source, "year_non_integer", int(non_integer.sum()))
    if non_numeric.any():
        _warn(report, f"[{source}] {int(non_numeric.sum())} annees non numeriques rejetees")
    if non_integer.any():
        _warn(report, f"[{source}] {int(non_integer.sum())} annees non entieres rejetees")
    return numeric.astype("Int64")


def _value_series(
    series: pd.Series, source: str, report: dict[str, Any] | None
) -> pd.Series:
    raw = series
    numeric = pd.to_numeric(raw, errors="coerce")
    missing = raw.isna()
    non_numeric = numeric.isna() & ~missing
    array = numeric.astype("float64").to_numpy()
    non_finite = ~np.isfinite(array) & ~np.isnan(array)
    numeric = numeric.where(~non_finite)
    _reject(report, source, "value_missing", int(missing.sum()))
    _reject(report, source, "value_non_numeric", int(non_numeric.sum()))
    _reject(report, source, "value_non_finite", int(non_finite.sum()))
    if non_numeric.any():
        _warn(report, f"[{source}] {int(non_numeric.sum())} valeurs non numeriques rejetees")
    return numeric


def _normalize_rate(
    series: pd.Series, indicator: str, report: dict[str, Any] | None
) -> pd.Series:
    numeric = _value_series(series, "findex", report)
    valid = numeric.dropna()
    if valid.empty:
        return numeric
    maximum = float(valid.max())
    if maximum <= 1.0 + 1e-9:
        factor = 1.0
    elif maximum <= 100.0 + 1e-9:
        if (valid > 1.0 + 1e-9).any() and (valid <= 1.0 + 1e-9).any():
            raise AgentError(
                f"[findex] echelle mixte detectee pour {indicator!r} : "
                "fractions et pourcentages dans la meme colonne"
            )
        factor = 100.0
        _warn(
            report,
            f"[findex] {indicator} fourni en pourcentage, converti en fraction",
        )
    else:
        raise AgentError(
            f"[findex] echelle inattendue pour {indicator!r} : maximum={maximum:.6g}"
        )
    if factor != 1.0:
        numeric = numeric / factor
    out_of_range = numeric.notna() & ((numeric < 0) | (numeric > 1))
    _reject(report, "findex", "rate_out_of_range", int(out_of_range.sum()))
    if out_of_range.any():
        _warn(
            report,
            f"[findex] {int(out_of_range.sum())} valeurs hors [0,1] rejetees pour {indicator}",
        )
    return numeric.mask(out_of_range)


def _resolve_duplicates(
    df: pd.DataFrame,
    key: tuple[str, ...],
    source: str,
    report: dict[str, Any] | None,
    label: str,
) -> pd.DataFrame:
    if df.empty:
        return df
    exact = df.duplicated(keep="first")
    if exact.any():
        _reject(report, source, "exact_duplicates_removed", int(exact.sum()))
        _warn(
            report,
            f"[{source}] {int(exact.sum())} doublons exacts supprimes ({label})",
        )
        df = df.loc[~exact].copy()
    duplicate_rows = df[df.duplicated(subset=list(key), keep=False)]
    if not duplicate_rows.empty:
        grouped = duplicate_rows.groupby(list(key), dropna=False, sort=False)
        conflicts = [
            (key_value, len(group))
            for key_value, group in grouped
            if len(group) > 1
        ]
        if conflicts:
            raise AgentError(
                f"[{source}] doublons conflictuels sur {label} ({', '.join(key)}) : "
                f"{len(conflicts)} groupes, exemple={conflicts[0]}"
            )
    return df


def _assert_unique(df: pd.DataFrame, key: tuple[str, ...], label: str) -> None:
    if df.duplicated(subset=list(key), keep=False).any():
        raise AgentError(f"[etl] cle non unique dans {label} : {', '.join(key)}")


def _assert_no_pivot_collisions(fact: pd.DataFrame) -> None:
    duplicates = fact[fact.duplicated(subset=list(PIVOT_KEY), keep=False)]
    if not duplicates.empty:
        sample = duplicates.iloc[0][list(PIVOT_KEY)].to_dict()
        raise AgentError(
            "[etl] collision de cles avant pivot : "
            f"{len(duplicates)} lignes, exemple={sample}"
        )


def _parse_fas_codes(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    text = series.astype("string").str.strip().str.upper()
    parts = text.str.split(".", n=1)
    iso3 = parts.str[0]
    remainder = parts.str[1]
    series_code = remainder.str.rsplit(".", n=1).str[0]
    return iso3, series_code


def findex_long(
    df: pd.DataFrame,
    source_cfg: dict,
    min_year: int,
    max_year: int,
    report: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    _require_columns(df, "findex", FINDEX_REQUIRED, FINDEX_OPTIONAL, report)
    _add_input(report, "findex", len(df))

    configured = list(source_cfg.get("indicators", []))
    missing_indicators = [column for column in configured if column not in df.columns]
    if missing_indicators:
        _warn(
            report,
            f"[findex] indicateurs configures absents : {', '.join(missing_indicators)}",
        )
    indicators = [column for column in configured if column in df.columns]
    if not indicators:
        raise AgentError("[findex] aucune colonne indicateur trouvee")

    base = df.copy()
    base["iso3"] = _clean_iso3(base["codewb"], "findex", report)
    base["year_i"] = _year_series(base["year"], "findex", report)
    for column in ("group", "group2"):
        missing = base[column].isna()
        _reject(report, "findex", f"{column}_missing", int(missing.sum()))
        if missing.any():
            _warn(report, f"[findex] {int(missing.sum())} valeurs {column} manquantes rejetees")

    in_range = base["year_i"].between(min_year, max_year)
    out_of_range = base["year_i"].notna() & ~in_range
    _reject(report, "findex", "year_out_of_range", int(out_of_range.sum()))
    valid = (
        in_range
        & base["iso3"].notna()
        & base["group"].notna()
        & base["group2"].notna()
    )
    base = base.loc[valid].copy()
    if base.empty:
        raise AgentError("[findex] aucune observation valide apres filtrage")
    unknown = invalid_iso3(base["iso3"].dropna().unique())
    if unknown:
        _warn(
            report,
            f"[findex] codes ISO3 inconnus conserves : {', '.join(unknown[:10])}",
        )

    base["country"] = (
        base["countrynewwb"] if "countrynewwb" in base.columns else pd.NA
    )
    for indicator in indicators:
        base[indicator] = _normalize_rate(base[indicator], indicator, report)

    id_vars = ["iso3", "country", "year_i", "group", "group2"]
    long = base[id_vars + indicators].melt(
        id_vars=id_vars,
        value_vars=indicators,
        var_name="indicator_code",
        value_name="value",
    )
    long = long.dropna(subset=["value"])
    long = long.rename(
        columns={
            "year_i": "year",
            "group": "dimension",
            "group2": "dimension_value",
        }
    )
    long["source"] = "findex"
    long["indicator_label"] = long["indicator_code"].map(FINDEX_LABELS).fillna(
        long["indicator_code"]
    )
    long["unit"] = long["indicator_code"].map(lambda code: unit_for(code, "fraction"))
    long["year"] = long["year"].astype(int)
    long = _resolve_duplicates(
        long[FACT_COLUMNS],
        ("iso3", "year", "dimension", "dimension_value", "indicator_code"),
        "findex",
        report,
        "fait Findex",
    )
    _current = report
    if _current is not None:
        _current.setdefault("output_rows", {})["findex"] = int(len(long))

    population = _population_from_findex(base, report)
    return long, population


def _population_from_findex(
    base: pd.DataFrame, report: dict[str, Any] | None
) -> pd.DataFrame:
    empty = pd.DataFrame(columns=["iso3", "year", "pop_adult"])
    if "pop_adult" not in base.columns:
        _warn(report, "[findex] pop_adult absente : table population vide")
        if report is not None:
            report.setdefault("output_rows", {})["population"] = 0
        return empty
    population = base[["iso3", "year_i", "pop_adult"]].copy()
    population["pop_adult"] = _value_series(population["pop_adult"], "findex", report)
    missing = population["pop_adult"].isna()
    _reject(report, "findex", "population_missing", int(missing.sum()))
    population = population.dropna(subset=["iso3", "year_i", "pop_adult"])
    non_positive = population["pop_adult"] <= 0
    _reject(report, "findex", "population_nonpositive", int(non_positive.sum()))
    population = population.loc[~non_positive].copy()
    before = len(population)
    population = population.drop_duplicates(
        subset=["iso3", "year_i", "pop_adult"]
    )
    _reject(
        report,
        "findex",
        "population_repeated_metadata",
        before - len(population),
    )
    population = population.rename(columns={"year_i": "year"})
    population["year"] = population["year"].astype(int)
    population = _resolve_duplicates(
        population[["iso3", "year", "pop_adult"]],
        ("iso3", "year"),
        "findex",
        report,
        "population",
    ).sort_values(["iso3", "year"]).reset_index(drop=True)
    if report is not None:
        report.setdefault("output_rows", {})["population"] = int(len(population))
    return population


def fas_long(
    df: pd.DataFrame,
    series_map: dict[str, str],
    min_year: int,
    max_year: int,
    report: dict[str, Any] | None = None,
) -> pd.DataFrame:
    _require_columns(df, "fas", FAS_REQUIRED, FAS_OPTIONAL, report)
    _add_input(report, "fas", len(df))
    year_cols = [column for column in df.columns if YEAR_RE.match(str(column))]
    if not year_cols:
        raise AgentError("[fas] aucune colonne annee detectee")

    reverse = {series: code for code, series in series_map.items()}
    work = df.copy()
    work["iso3"], work["series_code"] = _parse_fas_codes(work["SERIES_CODE"])
    work["iso3"] = _clean_iso3(work["iso3"], "fas", report)
    work["indicator_code"] = work["series_code"].map(reverse)
    work = work.loc[work["indicator_code"].notna() & work["iso3"].notna()].copy()
    if work.empty:
        raise AgentError("[fas] aucune serie du mapping trouvee dans le fichier")
    unknown = invalid_iso3(work["iso3"].dropna().unique())
    if unknown:
        _warn(
            report,
            f"[fas] codes ISO3 inconnus conserves : {', '.join(unknown[:10])}",
        )

    work["country"] = work["COUNTRY"] if "COUNTRY" in work.columns else pd.NA
    work["indicator_label_raw"] = (
        work["INDICATOR"] if "INDICATOR" in work.columns else pd.NA
    )
    id_vars = ["iso3", "country", "indicator_code", "indicator_label_raw"]
    long = work[id_vars + year_cols].melt(
        id_vars=id_vars,
        value_vars=year_cols,
        var_name="year",
        value_name="value",
    )
    long["year"] = _year_series(long["year"], "fas", report)
    long["value"] = _value_series(long["value"], "fas", report)
    in_range = long["year"].between(min_year, max_year)
    out_of_range = long["year"].notna() & ~in_range
    _reject(report, "fas", "year_out_of_range", int(out_of_range.sum()))
    long = long.loc[in_range & long["value"].notna()].copy()
    negative = long["value"] < 0
    _reject(report, "fas", "negative_values", int(negative.sum()))
    if negative.any():
        _warn(report, f"[fas] {int(negative.sum())} valeurs negatives rejetees")
    long = long.loc[~negative].copy()
    long["year"] = long["year"].astype(int)
    long["source"] = "fas"
    long["indicator_label"] = long["indicator_code"].map(FAS_LABELS)
    long["indicator_label"] = (
        long["indicator_label"]
        .fillna(long["indicator_label_raw"])
        .fillna(long["indicator_code"])
    )
    long["unit"] = long["indicator_code"].map(lambda code: unit_for(code, "number"))
    long["dimension"] = "bank_type"
    long["dimension_value"] = "commercial_banks"
    long = _resolve_duplicates(
        long[FACT_COLUMNS],
        ("iso3", "year", "indicator_code", "dimension", "dimension_value"),
        "fas",
        report,
        "fait FAS",
    )
    if report is not None:
        report.setdefault("output_rows", {})["fas"] = int(len(long))
    return long


def gdp_long(
    df: pd.DataFrame,
    min_year: int,
    max_year: int,
    report: dict[str, Any] | None = None,
) -> pd.DataFrame:
    _require_columns(df, "gdp", GDP_REQUIRED, GDP_OPTIONAL, report)
    _add_input(report, "gdp", len(df))
    work = df.copy()
    work["iso3"] = _clean_iso3(work["iso3"], "gdp", report)
    work["year_i"] = _year_series(work["year"], "gdp", report)
    work["value"] = _value_series(work["value"], "gdp", report)
    in_range = work["year_i"].between(min_year, max_year)
    out_of_range = work["year_i"].notna() & ~in_range
    _reject(report, "gdp", "year_out_of_range", int(out_of_range.sum()))
    work = work.loc[
        in_range & work["iso3"].notna() & work["value"].notna()
    ].copy()
    unknown = invalid_iso3(work["iso3"].dropna().unique())
    if unknown:
        _warn(
            report,
            f"[gdp] codes ISO3 inconnus conserves : {', '.join(unknown[:10])}",
        )
    negative = work["value"] < 0
    _reject(report, "gdp", "negative_values", int(negative.sum()))
    if negative.any():
        _warn(report, f"[gdp] {int(negative.sum())} valeurs negatives rejetees")
    work = work.loc[~negative].copy()
    work["year"] = work["year_i"].astype(int)
    work["country"] = work["country"] if "country" in work.columns else pd.NA
    indicator_name = (
        work["indicator_name"]
        if "indicator_name" in work.columns
        else pd.Series(pd.NA, index=work.index)
    )
    work["indicator_label"] = (
        work["indicator_code"]
        .map(GDP_LABELS)
        .fillna(indicator_name)
        .fillna(work["indicator_code"])
    )
    work["source"] = "gdp"
    work["unit"] = work["indicator_code"].map(lambda code: unit_for(code, "usd"))
    work["dimension"] = "total"
    work["dimension_value"] = "all"
    work = _resolve_duplicates(
        work[FACT_COLUMNS],
        ("iso3", "year", "indicator_code", "dimension", "dimension_value"),
        "gdp",
        report,
        "fait WDI",
    )
    if report is not None:
        report.setdefault("output_rows", {})["gdp"] = int(len(work))
    return work


def _country_label(name: Any, code: str) -> str:
    if isinstance(name, str) and name.strip():
        return name.strip()
    return country_name(code, code)


def build_country_dim(
    findex: pd.DataFrame,
    fas: pd.DataFrame,
    gdp: pd.DataFrame,
    report: dict[str, Any] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if "codewb" in findex.columns:
        base = findex.copy()
        base["iso3"] = base["codewb"].map(normalize_iso3)
        base = base.loc[base["iso3"].map(lambda value: bool(value and re.fullmatch(r"[A-Z]{3}", value)))]
        base = base.drop_duplicates(subset=["iso3"]).copy()
        for _, row in base.iterrows():
            rows.append(
                {
                    "iso3": row["iso3"],
                    "country": row.get("countrynewwb"),
                    "region": row.get("regionwb24_hi"),
                    "income_group": row.get("incomegroupwb24"),
                }
            )

    fas_names: dict[str, Any] = {}
    if "SERIES_CODE" in fas.columns:
        iso3, _ = _parse_fas_codes(fas["SERIES_CODE"])
        iso3 = iso3.map(normalize_iso3)
        names = fas["COUNTRY"] if "COUNTRY" in fas.columns else pd.Series(pd.NA, index=fas.index)
        frame = pd.DataFrame({"iso3": iso3, "country": names})
        frame = frame.loc[frame["iso3"].map(lambda value: bool(value and re.fullmatch(r"[A-Z]{3}", value)))]
        frame = frame.drop_duplicates(subset=["iso3"])
        fas_names = dict(zip(frame["iso3"], frame["country"]))

    gdp_names: dict[str, Any] = {}
    if "iso3" in gdp.columns:
        names = gdp["country"] if "country" in gdp.columns else pd.Series(pd.NA, index=gdp.index)
        frame = pd.DataFrame(
            {"iso3": gdp["iso3"].map(normalize_iso3), "country": names}
        )
        frame = frame.loc[frame["iso3"].map(lambda value: bool(value and re.fullmatch(r"[A-Z]{3}", value)))]
        frame = frame.drop_duplicates(subset=["iso3"])
        gdp_names = dict(zip(frame["iso3"], frame["country"]))

    known = {row["iso3"] for row in rows}
    for code in sorted(set(fas_names) | set(gdp_names)):
        if code in known:
            continue
        rows.append(
            {
                "iso3": code,
                "country": fas_names.get(code) if code in fas_names else gdp_names.get(code),
                "region": None,
                "income_group": None,
            }
        )
    if not rows:
        raise AgentError("[country_dim] aucun code pays exploitable")
    dim = pd.DataFrame(rows).drop_duplicates(subset=["iso3"]).copy()
    dim["country"] = [
        _country_label(name, code)
        for name, code in zip(dim["country"], dim["iso3"])
    ]
    dim["is_country"] = dim["iso3"].map(is_country).astype(bool)
    dim["is_aggregate"] = dim["iso3"].map(is_aggregate).astype(bool)
    dim = dim.sort_values("iso3").reset_index(drop=True)
    _assert_unique(dim, ("iso3",), "country_dim")
    unknown = invalid_iso3(dim["iso3"].unique())
    if unknown:
        _warn(
            report,
            f"[country_dim] codes inconnus conserves avec is_country=false : "
            f"{', '.join(unknown[:10])}",
        )
    return dim


def build_indicator_dim(
    fact: pd.DataFrame, report: dict[str, Any] | None = None
) -> pd.DataFrame:
    dim = (
        fact[["source", "indicator_code", "indicator_label", "unit", "dimension"]]
        .drop_duplicates(subset=["source", "indicator_code", "dimension"])
        .sort_values(["source", "indicator_code", "dimension"])
        .reset_index(drop=True)
    )
    dim["indicator_label"] = dim["indicator_label"].fillna(dim["indicator_code"])
    dim["unit"] = dim["unit"].fillna("")
    _assert_unique(dim, ("source", "indicator_code", "dimension"), "indicator_dim")
    if report is not None:
        report.setdefault("output_rows", {})["indicator_dim"] = int(len(dim))
    return dim


PIVOT_SQL = """
CREATE OR REPLACE TABLE country_year_pivot AS
SELECT
    iso3,
    min(country) AS country,
    year,
    max(CASE WHEN indicator_code = 'account_t_d' AND dimension_value = 'all' THEN value END) * 100 AS account_own,
    max(CASE WHEN indicator_code = 'account_t_d' AND dimension_value = 'men' THEN value END) * 100 AS account_male,
    max(CASE WHEN indicator_code = 'account_t_d' AND dimension_value = 'women' THEN value END) * 100 AS account_female,
    max(CASE WHEN indicator_code = 'fiaccount_t_d' AND dimension_value = 'all' THEN value END) * 100 AS fi_account,
    max(CASE WHEN indicator_code = 'mobileaccount_t_d' AND dimension_value = 'all' THEN value END) * 100 AS mobile_account,
    max(CASE WHEN indicator_code = 'inactive_t_d' AND dimension_value = 'all' THEN value END) * 100 AS inactive,
    max(CASE WHEN indicator_code = 'dig_acc' AND dimension_value = 'all' THEN value END) * 100 AS digital_payment,
    max(CASE WHEN indicator_code = 'save_any_t_d' AND dimension_value = 'all' THEN value END) * 100 AS savings,
    max(CASE WHEN indicator_code = 'borrow_any_t_d' AND dimension_value = 'all' THEN value END) * 100 AS borrowing,
    max(CASE WHEN indicator_code = 'merchant_pay' AND dimension_value = 'all' THEN value END) * 100 AS merchant_payment,
    max(CASE WHEN indicator_code = 'g20_any' AND dimension_value = 'all' THEN value END) * 100 AS remittance_use,
    max(CASE WHEN indicator_code = 'branch_density' THEN value END) AS brch_per_100k,
    max(CASE WHEN indicator_code = 'atm_density' THEN value END) AS atm_per_100k,
    max(CASE WHEN indicator_code = 'depositors_per_1k' THEN value END) AS depositors_per_1k,
    max(CASE WHEN indicator_code = 'borrowers_per_1k' THEN value END) AS borrowers_per_1k,
    max(CASE WHEN indicator_code = 'loan_accounts_per_1k' THEN value END) AS loan_accounts_per_1k,
    max(CASE WHEN indicator_code = 'deposit_accounts_per_1k' THEN value END) AS deposit_accounts_per_1k,
    max(CASE WHEN indicator_code = 'NY.GDP.PCAP.CD' THEN value END) AS gdp_pc,
    max(CASE WHEN indicator_code = 'NY.GDP.MKTP.CD' THEN value END) AS gdp_usd
FROM fact
GROUP BY iso3, year
"""

DERIVE_SQL = """
CREATE OR REPLACE TABLE country_year_derived AS
WITH base AS (
    SELECT
        *,
        lag(gdp_usd) OVER (PARTITION BY iso3 ORDER BY year) AS prev_gdp_usd,
        lag(year) OVER (PARTITION BY iso3 ORDER BY year) AS prev_year
    FROM country_year_pivot
)
SELECT
    * EXCLUDE (prev_gdp_usd, prev_year),
    CASE
        WHEN account_male IS NOT NULL AND account_female IS NOT NULL
        THEN account_male - account_female
    END AS gender_gap_pp,
    CASE
        WHEN gdp_usd IS NOT NULL AND gdp_usd > 0
         AND prev_gdp_usd IS NOT NULL AND prev_gdp_usd > 0
         AND prev_year = year - 1
        THEN 100 * (gdp_usd / prev_gdp_usd - 1)
    END AS gdp_growth_pct
FROM base
"""

JOIN_SQL = """
CREATE OR REPLACE TABLE country_year_final AS
SELECT cy.*, cd.region, cd.income_group, cd.is_country, cd.is_aggregate
FROM country_year_derived cy
LEFT JOIN country_dim cd USING (iso3)
"""


def _write_parquet(df: pd.DataFrame, path) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    df.to_parquet(tmp, index=False)
    os.replace(tmp, path)


def _check_country_year(df: pd.DataFrame) -> None:
    required = {
        "iso3",
        "country",
        "year",
        "account_own",
        "account_male",
        "account_female",
        "fi_account",
        "mobile_account",
        "inactive",
        "digital_payment",
        "savings",
        "borrowing",
        "merchant_payment",
        "remittance_use",
        "brch_per_100k",
        "atm_per_100k",
        "depositors_per_1k",
        "borrowers_per_1k",
        "loan_accounts_per_1k",
        "deposit_accounts_per_1k",
        "gdp_pc",
        "gdp_usd",
        "gender_gap_pp",
        "gdp_growth_pct",
        "region",
        "income_group",
        "is_country",
        "is_aggregate",
    }
    missing = sorted(required - set(df.columns))
    if missing:
        raise AgentError(f"[etl] colonnes absentes de country_year : {', '.join(missing)}")
    _assert_unique(df, ("iso3", "year"), "country_year")
    if df["iso3"].isna().any():
        raise AgentError("[etl] country_year contient des iso3 nuls")
    rate_columns = [
        "account_own",
        "account_male",
        "account_female",
        "fi_account",
        "mobile_account",
        "inactive",
        "digital_payment",
        "savings",
        "borrowing",
        "merchant_payment",
        "remittance_use",
    ]
    for column in rate_columns:
        values = pd.to_numeric(df[column], errors="coerce")
        invalid = values.notna() & ((values < 0) | (values > 100))
        if invalid.any():
            raise AgentError(
                f"[etl] valeurs hors [0,100] dans country_year.{column} : "
                f"{int(invalid.sum())}"
            )


class EtlAgent(BaseAgent):
    name = "etl"

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        sources = ctx.get("sources") or self.cfg.get("sources") or {}
        raw_paths = ctx.get("raw_paths") or {}
        etl_cfg = self.cfg.get("etl") or {}
        min_year = int(etl_cfg.get("min_year", 2011))
        max_year = int(etl_cfg.get("max_year", 2024))
        report = _new_report()

        for required in ("findex", "fas", "gdp"):
            if required not in sources:
                raise AgentError(f"source '{required}' absente de la configuration")

        def path_of_source(name: str) -> str:
            return raw_paths.get(name) or sources[name]["path"]

        self.log.info("[etl] lecture des 3 sources (%d-%d)", min_year, max_year)
        findex_raw = load_source({**sources["findex"], "path": path_of_source("findex")})
        fas_raw = load_source({**sources["fas"], "path": path_of_source("fas")})
        gdp_raw = load_source({**sources["gdp"], "path": path_of_source("gdp")})

        findex, population = findex_long(
            findex_raw, sources["findex"], min_year, max_year, report=report
        )
        fas = fas_long(
            fas_raw,
            sources["fas"].get("series") or {},
            min_year,
            max_year,
            report=report,
        )
        gdp = gdp_long(gdp_raw, min_year, max_year, report=report)

        country_dim = build_country_dim(
            findex_raw, fas_raw, gdp_raw, report=report
        )
        fact = pd.concat([findex, fas, gdp], ignore_index=True)
        if fact.empty:
            raise AgentError("[etl] aucun fait produit par les trois sources")
        name_map = country_dim.set_index("iso3")["country"]
        fact["country"] = fact["country"].fillna(fact["iso3"].map(name_map))
        fact["country"] = fact["country"].fillna(fact["iso3"])
        fact = _resolve_duplicates(
            fact[FACT_COLUMNS], FACT_KEY, "fact", report, "fait global"
        )
        _assert_no_pivot_collisions(fact)

        missing_dim = sorted(set(fact["iso3"]) - set(country_dim["iso3"]))
        if missing_dim:
            extra = pd.DataFrame(
                [
                    {
                        "iso3": code,
                        "country": country_name(code, code),
                        "region": None,
                        "income_group": None,
                        "is_country": is_country(code),
                        "is_aggregate": is_aggregate(code),
                    }
                    for code in missing_dim
                ]
            )
            country_dim = (
                pd.concat([country_dim, extra], ignore_index=True)
                .drop_duplicates(subset=["iso3"])
                .sort_values("iso3")
                .reset_index(drop=True)
            )
            _warn(
                report,
                f"[country_dim] {len(missing_dim)} codes ajoutes depuis le fait",
            )
        _assert_unique(country_dim, ("iso3",), "country_dim")
        indicator_dim = build_indicator_dim(fact, report=report)

        self.log.info(
            "[etl] fait: %d lignes (%s / %s / %s)",
            len(fact),
            len(findex),
            len(fas),
            len(gdp),
        )

        processed = resolve(self.cfg["paths"].get("processed", "data/processed"))
        processed.mkdir(parents=True, exist_ok=True)

        fact_path = processed / "fact_inclusion.parquet"
        country_path = processed / "country_dim.parquet"
        indicator_path = processed / "indicator_dim.parquet"
        year_path = processed / "country_year.parquet"
        population_path = processed / "population.parquet"
        warehouse_path = processed / "warehouse.duckdb"

        conn = duckdb.connect(str(warehouse_path))
        try:
            conn.register("fact_df", fact)
            conn.register("country_dim_df", country_dim)
            conn.register("population_df", population)
            conn.register("indicator_dim_df", indicator_dim)
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute("CREATE OR REPLACE TABLE fact AS SELECT * FROM fact_df")
                conn.execute(
                    "CREATE OR REPLACE TABLE country_dim AS SELECT * FROM country_dim_df"
                )
                conn.execute(
                    "CREATE OR REPLACE TABLE population AS SELECT * FROM population_df"
                )
                conn.execute(
                    "CREATE OR REPLACE TABLE indicator_dim AS SELECT * FROM indicator_dim_df"
                )
                conn.execute(PIVOT_SQL)
                conn.execute(DERIVE_SQL)
                conn.execute(JOIN_SQL)
                conn.execute("DROP TABLE IF EXISTS country_year")
                conn.execute("ALTER TABLE country_year_final RENAME TO country_year")
                country_year = conn.execute(
                    "SELECT * FROM country_year ORDER BY iso3, year"
                ).df()
                _check_country_year(country_year)
                conn.execute("DROP TABLE IF EXISTS country_year_pivot")
                conn.execute("DROP TABLE IF EXISTS country_year_derived")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        finally:
            conn.close()

        report.setdefault("checks", {})["fact_unique"] = True
        report["checks"]["country_dim_unique"] = True
        report["checks"]["indicator_dim_unique"] = True
        report["checks"]["country_year_unique"] = True
        findex_dimensions = set(
            fact.loc[fact["source"] == "findex", "dimension_value"]
            .dropna()
            .unique()
            .tolist()
        )
        report["checks"]["findex_dimensions"] = sorted(findex_dimensions)
        report["checks"]["findex_all_men_women"] = {
            "all": "all" in findex_dimensions,
            "men": "men" in findex_dimensions,
            "women": "women" in findex_dimensions,
        }
        report["checks"]["gdp_growth_rule"] = "year-1, positive values only"
        report.setdefault("output_rows", {})["fact"] = int(len(fact))
        report["output_rows"]["country_year"] = int(len(country_year))

        _write_parquet(fact, fact_path)
        _write_parquet(country_dim, country_path)
        _write_parquet(indicator_dim, indicator_path)
        _write_parquet(population, population_path)
        _write_parquet(country_year, year_path)
        if etl_cfg.get("write_csv_copy", True):
            csv_tmp = processed / ".country_year.csv.tmp"
            write_csv(country_year, csv_tmp)
            os.replace(csv_tmp, processed / "country_year.csv")

        lineage = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "run_id": ctx.get("run_id"),
            "period": {"min_year": min_year, "max_year": max_year},
            "inputs": {
                name: {
                    **(ctx.get("raw_meta") or {}).get(name, {}),
                    "path": path_of_source(name),
                    "rows": report["input_rows"].get(name),
                    "rejected": report["rejected"].get(name, {}),
                }
                for name in ("findex", "fas", "gdp")
            },
            "transforms": [
                "Findex: annees -> lignes, echelles verifiees puis fractions converties en % au pivot",
                "FAS: selection des series configurees, annees -> lignes",
                "WDI: indicateurs PIB -> lignes",
                "Pivot par pays x annee, croissance PIB sur annee-1 uniquement, jointure dimension pays",
            ],
            "checks": report["checks"],
            "rejected": report["rejected"],
            "warnings": report["warnings"],
            "outputs": {
                "fact_inclusion": {
                    "path": str(fact_path),
                    "rows": int(len(fact)),
                },
                "country_year": {
                    "path": str(year_path),
                    "rows": int(len(country_year)),
                },
                "country_dim": {
                    "path": str(country_path),
                    "rows": int(len(country_dim)),
                },
                "indicator_dim": {
                    "path": str(indicator_path),
                    "rows": int(len(indicator_dim)),
                },
                "population": {
                    "path": str(population_path),
                    "rows": int(len(population)),
                },
                "warehouse": str(warehouse_path),
            },
        }
        save_json(lineage, processed / "lineage.json")

        notes = dict(ctx.get("llm_notes") or {})
        notes["etl"] = (
            f"{len(fact):,} lignes harmonisees, {len(country_year):,} couples pays-annee, "
            f"{int(country_year['is_country'].fillna(False).sum())} lignes pays"
        )
        self.log.info("[etl] sorties -> %s", processed)

        return {
            "staging_paths": {
                "fact_inclusion": str(fact_path),
                "country_year": str(year_path),
                "country_dim": str(country_path),
                "indicator_dim": str(indicator_path),
                "population": str(population_path),
            },
            "warehouse_path": str(warehouse_path),
            "llm_notes": notes,
            "warnings": list(report["warnings"]),
        }
