"""Read-only warehouse reader: whitelisted series only, nulls never zero-filled."""
import duckdb
import pytest

from biflow.tools.warehouse_reader import (
    UnknownSeriesError, WarehouseReadError, WarehouseReader,
)


@pytest.fixture
def warehouse(tmp_path):
    path = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute(
            "CREATE TABLE country_dim (iso3 VARCHAR, country VARCHAR, region VARCHAR, "
            "income_group VARCHAR, is_country BOOLEAN, is_aggregate BOOLEAN)"
        )
        con.execute("INSERT INTO country_dim VALUES ('TUN','Tunisia','MENA','LMIC',true,false)")
        con.execute(
            "CREATE TABLE country_year (iso3 VARCHAR, year INTEGER, gdp_pc DOUBLE)"
        )
        con.execute("INSERT INTO country_year VALUES ('TUN', 2024, 4213.0)")
        con.execute(
            "CREATE TABLE fact (iso3 VARCHAR, year INTEGER, source VARCHAR, "
            "indicator_code VARCHAR, dimension VARCHAR, dimension_value VARCHAR, "
            "value DOUBLE, unit VARCHAR)"
        )
        con.executemany("INSERT INTO fact VALUES (?, ?, ?, ?, ?, ?, ?, ?)", [
            ("TUN", 2017, "fas", "atm_density", "bank_type", "commercial_banks",
             30.0, "per_100k_adults"),
            ("TUN", 2023, "fas", "atm_density", "bank_type", "commercial_banks",
             None, "per_100k_adults"),
            ("TUN", 2024, "fas", "atm_density", "bank_type", "commercial_banks",
             35.44, "per_100k_adults"),
            ("TUN", 2018, "fas", "depositors_per_1k", "bank_type", "commercial_banks",
             1063.3, "per_1k_adults"),
            ("TUN", 2024, "findex", "account_t_d", "gender", "women", 0.266, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "gender", "men", 0.496, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "urbanicity", "rural", 0.302, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "urbanicity", "urban", 0.467, "fraction"),
            ("TUN", 2024, "findex", "account_t_d", "all", "all", 0.3784, "fraction"),
        ])
    return path


@pytest.fixture
def reader(warehouse):
    return WarehouseReader(warehouse)


def test_series_keeps_observed_years_and_nulls(reader):
    points = reader.series("atm_per_100k", "TUN")
    assert [point["year"] for point in points] == [2017, 2023, 2024]
    assert points[0]["value"] == pytest.approx(30.0)
    assert points[1]["status"] == "unavailable" and points[1]["value"] is None
    assert points[2]["value"] == pytest.approx(35.44)


def test_latest_upto_never_takes_a_later_wave(reader):
    assert reader.latest_upto("atm_per_100k", "TUN", 2020)["year"] == 2017
    assert reader.latest_upto("atm_per_100k", "TUN", 2024)["value"] == pytest.approx(35.44)
    stopped = reader.latest("depositors_per_1k", "TUN")
    assert stopped["year"] == 2018 and stopped["value"] == pytest.approx(1063.3)
    assert reader.value("atm_per_100k", "TUN", 2022)["status"] == "unavailable"


def test_subgroups_convert_fractions_and_exclude_total(reader):
    rows = reader.subgroups("TUN", "account_t_d", "gender", 2024)
    assert {row["group"]: row["value"] for row in rows} == {
        "men": pytest.approx(49.6), "women": pytest.approx(26.6),
    }
    assert reader.subgroups("TUN", "account_t_d", "urbanicity", 2024)[1]["value"] == pytest.approx(
        46.7
    )


def test_whitelists_reject_unknown_series_and_dimensions(reader):
    with pytest.raises(UnknownSeriesError):
        reader.series("password_table", "TUN")
    with pytest.raises(UnknownSeriesError):
        reader.subgroups("TUN", "account_t_d", "religion", 2024)
    with pytest.raises(UnknownSeriesError):
        reader.country_year_value("gdp_pc; DROP TABLE fact", "TUN", 2024)


def test_connection_is_read_only(reader):
    with pytest.raises(duckdb.Error):
        with reader._connect() as con:
            con.execute("INSERT INTO fact (iso3) VALUES ('TUN')")


def test_summary_and_country_metadata(reader):
    summary = reader.summary()
    assert summary["fact_rows"] == 9
    assert summary["by_source"] == {"fas": 4, "findex": 5}
    assert reader.country_meta("TUN") == {
        "iso3": "TUN", "name": "Tunisia", "region": "MENA", "income_group": "LMIC",
    }
    assert reader.country_year_value("gdp_pc", "TUN", 2024)["value"] == pytest.approx(4213.0)
    assert reader.country_year_value("gdp_pc", "TUN", 2023)["value"] is None


def test_missing_warehouse_raises(tmp_path):
    with pytest.raises(WarehouseReadError):
        WarehouseReader(tmp_path / "missing.duckdb")
