"""Auditor : verification independante des KPI (fixtures temporaires, aucun reseau)."""
from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest
import yaml

from biflow.agents.auditor import AuditorAgent
from biflow.agents.etl import EtlAgent
from biflow.agents.quality import QualityAgent
from biflow.agents.semantic_kpi import SemanticKpiAgent
from biflow.config import ROOT
from biflow.tools.snapshots import SnapshotStore
from biflow.utils.io import file_stat, sha256_file
from test_kpi_values import _inputs

FOCUS, PEERS = "TUN", ["DZA", "EGY", "JOR", "MAR"]


def _cfg(base: Path, paths: dict) -> dict:
    return {
        "paths": {"processed": str(base / "processed"), "quality": str(base / "quality"),
                  "reports": str(base / "reports")},
        "llm": {"enabled": False},
        "etl": {"min_year": 2011, "max_year": 2024, "write_csv_copy": False},
        "quality": {"min_rows": 1, "score_threshold": 0.5},
        "kpi": {"focus": FOCUS, "peers": PEERS},
        "snapshots": {"enabled": True, "root": str(base / "snapshots")},
        "auditor": {"tolerance": 1e-9, "min_meaningful_change_pp": 2.0},
        "sources": {
            "findex": {"path": paths["findex"], "type": "csv", "indicators": ["account_t_d", "g20_any"]},
            "fas": {"path": paths["fas"], "type": "csv", "series": {"branch_density": "FA26N.PHTADLT_NUM"}},
            "gdp": {"path": paths["gdp"], "type": "csv", "indicators": ["NY.GDP.PCAP.CD"]},
        },
    }


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Run complet sur petite fixture : snapshot v1 (pending), qualite, ETL, KPI."""
    base = tmp_path_factory.mktemp("audit_world")
    (base / "raw").mkdir()
    paths = _inputs(base / "raw")
    cfg = _cfg(base, paths)
    raw_meta = {name: {"path": path, "sha256": sha256_file(path), **file_stat(path)} for name, path in paths.items()}
    snapshot = SnapshotStore(base / "snapshots").prepare(paths, cfg["sources"], run_id="audit_run")
    state = {"run_id": "audit_run", "sources": cfg["sources"], "raw_paths": paths, "raw_meta": raw_meta,
             "snapshot": snapshot, "snapshot_id": snapshot["snapshot_id"]}
    for agent in (QualityAgent, EtlAgent, SemanticKpiAgent):
        state.update(agent(cfg=cfg, run_id="audit_run").execute(state))
    assert state["quality"]["passed"] is True
    return base, state


@pytest.fixture
def world(built, tmp_path):
    """Copie modifiable (warehouse, rapport qualite, snapshots) ; audit en contexte pipeline."""
    base, state = built
    for folder in ("processed", "quality", "snapshots", "raw"):
        shutil.copytree(base / folder, tmp_path / folder)
    cfg = _cfg(tmp_path, {name: str(tmp_path / "raw" / Path(p).name) for name, p in state["raw_paths"].items()})
    warehouse = tmp_path / "processed" / "warehouse.duckdb"
    quality_path = tmp_path / "quality" / "quality_report.json"
    ctx = {"warehouse_path": str(warehouse), "quality_paths": {"json": str(quality_path)},
           "sources": cfg["sources"], "run_id": "audit_run", "snapshot_id": "v1",
           "staging_paths": {"fact_inclusion": "x"}}

    def run(**cfg_changes):
        cfg.update(cfg_changes)
        return AuditorAgent(cfg=cfg, run_id="audit_run").audit(ctx)

    def sql(statement, params=None):
        with duckdb.connect(str(warehouse)) as con:
            con.execute(statement, params or [])

    def blob(source):
        manifest = json.loads((tmp_path / "snapshots" / "v1" / "manifest.json").read_text(encoding="utf-8"))
        return tmp_path / "snapshots" / manifest["sources"][source]["blob"]

    def edit_json(path, change):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        change(data)
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    return SimpleNamespace(run=run, sql=sql, blob=blob, edit_json=edit_json, ctx=ctx, tmp=tmp_path, cfg=cfg,
                           quality_path=quality_path, lineage_path=warehouse.with_name("lineage.json"))


def _check(result, check_id):
    return next(c for c in result["checks"] if c["check_id"] == check_id)


def test_clean_build_passes_every_recomputation_check(world):
    result = world.run()
    results = {c["check_id"]: c["result"] for c in result["checks"]}
    assert {k: v for k, v in results.items() if k[0] in "AB"} == {k: "pass" for k in results if k[0] in "AB"}
    assert len([k for k in results if k[0] in "AB"]) == 14
    assert result["recomputed"][("account_ownership", "TUN", 2024)]["value"] == pytest.approx(37.844486)


def test_tampered_value_is_reported_with_expected_and_found(world):
    run, sql, tmp_path = world.run, world.sql, world.tmp
    sql("UPDATE kpi_values SET value = value + 1e-6 WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024")
    check = _check(run(), "A1_recomputed_values")
    assert check["result"] == "fail"
    row, = check["affected_rows"]
    assert (row["kpi_id"], row["iso3"], row["year"]) == ("account_ownership", "TUN", 2024)
    assert row["found"] - row["expected"] == pytest.approx(1e-6)


def test_zero_instead_of_null_is_detected(world):
    run, sql, tmp_path = world.run, world.sql, world.tmp
    sql("UPDATE kpi_values SET value = 0 WHERE kpi_id='account_ownership' AND iso3='EGY' AND year=2024")
    check = _check(run(), "A2_unavailable_rows_are_null")
    assert check["result"] == "fail" and check["affected_rows"][0]["found"] == 0


def test_hidden_value_published_as_null_is_detected(world):
    run, sql, tmp_path = world.run, world.sql, world.tmp
    sql("UPDATE kpi_values SET value = NULL, availability_status='unavailable' "
        "WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024")
    check = _check(run(), "A2_unavailable_rows_are_null")
    assert check["result"] == "fail" and check["affected_rows"][0]["expected"] == pytest.approx(37.844486)


def test_peer_mean_and_peer_lists_are_recomputed(world):
    run, sql, tmp_path = world.run, world.sql, world.tmp
    sql("UPDATE kpi_values SET value = 99, missing_peers = ['EGY'] "
        "WHERE kpi_id='account_ownership' AND iso3='PEERS' AND year=2024")
    check = _check(run(), "A3_peers_recomputed")
    assert check["result"] == "fail"
    assert "missing_peers" in check["affected_rows"][0]["reason"] and "moyenne" in check["affected_rows"][0]["reason"]


def test_missing_and_unexpected_rows_are_detected(world):
    run, sql, tmp_path = world.run, world.sql, world.tmp
    sql("DELETE FROM kpi_values WHERE kpi_id='branch_density' AND iso3='JOR' AND year=2015")
    sql("INSERT INTO kpi_values SELECT * REPLACE ('FRA' AS iso3) FROM kpi_values "
        "WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024")
    reasons = {(r["iso3"], r["reason"]) for r in _check(run(), "A4_row_completeness")["affected_rows"]}
    assert reasons == {("JOR", "ligne manquante"), ("FRA", "ligne inattendue")}


def test_fact_differing_from_raw_file_is_detected(world):
    run, sql, tmp_path = world.run, world.sql, world.tmp
    blob = world.blob("findex")
    blob.write_text(blob.read_text(encoding="utf-8").replace("0.37844486", "0.37844487"), encoding="utf-8")
    check = _check(run(), "A5_raw_to_fact")
    assert check["result"] == "fail"
    row = check["affected_rows"][0]
    assert row["fact_key"][:4] == ["TUN", 2024, "findex", "account_t_d"]
    assert row["expected"] == 0.37844487 and row["found"] == 0.37844486


def test_scale_error_is_not_hidden_by_a_factor_of_100(world):
    run, sql, tmp_path = world.run, world.sql, world.tmp
    # Brut en pourcentage (37.844486) alors que fact contient la fraction : echec
    blob = world.blob("findex")
    blob.write_text(blob.read_text(encoding="utf-8").replace("0.37844486", "37.844486"), encoding="utf-8")
    assert _check(run(), "A5_raw_to_fact")["result"] == "fail"


def test_unsupported_catalog_formula_fails(world):
    run, sql, tmp_path = world.run, world.sql, world.tmp
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


# --------------------------------------------------------------------------- B : coherence
def test_clean_build_verdict_has_only_caveat_warnings(world):
    result = world.run()
    by_id = {c["check_id"]: c for c in result["checks"]}
    assert not [c for c in result["checks"] if c["result"] == "fail"]
    assert by_id["C2_partial_peer_coverage"]["result"] == "warn"  # EGY et JOR absents
    noise = by_id["C4_within_survey_noise"]
    assert noise["affects_publication"] is False
    assert {"kpi_id": "account_ownership", "iso3": "MAR", "year": 2024, "from_year": 2021,
            "change_pp": 0.09} in noise["affected_rows"]


@pytest.mark.parametrize("statement,check_id", [
    ("UPDATE kpi_values SET unit='fraction' WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024",
     "B1_one_unit_per_kpi"),
    ("UPDATE kpi_values SET value=150 WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024",
     "B2_value_ranges"),
    ("INSERT INTO kpi_values SELECT * REPLACE ('WLD' AS iso3) FROM kpi_values "
     "WHERE kpi_id='account_ownership' AND iso3='TUN' AND year=2024", "B3_country_entities_only"),
    ("UPDATE kpi_values SET missing_peers=['EGY','JOR','FRA'] WHERE iso3='PEERS' AND kpi_id='account_ownership' "
     "AND year=2024", "B4_peers_are_configured_peers"),
    ("UPDATE kpi_values SET snapshot_id='v9' WHERE kpi_id='branch_density' AND iso3='TUN' AND year=2023",
     "B5_snapshot_and_run_ids"),
    ("UPDATE kpi_values SET run_id='other_run' WHERE iso3='MAR'", "B5_snapshot_and_run_ids"),
    ("UPDATE fact SET value = value + 0.5 WHERE source='gdp'", "B7_warehouse_content_digest"),
    ("UPDATE country_dim SET region='X' WHERE iso3='TUN'", "B7_warehouse_content_digest"),
])
def test_consistency_faults_fail_the_right_check(world, statement, check_id):
    world.sql(statement)
    check = _check(world.run(), check_id)
    assert check["result"] == "fail" and check["affected_rows"]


@pytest.mark.parametrize("artifact,change,check_id", [
    ("quality", lambda q: q["inputs"]["findex"].update(sha256="0" * 64), "B6_source_hashes"),
    ("lineage", lambda l: l["inputs"]["fas"].update(sha256="1" * 64), "B6_source_hashes"),
    ("quality", lambda q: q.update(snapshot_id="v2"), "B5_snapshot_and_run_ids"),
    ("quality", lambda q: q.update(run_id="older_run"), "B5_snapshot_and_run_ids"),
    ("lineage", lambda l: l.update(snapshot_id=None), "B5_snapshot_and_run_ids"),
    ("quality", lambda q: q.update(passed=False), "B9_quality_gate"),
])
def test_traceability_faults_fail_the_right_check(world, artifact, change, check_id):
    world.edit_json(world.quality_path if artifact == "quality" else world.lineage_path, change)
    assert _check(world.run(), check_id)["result"] == "fail"


def test_tampered_snapshot_blob_breaks_hash_chain(world):
    blob = world.blob("gdp")
    blob.write_text(blob.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    row, = _check(world.run(), "B6_source_hashes")["affected_rows"]
    assert row["source"] == "gdp" and row["found"]["blob_content"] != row["found"]["blob_name"]


def test_snapshot_must_be_the_pending_candidate_of_this_run(world):
    world.edit_json(world.tmp / "snapshots" / "index.json",
                    lambda index: index["snapshots"][0].update(run_id="another_run"))
    assert _check(world.run(), "B5_snapshot_and_run_ids")["result"] == "fail"


@pytest.mark.parametrize("change", [
    lambda c: c["kpis"]["saving_rate"]["verification"].update(status="provisional"),
    lambda c: c["kpis"]["branch_density"]["verification"].update(evidence=["unknown_ref"]),
    lambda c: c.update(updated_on="2026-12-31"),  # catalogue modifie : hash different de kpi_values
])
def test_catalog_faults_fail(world, change):
    catalog = yaml.safe_load((ROOT / "config" / "kpi_catalog.v1.yaml").read_text(encoding="utf-8"))
    change(catalog)
    path = world.tmp / "catalog.yaml"
    path.write_text(yaml.safe_dump(catalog), encoding="utf-8")
    assert _check(world.run(auditor={"catalog": str(path)}), "B8_catalog_definitions")["result"] == "fail"


def test_unverified_findex_code_fails_catalog_check(world, monkeypatch):
    monkeypatch.setattr("biflow.tools.audit_checks.FINDEX_UNVERIFIED", frozenset({"g20_any"}))
    reasons = [r["reason"] for r in _check(world.run(), "B8_catalog_definitions")["affected_rows"]]
    assert reasons == ["code non verifie g20_any"]


def test_quality_diagnostic_on_an_input_is_a_caveat(world):
    diagnostic = {"source": "findex", "code": "test", "iso3": "TUN", "year": 2024,
                  "indicator_code": "account_t_d", "reason": "valeur a revoir"}
    world.edit_json(world.quality_path, lambda q: q["diagnostics"].append(diagnostic))
    check = _check(world.run(), "C3_input_quality_findings")
    assert check["result"] == "warn"
    assert {r["kpi_id"] for r in check["affected_rows"]} == {"account_ownership", "unbanked_share"}


def test_partial_wave_caveat_only_for_survey_kpis(world):
    world.sql("UPDATE kpi_values SET value=44 WHERE iso3='MAR' AND year=2022 "
              "AND kpi_id IN ('account_ownership', 'branch_density')")
    rows = _check(world.run(), "C1_partial_survey_wave")["affected_rows"]
    assert rows == [{"kpi_id": "account_ownership", "iso3": "MAR", "year": 2022}]


# --------------------------------------------------------------------------- C : publication
def _statuses(world):
    with duckdb.connect(str(world.tmp / "processed" / "warehouse.duckdb"), read_only=True) as con:
        return {(k, i, y): st for k, i, y, st in con.execute(
            "SELECT kpi_id, iso3, year, publication_status FROM kpi_values").fetchall()}


def _execute(world):
    return AuditorAgent(cfg=world.cfg, run_id="audit_run").execute(world.ctx)["audit"]


def test_kpi_step_writes_not_evaluated(built):
    base, _ = built
    with duckdb.connect(str(base / "processed" / "warehouse.duckdb"), read_only=True) as con:
        assert con.execute("SELECT DISTINCT publication_status FROM kpi_values").fetchall() == [("not_evaluated",)]


def test_clean_audit_approves_rows_and_notes_partial_peers(world):
    audit = _execute(world)
    statuses = _statuses(world)
    assert audit["verdict"] == "pass_with_warnings" and "blocked" not in statuses.values()
    assert statuses[("account_ownership", "TUN", 2024)] == "approved"
    assert statuses[("account_ownership", "EGY", 2024)] == "approved"  # NULL reel : publie "indisponible"
    assert statuses[("account_ownership", "PEERS", 2024)] == "approved_with_review_note"  # pairs partiels
    assert audit["publication"] == {s: list(statuses.values()).count(s)
                                    for s in ("approved", "approved_with_review_note", "blocked")}
    import pandas as pd
    parquet = pd.read_parquet(world.tmp / "processed" / "kpi_values.parquet")
    assert set(parquet.publication_status) == set(statuses.values())


def test_failing_row_is_blocked_and_peers_row_inherits(world):
    world.sql("UPDATE kpi_values SET value = value + 1 WHERE kpi_id='account_ownership' AND iso3='MAR' AND year=2024")
    audit = _execute(world)
    statuses = _statuses(world)
    assert audit["verdict"] == "fail"
    assert statuses[("account_ownership", "MAR", 2024)] == "blocked"
    assert statuses[("account_ownership", "PEERS", 2024)] == "blocked"  # MAR est un pair inclus
    assert statuses[("account_ownership", "TUN", 2024)] == "approved"
    assert statuses[("account_ownership", "MAR", 2021)] != "blocked"


def test_run_level_failure_blocks_every_row(world):
    world.edit_json(world.quality_path, lambda q: q.update(passed=False))
    audit = _execute(world)
    assert audit["verdict"] == "fail" and set(_statuses(world).values()) == {"blocked"}


def test_survey_noise_does_not_change_publication(world):
    _execute(world)
    # MAR 2021 -> 2024 : +0.09 pt, dans le bruit d'enquete, mais aucune note de revue pour la valeur
    assert _statuses(world)[("account_ownership", "MAR", 2024)] == "approved"
