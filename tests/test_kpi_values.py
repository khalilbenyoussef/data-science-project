"""Etape semantic_kpi du pipeline : table kpi_values (fixtures temporaires, aucun reseau)."""
from __future__ import annotations

import math

import duckdb
import pandas as pd
import pytest

from biflow import graph
from biflow.agents.etl import EtlAgent
from biflow.agents.semantic_kpi import SemanticKpiAgent
from biflow.tools.kpi import load_catalog
from biflow.tools.kpi_values import COLUMNS, PEER_METHOD, peer_codes


def _inputs(tmp_path):
    # TUN 2024 = valeur reelle Findex (0.37844486) ; EGY et JOR absents.
    findex = pd.DataFrame({
        "countrynewwb": ["Tunisia", "Morocco", "Algeria", "Morocco"],
        "codewb": ["TUN", "MAR", "DZA", "MAR"],
        "regionwb24_hi": ["MENA"] * 4,
        "incomegroupwb24": ["Lower middle"] * 4,
        "year": [2024, 2024, 2024, 2021],
        "pop_adult": [9e6, 27e6, 31e6, 26e6],
        "group": ["all"] * 4,
        "group2": ["all"] * 4,
        "account_t_d": [0.37844486, 0.44386329, 0.5, 0.443],
        "g20_any": [0.30, None, 0.40, 0.25],
    })
    fas = pd.DataFrame({
        "SERIES_CODE": ["TUN.FA26N.PHTADLT_NUM.A", "MAR.FA26N.PHTADLT_NUM.A"],
        "COUNTRY": ["Tunisia", "Morocco"],
        "2023": [18.0, 21.0],
        "2024": [18.5, None],
    })
    gdp = pd.DataFrame({
        "iso3": ["TUN"], "country": ["Tunisia"], "indicator_code": ["NY.GDP.PCAP.CD"],
        "indicator_name": ["GDP per capita"], "year": [2024], "value": [4000.0],
    })
    paths = {}
    for name, frame in (("findex", findex), ("fas", fas), ("gdp", gdp)):
        paths[name] = str(tmp_path / f"{name}.csv")
        frame.to_csv(paths[name], index=False)
    return paths


