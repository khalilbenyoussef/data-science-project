"""Liaison KPI <-> contenu du warehouse (empreinte des tables, pas du fichier)."""
from __future__ import annotations

import json

import duckdb
import pytest

from biflow.tools import kpi_provenance
from biflow.tools.kpi import KpiCalculator
from biflow.tools.kpi_provenance import CONTENT_TABLES, warehouse_content_digest
from test_kpi_values import kpi_run  # noqa: F401 - ETL + etape KPI reelles sur fixture


def _lineage(processed):
    return json.loads((processed / "lineage.json").read_text(encoding="utf-8"))


def _calculate(processed):
    return KpiCalculator(processed / "warehouse.duckdb").calculate("TUN", 2024, "account_ownership")


def test_etl_records_content_digest_of_fact_country_year_and_country_dim(kpi_run):
    _, _, processed = kpi_run
    outputs = _lineage(processed)["outputs"]
    assert outputs["warehouse_content_tables"] == list(CONTENT_TABLES) == ["fact", "country_year", "country_dim"]
    with duckdb.connect(str(processed / "warehouse.duckdb"), read_only=True) as con:
        # kpi_values a ete ecrite apres l'ETL : l'empreinte du contenu est inchangee
        assert "kpi_values" in {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        assert warehouse_content_digest(con) == outputs["warehouse_content_sha256"]


def test_matching_content_removes_binding_review_reason(kpi_run):
    _, table, processed = kpi_run
    result = _calculate(processed)
    issues = result.provenance.issues
    assert "warehouse_content_binding_unverified" not in issues
    assert "warehouse_content_mismatch" not in issues
    assert result.provenance.warehouse_content_sha256 == _lineage(processed)["outputs"]["warehouse_content_sha256"]
    assert not table.review_reasons.map(lambda r: "warehouse_content_binding_unverified" in list(r)).any()


@pytest.mark.parametrize("change", [
    "UPDATE fact SET value = value + 0.001 WHERE iso3 = 'MAR'",
    "UPDATE country_year SET gdp_pc = 1 WHERE iso3 = 'TUN'",
    "UPDATE country_dim SET region = 'Changed' WHERE iso3 = 'MAR'",
    "INSERT INTO country_dim SELECT 'ZZZ', 'Test', NULL, NULL, false, false",
])
def test_changed_table_content_is_a_mismatch(kpi_run, tmp_path, change):
    _, _, processed = kpi_run
    copy = tmp_path / "processed"
    copy.mkdir()
    (copy / "warehouse.duckdb").write_bytes((processed / "warehouse.duckdb").read_bytes())
    lineage = _lineage(processed)
    lineage["outputs"]["warehouse"] = str(copy / "warehouse.duckdb")
    (copy / "lineage.json").write_text(json.dumps(lineage), encoding="utf-8")
    with duckdb.connect(str(copy / "warehouse.duckdb")) as con:
        con.execute(change)
    result = _calculate(copy)
    assert "warehouse_content_mismatch" in result.review_reasons and result.requires_review
    assert result.value == pytest.approx(37.844486, abs=1e-6)  # valeur jamais modifiee


def test_digest_ignores_insertion_order_but_not_values(tmp_path):
    def digest(rows):
        path = tmp_path / f"w{len(list(tmp_path.iterdir()))}.duckdb"
        with duckdb.connect(str(path)) as con:
            con.execute("CREATE TABLE fact (iso3 VARCHAR, year INTEGER, value DOUBLE)")
            con.execute("CREATE TABLE country_year (iso3 VARCHAR, year INTEGER, x DOUBLE)")
            con.executemany("INSERT INTO fact VALUES (?, ?, ?)", rows)
            con.execute("INSERT INTO country_year VALUES ('TUN', 2024, NULL)")
            con.execute("CREATE TABLE country_dim AS SELECT 'TUN' AS iso3, true AS is_country")
            return warehouse_content_digest(con)

    rows = [("TUN", 2024, 0.5), ("MAR", 2024, None), ("DZA", 2021, 0.25)]
    assert digest(rows) == digest(list(reversed(rows)))
    assert digest(rows) != digest(rows[:2] + [("DZA", 2021, 0.26)])


def test_older_lineage_keeps_its_recorded_table_list(kpi_run, tmp_path):
    _, _, processed = kpi_run
    with duckdb.connect(str(processed / "warehouse.duckdb"), read_only=True) as con:
        two_tables = warehouse_content_digest(con, ("fact", "country_year"))
    lineage = _lineage(processed)
    lineage["outputs"].update(warehouse_content_sha256=two_tables,
                              warehouse_content_tables=["fact", "country_year"])
    path = tmp_path / "lineage.json"
    path.write_text(json.dumps(lineage), encoding="utf-8")
    result = KpiCalculator(processed / "warehouse.duckdb", lineage_path=path).calculate(
        "TUN", 2024, "account_ownership")
    assert "warehouse_content_mismatch" not in result.review_reasons


def test_unreadable_recorded_tables_require_review(kpi_run, tmp_path, monkeypatch):
    _, _, processed = kpi_run
    lineage = _lineage(processed)
    lineage["outputs"]["warehouse_content_tables"] = ["missing_table"]
    path = tmp_path / "lineage.json"
    path.write_text(json.dumps(lineage), encoding="utf-8")
    monkeypatch.setattr(kpi_provenance, "_CONTENT_CACHE", {})
    result = KpiCalculator(processed / "warehouse.duckdb", lineage_path=path).calculate(
        "TUN", 2024, "account_ownership")
    assert "warehouse_content_unreadable" in result.review_reasons
