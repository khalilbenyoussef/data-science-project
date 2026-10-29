"""Auditor : verification independante des KPI (fixtures temporaires, aucun reseau)."""
from __future__ import annotations

import ast
import shutil
from pathlib import Path

import duckdb
import pytest
import yaml

from biflow.agents.auditor import AuditorAgent
from biflow.agents.etl import EtlAgent
from biflow.agents.semantic_kpi import SemanticKpiAgent
from biflow.config import ROOT
from test_kpi_values import _inputs

FOCUS, PEERS = "TUN", ["DZA", "EGY", "JOR", "MAR"]


def _cfg(base: Path, paths: dict) -> dict:
    return {
        "paths": {"processed": str(base / "processed"), "quality": str(base / "quality"),
                  "reports": str(base / "reports")},
        "llm": {"enabled": False},
        "etl": {"min_year": 2011, "max_year": 2024, "write_csv_copy": False},
        "kpi": {"focus": FOCUS, "peers": PEERS},
        "snapshots": {"enabled": False, "root": str(base / "snapshots")},
        "auditor": {"tolerance": 1e-9},
        "sources": {
            "findex": {"path": paths["findex"], "type": "csv", "indicators": ["account_t_d", "g20_any"]},
            "fas": {"path": paths["fas"], "type": "csv", "series": {"branch_density": "FA26N.PHTADLT_NUM"}},
            "gdp": {"path": paths["gdp"], "type": "csv"},
        },
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """ETL + etape KPI reelles sur une petite fixture, construites une fois."""
    base = tmp_path_factory.mktemp("audit_world")
    paths = _inputs(base)
    cfg = _cfg(base, paths)
    state = {"run_id": "audit_run", "sources": cfg["sources"], "raw_paths": paths}
    state.update(EtlAgent(cfg=cfg, run_id="audit_run").execute(state))
    state.update(SemanticKpiAgent(cfg=cfg, run_id="audit_run").execute(state))
    return base, paths


@pytest.fixture
def world(built, tmp_path):
    """Copie modifiable du warehouse et des fichiers bruts."""
    base, paths = built
    shutil.copytree(base / "processed", tmp_path / "processed")
    raw = {}
    for name, path in paths.items():
        raw[name] = str(tmp_path / Path(path).name)
        shutil.copyfile(path, raw[name])
    lineage = (tmp_path / "processed" / "lineage.json")
    text = lineage.read_text(encoding="utf-8")
    for name, path in paths.items():
        text = text.replace(str(Path(path)).replace("\\", "\\\\"), raw[name].replace("\\", "\\\\"))
    lineage.write_text(text, encoding="utf-8")
    cfg = _cfg(tmp_path, raw)
    warehouse = tmp_path / "processed" / "warehouse.duckdb"

    def run(**cfg_changes):
        cfg.update(cfg_changes)
        agent = AuditorAgent(cfg=cfg, run_id="audit_run")
        return agent.audit({"warehouse_path": str(warehouse), "sources": cfg["sources"],
                            "run_id": "audit_run"})

    def sql(statement, params=None):
        with duckdb.connect(str(warehouse)) as con:
            con.execute(statement, params or [])

    return run, sql, raw, tmp_path


def _check(result, check_id):
    return next(c for c in result["checks"] if c["check_id"] == check_id)


def test_clean_build_passes_every_recomputation_check(world):
    run, _, _, _ = world
    result = run()
    assert {c["check_id"]: c["result"] for c in result["checks"]} == {
        "A1_recomputed_values": "pass", "A2_unavailable_rows_are_null": "pass",
        "A3_peers_recomputed": "pass", "A4_row_completeness": "pass", "A5_raw_to_fact": "pass"}
    assert result["recomputed"][("account_ownership", "TUN", 2024)]["value"] == pytest.approx(37.844486)


def test_tampered_value_is_reported_with_expected_and_found(world):
    run, sql, _, _ = world
    sql("UPDATE kpi_values SET value = value + 1e-6 WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024")
    check = _check(run(), "A1_recomputed_values")
    assert check["result"] == "fail"
    row, = check["affected_rows"]
    assert (row["kpi_id"], row["iso3"], row["year"]) == ("account_ownership", "TUN", 2024)
    assert row["found"] - row["expected"] == pytest.approx(1e-6)


def test_zero_instead_of_null_is_detected(world):
    run, sql, _, _ = world
    sql("UPDATE kpi_values SET value = 0 WHERE kpi_id='account_ownership' AND iso3='EGY' AND year=2024")
    check = _check(run(), "A2_unavailable_rows_are_null")
    assert check["result"] == "fail" and check["affected_rows"][0]["found"] == 0


def test_hidden_value_published_as_null_is_detected(world):
    run, sql, _, _ = world
    sql("UPDATE kpi_values SET value = NULL, availability_status='unavailable' "
        "WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024")
    check = _check(run(), "A2_unavailable_rows_are_null")
    assert check["result"] == "fail" and check["affected_rows"][0]["expected"] == pytest.approx(37.844486)


def test_peer_mean_and_peer_lists_are_recomputed(world):
    run, sql, _, _ = world
    sql("UPDATE kpi_values SET value = 99, missing_peers = ['EGY'] "
        "WHERE kpi_id='account_ownership' AND iso3='PEERS' AND year=2024")
    check = _check(run(), "A3_peers_recomputed")
    assert check["result"] == "fail"
    assert "missing_peers" in check["affected_rows"][0]["reason"] and "moyenne" in check["affected_rows"][0]["reason"]


def test_missing_and_unexpected_rows_are_detected(world):
    run, sql, _, _ = world
    sql("DELETE FROM kpi_values WHERE kpi_id='branch_density' AND iso3='JOR' AND year=2015")
    sql("INSERT INTO kpi_values SELECT * REPLACE ('FRA' AS iso3) FROM kpi_values "
        "WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024")
    reasons = {(r["iso3"], r["reason"]) for r in _check(run(), "A4_row_completeness")["affected_rows"]}
    assert reasons == {("JOR", "ligne manquante"), ("FRA", "ligne inattendue")}


def test_fact_differing_from_raw_file_is_detected(world):
    run, _, raw, _ = world
    text = Path(raw["findex"]).read_text(encoding="utf-8").replace("0.37844486", "0.37844487")
    Path(raw["findex"]).write_text(text, encoding="utf-8")
    check = _check(run(), "A5_raw_to_fact")
    assert check["result"] == "fail"
    row = check["affected_rows"][0]
    assert row["fact_key"][:4] == ["TUN", 2024, "findex", "account_t_d"]
    assert row["expected"] == 0.37844487 and row["found"] == 0.37844486


def test_scale_error_is_not_hidden_by_a_factor_of_100(world):
    run, _, raw, _ = world
    # Brut en pourcentage (37.844486) alors que fact contient la fraction : echec
    text = Path(raw["findex"]).read_text(encoding="utf-8").replace("0.37844486", "37.844486")
    Path(raw["findex"]).write_text(text, encoding="utf-8")
    assert _check(run(), "A5_raw_to_fact")["result"] == "fail"


def test_unsupported_catalog_formula_fails(world):
    run, _, _, tmp_path = world
    catalog = yaml.safe_load((ROOT / "config" / "kpi_catalog.v1.yaml").read_text(encoding="utf-8"))
    catalog["kpis"]["account_ownership"]["formula"]["from_fact"] = "__import__('os').getcwd()"
    path = tmp_path / "catalog.yaml"
    path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    check = _check(run(auditor={"catalog": str(path)}), "A1_recomputed_values")
    assert check["result"] == "fail" and "formule non reconnue" in check["affected_rows"][0]["reason"]


def test_audit_modules_never_import_kpi_calculation_code():
    forbidden = {"biflow.tools.kpi", "biflow.tools.kpi_values", "biflow.tools.semantic_kpi",
                 "biflow.tools.kpi_provenance", "biflow.agents.semantic_kpi"}
    for module in ("src/biflow/tools/audit_checks.py", "src/biflow/agents/auditor.py"):
        tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
        imported = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        imported |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        assert not imported & forbidden, (module, imported & forbidden)