@pytest.fixture(scope="module")
def kpi_run(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("kpi_run")
    paths = _inputs(tmp_path)
    cfg = {
        "paths": {"processed": str(tmp_path / "processed"), "quality": str(tmp_path / "quality"),
                  "reports": str(tmp_path / "reports")},
        "llm": {"enabled": False},
        "etl": {"min_year": 2011, "max_year": 2024, "write_csv_copy": False},
        "kpi": {"focus": "TUN", "peers": ["DZA", "EGY", "JOR", "MAR"]},
        "sources": {
            "findex": {"path": paths["findex"], "type": "csv", "indicators": ["account_t_d", "g20_any"]},
            "fas": {"path": paths["fas"], "type": "csv", "series": {"branch_density": "FA26N.PHTADLT_NUM"}},
            "gdp": {"path": paths["gdp"], "type": "csv"},
        },
    }
    state = {"run_id": "kpi_test", "sources": cfg["sources"], "raw_paths": paths}
    state.update(EtlAgent(cfg=cfg, run_id="kpi_test").execute(state))
    report = SemanticKpiAgent(cfg=cfg, run_id="kpi_test").run(state)
    assert report["status"] == "success", report["errors"]
    warehouse = tmp_path / "processed" / "warehouse.duckdb"
    with duckdb.connect(str(warehouse), read_only=True) as con:
        table = con.execute("SELECT * FROM kpi_values").df()
    return report, table, tmp_path / "processed"


def _row(table, kpi_id, iso3, year):
    rows = table[(table.kpi_id == kpi_id) & (table.iso3 == iso3) & (table.year == year)]
    assert len(rows) == 1
    return rows.iloc[0]


def test_kpi_values_table_and_parquet_are_created(kpi_run):
    report, table, processed = kpi_run
    assert list(table.columns) == list(COLUMNS)
    parquet = pd.read_parquet(processed / "kpi_values.parquet")
    assert len(parquet) == len(table) == report["outputs"]["kpi_summary"]["rows"]
    catalog = load_catalog()
    expected = sum(len(k["valid_years"]) for k in catalog["kpis"].values()) * 6  # 5 pays + PEERS
    assert len(table) == expected
    assert not table.duplicated(["kpi_id", "iso3", "year"]).any()
    assert set(table.kpi_id) == set(catalog["kpis"])
    assert set(table.run_id) == {"kpi_test"}
    assert set(table.catalog_version) == {catalog["catalog_version"]}
    assert table.catalog_sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    assert report["outputs"]["kpi_paths"]["table"] == "kpi_values"


def test_tun_2024_account_ownership(kpi_run):
    _, table, _ = kpi_run
    row = _row(table, "account_ownership", "TUN", 2024)
    assert row.value == pytest.approx(37.844486, abs=1e-6)
    assert row.unit == "percent" and row.availability_status == "available"
    assert row.definition_status == "verified"
    unbanked = _row(table, "unbanked_share", "TUN", 2024)
    assert unbanked.value == pytest.approx(100 - 37.844486, abs=1e-6)


def test_missing_values_stay_null_never_zero(kpi_run):
    _, table, _ = kpi_run
    for iso3, year, kpi in (("TUN", 2021, "account_ownership"), ("EGY", 2024, "account_ownership"),
                            ("MAR", 2024, "digital_payment_rate"), ("MAR", 2024, "branch_density"),
                            ("TUN", 2024, "saving_rate")):
        row = _row(table, kpi, iso3, year)
        assert row.value is None or math.isnan(row.value)
        assert row.availability_status == "unavailable"
    assert (table.loc[table.availability_status == "unavailable", "value"].isna()).all()
    # Les valeurs presentes ne sont jamais remplacees par 0
    assert not (table.value == 0).any()


def test_no_provisional_definition_remains(kpi_run):
    _, table, _ = kpi_run
    assert set(table.definition_status) <= {"verified", "verified_metadata", "derived_verified"}
    assert not table.review_reasons.map(lambda r: "provisional_definition" in list(r)).any()


def test_peer_average_partial_and_lists_missing(kpi_run):
    _, table, _ = kpi_run
    row = _row(table, "account_ownership", "PEERS", 2024)
    assert row.value == pytest.approx((44.386329 + 50.0) / 2)
    assert row.peer_status == "partial" and row.reason == "partial_peer_coverage"
    assert list(row.peers_included) == ["DZA", "MAR"]
    assert list(row.missing_peers) == ["EGY", "JOR"]
    assert row.aggregation_method == PEER_METHOD
    assert row.requires_review and "peer_average_unweighted" in list(row.review_reasons)

    single = _row(table, "account_ownership", "PEERS", 2021)
    assert single.value == pytest.approx(44.3) and list(single.missing_peers) == ["DZA", "EGY", "JOR"]

    none = _row(table, "saving_rate", "PEERS", 2024)
    assert math.isnan(none.value) and none.peer_status == "none"
    assert none.availability_status == "unavailable"
    assert list(none.missing_peers) == ["DZA", "EGY", "JOR", "MAR"]


def test_kpi_step_does_not_modify_fact_tables(kpi_run):
    _, _, processed = kpi_run
    with duckdb.connect(str(processed / "warehouse.duckdb"), read_only=True) as con:
        tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
        fact = con.execute("SELECT count(*) FROM fact").fetchone()[0]
    assert {"fact", "country_dim", "country_year", "kpi_values"} <= tables
    assert fact == len(pd.read_parquet(processed / "fact_inclusion.parquet"))


def test_peer_codes_normalize_and_drop_focus():
    assert peer_codes("tun", ["MAR", "TUN", "mar", "KOS"]) == ("TUN", ["MAR", "XKX"])
    with pytest.raises(ValueError):
        peer_codes(None, [])


def test_request_mode_is_unchanged_when_request_present(kpi_run):
    processed = kpi_run[2]
    cfg = {"paths": {"processed": str(processed), "quality": str(processed.parent / "quality"),
                     "reports": str(processed.parent / "reports")}}
    out = SemanticKpiAgent(cfg=cfg, run_id="q").execute(
        {"semantic_kpi_request": {"action": "calculate", "kpi_id": "account_ownership",
                                  "iso3": "TUN", "year": 2024}})
    assert out["semantic_kpi_response"]["result"]["value"] == pytest.approx(37.844486, abs=1e-6)
    assert "kpi_summary" not in out


# --------------------------------------------------------------------------- orchestration
class _Fake:
    def __init__(self, name, calls, passed=True):
        self.name, self.calls, self.passed = name, calls, passed

    def run(self, state):
        self.calls.append(self.name)
        return {"status": "success",
                "outputs": {"quality": {"passed": self.passed}} if self.name == "quality" else {}}


@pytest.fixture(params=["langgraph", "sequential"])
def fakes(request, monkeypatch, tmp_path):
    if request.param == "langgraph" and not graph.LANGGRAPH_AVAILABLE:
        pytest.skip("LangGraph unavailable")
    monkeypatch.setattr(graph, "LANGGRAPH_AVAILABLE", request.param == "langgraph")
    calls, settings = [], {"passed": True}
    for name in graph.STEP_ORDER:
        monkeypatch.setitem(graph.AGENT_CLASSES, name,
                            lambda name=name, **kw: _Fake(name, calls, settings["passed"]))
    return calls, settings, {"paths": {"reports": str(tmp_path)}}


def test_pipeline_order_ends_with_semantic_kpi_after_etl(fakes):
    calls, _, cfg = fakes
    assert graph.STEP_ORDER[-2:] == ["etl", "semantic_kpi"]
    state = graph.run_pipeline(cfg=cfg, use_llm=False)
    assert calls == ["collector", "profiler", "quality", "etl", "semantic_kpi"]
    assert state["status"] == "success"


def test_to_etl_still_stops_before_kpi(fakes):
    calls, _, cfg = fakes
    state = graph.run_pipeline(cfg=cfg, stop="etl", use_llm=False)
    assert calls == ["collector", "profiler", "quality", "etl"]
    assert state["status"] == "success"


def test_quality_fail_stops_before_etl_and_kpi(fakes):
    calls, settings, cfg = fakes
    settings["passed"] = False
    state = graph.run_pipeline(cfg=cfg, use_llm=False)
    assert calls == ["collector", "profiler", "quality"]
    assert state["status"] == "quality_failed"


def test_only_semantic_kpi_is_selectable(fakes):
    calls, _, cfg = fakes
    graph.run_pipeline(cfg=cfg, only="semantic_kpi", use_llm=False)
    assert calls == ["semantic_kpi"]
