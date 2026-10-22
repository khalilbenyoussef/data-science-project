"""Chargement et transformations des artefacts BIFlow pour le dashboard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COUNTRY_YEAR_PATH = PROJECT_ROOT / "data" / "processed" / "country_year.parquet"
KPI_VALUES_PATH = PROJECT_ROOT / "outputs" / "kpis" / "kpi_values.parquet"
KPI_SUMMARY_PATH = PROJECT_ROOT / "outputs" / "kpis" / "kpi_summary.json"
INSIGHTS_PATH = PROJECT_ROOT / "outputs" / "insights" / "insights.json"
QUALITY_PATH = PROJECT_ROOT / "data" / "quality" / "quality_report.json"

KPI_METRIC_COLUMNS = {
    "inclusion_rate": "account_own",
    "gender_gap": "gender_gap_pp",
    "mobile_account_rate": "mobile_account",
    "digital_payment_rate": "digital_payment",
    "inactive_account_rate": "inactive",
    "savings_rate": "savings",
    "borrowing_rate": "borrowing",
    "atm_density": "atm_per_100k",
    "branch_density": "brch_per_100k",
    "depositors_per_1k": "depositors_per_1k",
    "borrowers_per_1k": "borrowers_per_1k",
    "deposit_accounts_per_1k": "deposit_accounts_per_1k",
    "gdp_per_capita": "gdp_pc",
    "gdp_growth": "gdp_growth_pct",
}

LATEST_COLUMNS = [
    "id",
    "label",
    "unit",
    "source",
    "direction",
    "decimals",
    "latest_year",
    "latest_value",
    "previous_value",
    "change",
    "n_years",
    "n_obs",
]

QUALITY_COLUMNS = ["source", "rows", "cols", "score", "gate", "issues"]


class DashboardDataError(RuntimeError):
    """Erreur de chargement des artefacts nécessaires au dashboard."""


def _resolve(path: str | Path | None, default: Path) -> Path:
    return Path(path) if path is not None else default


def _read_json(path: str | Path | None, default: Path) -> dict[str, Any]:
    resolved = _resolve(path, default)
    if not resolved.exists():
        raise DashboardDataError(
            f"Artefact manquant : {resolved}\nLance d'abord : python main.py run"
        )
    with resolved.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _require_columns(df: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise DashboardDataError(
            f"{name} : colonnes manquantes {missing}"
        )


def load_country_year(path: str | Path | None = None) -> pd.DataFrame:
    resolved = _resolve(path, COUNTRY_YEAR_PATH)
    if not resolved.exists():
        raise DashboardDataError(
            f"Artefact manquant : {resolved}\nLance d'abord : python main.py run"
        )
    df = pd.read_parquet(resolved)
    _require_columns(df, ["iso3", "country", "year"], "country_year")
    df = df.copy()
    df["iso3"] = df["iso3"].astype("string").str.upper().str.strip()
    df["country"] = df["country"].astype("string")
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    for column in set(KPI_METRIC_COLUMNS.values()) & set(df.columns):
        df[column] = pd.to_numeric(df[column], errors="coerce")
    if "is_country" not in df.columns:
        df["is_country"] = True
    else:
        df["is_country"] = df["is_country"].fillna(False).astype(bool)
    for column in ("region", "income_group"):
        if column in df.columns:
            df[column] = df[column].astype("string")
    return df


def load_kpi_values(path: str | Path | None = None) -> pd.DataFrame:
    resolved = _resolve(path, KPI_VALUES_PATH)
    if not resolved.exists():
        raise DashboardDataError(
            f"Artefact manquant : {resolved}\nLance d'abord : python main.py run"
        )
    df = pd.read_parquet(resolved)
    _require_columns(
        df,
        ["kpi_id", "label", "unit", "year", "dimension", "dimension_value", "value"],
        "kpi_values",
    )
    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    if "n_obs" in df.columns:
        df["n_obs"] = pd.to_numeric(df["n_obs"], errors="coerce")
    for column in ("kpi_id", "label", "unit", "dimension", "dimension_value"):
        df[column] = df[column].astype("string")
    return df


def load_kpi_summary(path: str | Path | None = None) -> dict[str, Any]:
    return _read_json(path, KPI_SUMMARY_PATH)


def load_quality(path: str | Path | None = None) -> dict[str, Any]:
    return _read_json(path, QUALITY_PATH)


def load_insights(path: str | Path | None = None) -> dict[str, Any]:
    return _read_json(path, INSIGHTS_PATH)


def load_all() -> dict[str, Any]:
    return {
        "country_year": load_country_year(),
        "kpi_values": load_kpi_values(),
        "kpi_summary": load_kpi_summary(),
        "quality": load_quality(),
        "insights": load_insights(),
    }


def latest_kpis(summary: dict[str, Any]) -> pd.DataFrame:
    items = summary.get("items") or []
    df = pd.DataFrame(items)
    for column in LATEST_COLUMNS:
        if column not in df.columns:
            df[column] = pd.NA
    return df[LATEST_COLUMNS].reset_index(drop=True)


def filter_country_year(
    df: pd.DataFrame,
    regions: Iterable[str] | None = None,
    income_groups: Iterable[str] | None = None,
    countries: Iterable[str] | None = None,
    year: int | None = None,
    only_countries: bool = True,
) -> pd.DataFrame:
    out = df.copy()
    if only_countries and "is_country" in out.columns:
        out = out[out["is_country"].fillna(False).astype(bool)]
    if regions and "region" in out.columns:
        out = out[out["region"].isin(list(regions))]
    if income_groups and "income_group" in out.columns:
        out = out[out["income_group"].isin(list(income_groups))]
    if countries:
        codes = {str(code).upper() for code in countries}
        out = out[out["iso3"].isin(codes)]
    if year is not None:
        out = out[out["year"] == int(year)]
    return out.reset_index(drop=True)


def kpi_series(
    kpi_values: pd.DataFrame,
    kpi_ids: Iterable[str],
    dimension: str | None = "global",
    dimension_value: str | None = "all",
) -> pd.DataFrame:
    ids = list(kpi_ids)
    if not ids:
        return kpi_values.iloc[0:0].copy()
    out = kpi_values[kpi_values["kpi_id"].isin(ids)]
    if dimension is not None:
        out = out[out["dimension"] == dimension]
    if dimension_value is not None:
        out = out[out["dimension_value"] == dimension_value]
    out = out.copy()
    if "n_obs" not in out.columns:
        out["n_obs"] = pd.NA
    columns = ["kpi_id", "label", "unit", "year", "value", "n_obs"]
    present = [column for column in columns if column in out.columns]
    return out[present].sort_values(["label", "year"]).reset_index(drop=True)


def country_snapshot(
    country_year: pd.DataFrame,
    year: int,
    kpi_id: str,
) -> pd.DataFrame:
    metric = KPI_METRIC_COLUMNS.get(kpi_id)
    if metric is None or metric not in country_year.columns:
        raise DashboardDataError(f"KPI pays inconnu ou absent : {kpi_id}")
    out = filter_country_year(country_year, year=year)
    columns = ["iso3", "country", "year", metric]
    for column in ("region", "income_group"):
        if column in out.columns:
            columns.append(column)
    out = out[columns].rename(columns={metric: "value"})
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    return out.dropna(subset=["value"]).reset_index(drop=True)


def country_ranking(
    country_year: pd.DataFrame,
    year: int,
    kpi_id: str,
    ascending: bool = False,
    n: int | None = None,
) -> pd.DataFrame:
    out = country_snapshot(country_year, year, kpi_id).sort_values(
        "value", ascending=ascending
    )
    if n is not None:
        out = out.head(int(n))
    return out.reset_index(drop=True)


def top_bottom(df: pd.DataFrame, n: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    ranked = df.sort_values("value", ascending=False)
    top = ranked.head(int(n)).reset_index(drop=True)
    bottom = ranked.tail(int(n)).sort_values("value").reset_index(drop=True)
    return top, bottom


def coverage_warnings(summary: dict[str, Any]) -> list[str]:
    return [str(item) for item in (summary.get("issues") or [])]


def quality_table(quality: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for source, check in (quality.get("checks") or {}).items():
        rows.append(
            {
                "source": source,
                "rows": check.get("rows"),
                "cols": check.get("cols"),
                "score": check.get("score"),
                "gate": check.get("gate"),
                "issues": len(check.get("issues") or []),
            }
        )
    return pd.DataFrame(rows, columns=QUALITY_COLUMNS)


def available_years(df: pd.DataFrame) -> list[int]:
    values = pd.to_numeric(df["year"], errors="coerce").dropna().unique()
    return sorted(int(value) for value in values)


def dimension_values(kpi_values: pd.DataFrame, dimension: str) -> list[str]:
    out = (
        kpi_values.loc[kpi_values["dimension"] == dimension, "dimension_value"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    return sorted(out)


__all__ = [
    "COUNTRY_YEAR_PATH",
    "DashboardDataError",
    "INSIGHTS_PATH",
    "KPI_METRIC_COLUMNS",
    "KPI_SUMMARY_PATH",
    "KPI_VALUES_PATH",
    "PROJECT_ROOT",
    "QUALITY_PATH",
    "available_years",
    "country_ranking",
    "country_snapshot",
    "coverage_warnings",
    "dimension_values",
    "filter_country_year",
    "kpi_series",
    "latest_kpis",
    "load_all",
    "load_country_year",
    "load_insights",
    "load_kpi_summary",
    "load_kpi_values",
    "load_quality",
    "quality_table",
    "top_bottom",
]
