from __future__ import annotations

import pandas as pd
import pytest

from dashboard.data import (
    DashboardDataError,
    LATEST_COLUMNS,
    country_ranking,
    country_snapshot,
    filter_country_year,
    kpi_series,
    latest_kpis,
    load_country_year,
    quality_table,
    top_bottom,
)


def _country_year_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "iso3": ["MAR", "FRA", "WLD"],
            "country": ["Morocco", "France", "World"],
            "year": [2024, 2024, 2024],
            "account_own": [0.65, 0.95, 0.70],
            "gender_gap_pp": [8.0, 2.0, 5.0],
            "region": ["MENA", "Europe", None],
            "income_group": ["Lower middle", "High", None],
            "is_country": [True, True, False],
        }
    )


def _write_country_year(tmp_path) -> str:
    path = tmp_path / "country_year.parquet"
    _country_year_fixture().to_parquet(path, index=False)
    return str(path)


def test_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(DashboardDataError, match="Lance d'abord"):
        load_country_year(tmp_path / "missing.parquet")


def test_load_country_year_normalizes_types(tmp_path):
    loaded = load_country_year(_write_country_year(tmp_path))

    assert str(loaded["year"].dtype) == "Int64"
    assert loaded.loc[loaded["iso3"] == "MAR", "account_own"].iloc[0] == 0.65
    assert bool(loaded["is_country"].iloc[0]) is True
    assert bool(loaded["is_country"].iloc[-1]) is False


def test_filter_excludes_aggregates(tmp_path):
    loaded = load_country_year(_write_country_year(tmp_path))
    filtered = filter_country_year(
        loaded,
        regions=["MENA"],
        income_groups=["Lower middle"],
        year=2024,
    )

    assert filtered["iso3"].tolist() == ["MAR"]


def test_latest_kpis_from_summary():
    summary = {
        "items": [
            {
                "id": "inclusion_rate",
                "label": "Taux de detention",
                "unit": "%",
                "source": "findex",
                "direction": "up",
                "decimals": 1,
                "latest_year": 2024,
                "latest_value": 70.57,
                "previous_value": 70.25,
                "change": 0.32,
                "n_years": 5,
                "n_obs": 141,
            }
        ]
    }

    latest = latest_kpis(summary)

    assert list(latest.columns) == LATEST_COLUMNS
    assert latest["latest_value"].iloc[0] == 70.57
    assert latest["change"].iloc[0] == 0.32


def test_kpi_series_keeps_global_only():
    values = pd.DataFrame(
        {
            "kpi_id": ["inclusion_rate", "inclusion_rate", "inclusion_rate"],
            "label": ["Inclusion", "Inclusion", "Inclusion"],
            "unit": ["%", "%", "%"],
            "year": [2021, 2024, 2024],
            "dimension": ["global", "global", "region"],
            "dimension_value": ["all", "all", "MENA"],
            "value": [70.25, 70.57, 65.0],
            "n_obs": [120, 141, 10],
        }
    )

    series = kpi_series(values, ["inclusion_rate"])

    assert series["year"].tolist() == [2021, 2024]
    assert series["value"].tolist() == [70.25, 70.57]
    assert set(series["n_obs"]) == {120, 141}


def test_country_ranking_and_snapshot(tmp_path):
    loaded = load_country_year(_write_country_year(tmp_path))
    snapshot = country_snapshot(loaded, 2024, "inclusion_rate")
    ranking = country_ranking(loaded, 2024, "inclusion_rate")

    assert "WLD" not in snapshot["iso3"].tolist()
    assert ranking["iso3"].tolist() == ["FRA", "MAR"]
    assert ranking["value"].tolist() == [0.95, 0.65]


def test_top_bottom_returns_sorted_extremes(tmp_path):
    loaded = load_country_year(_write_country_year(tmp_path))
    snapshot = country_snapshot(loaded, 2024, "inclusion_rate")

    top, bottom = top_bottom(snapshot, n=1)

    assert top["iso3"].iloc[0] == "FRA"
    assert bottom["iso3"].iloc[0] == "MAR"


def test_quality_table():
    quality = {
        "checks": {
            "findex": {"rows": 10, "cols": 3, "score": 1.0, "gate": True, "issues": []},
            "fas": {"rows": 20, "cols": 4, "score": 0.8, "gate": True, "issues": [1]},
        }
    }

    table = quality_table(quality)

    assert table["source"].tolist() == ["findex", "fas"]
    assert table["issues"].tolist() == [0, 1]
    assert table["score"].tolist() == [1.0, 0.8]
