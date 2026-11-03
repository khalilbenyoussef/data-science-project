"""Auditor : verification independante des KPI (fixtures temporaires, aucun reseau)."""
from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pandas as pd
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
                  "reports": str(base / "reports"), "audit": str(base / "audit")},
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
    findex = pd.read_csv(paths["findex"])
    extra = []
    for iso3, year, men, women in (("TUN", 2024, 0.4957, 0.2661), ("TUN", 2021, 0.4514, 0.2875),
                                   ("MAR", 2024, 0.55, 0.35), ("MAR", 2021, 0.56, 0.33)):
        same_year = findex[(findex.codewb == iso3) & (findex.year == year)]
        base_row = (same_year if len(same_year) else findex[findex.codewb == iso3]).iloc[0].to_dict()
        for group2, value in (("men", men), ("women", women)):
            extra.append({**base_row, "year": year, "group": "gender", "group2": group2,
                          "account_t_d": value, "g20_any": None})
    extra = pd.DataFrame(extra).astype({"g20_any": float})
    pd.concat([findex, extra], ignore_index=True).to_csv(paths["findex"], index=False)
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
    assert len([k for k in results if k[0] in "AB"]) == 15  # A1-A6, B1-B9
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
    # Sans dimension, le diagnostic vise tous les faits account_t_d (sous-groupes inclus) :
    # catalogue 1.4.0, les KPI par sous-groupe (genre, seul present ici) lisent ces faits
    assert {r["kpi_id"] for r in check["affected_rows"]} == {
        "account_ownership", "unbanked_share", "gender_gap",
        "account_ownership_men", "account_ownership_women"}


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


# --------------------------------------------------------------------------- D : explications
def _explanations(world):
    _execute(world)
    with duckdb.connect(str(world.tmp / "processed" / "warehouse.duckdb"), read_only=True) as con:
        stored = {(k, i, y): json.loads(doc) for k, i, y, doc in con.execute(
            "SELECT kpi_id, iso3, year, explanation FROM kpi_explanations").fetchall()}
        rows = con.execute("SELECT count(*) FROM kpi_values").fetchone()[0]
    return stored, rows


def test_one_explanation_per_row_in_table_and_jsonl(world):
    stored, rows = _explanations(world)
    assert len(stored) == rows
    path = world.tmp / "audit" / "explanations.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == rows
    assert {(d["kpi_id"], d["iso3"], d["year"]) for d in map(json.loads, lines)} == set(stored)


def test_explanation_traces_value_to_raw_record(world):
    stored, _ = _explanations(world)
    e = stored[("account_ownership", "TUN", 2024)]
    assert e["value"] == pytest.approx(37.844486) and e["unit"] == "percent"
    assert e["formula"] == "100 * value" and "x 100" in e["transformation"]
    assert e["catalog_version"] == "1.4.0" and e["publication_status"] == "approved"
    item, = e["inputs"]
    assert item["fact_value"] == 0.37844486
    raw = item["raw"]
    assert raw["raw_value_text"] == "0.37844486" and raw["column"] == "account_t_d"
    assert raw["record_key"] == {"codewb": "TUN", "year": 2024, "group": "all", "group2": "all"}
    manifest = json.loads((world.tmp / "snapshots" / "v1" / "manifest.json").read_text(encoding="utf-8"))
    assert raw["sha256"] == manifest["sources"]["findex"]["sha256"] and raw["snapshot_id"] == "v1"
    fas = stored[("branch_density", "TUN", 2024)]["inputs"][0]["raw"]
    assert fas["record_key"]["SERIES_CODE"] == "TUN.FA26N.PHTADLT_NUM.A" and fas["column"] == "2024"


def test_dependencies_for_gaps_unbanked_and_peers(world):
    stored, _ = _explanations(world)
    gap = stored[("gender_gap", "TUN", 2024)]
    assert [(d["label"], round(d["value"], 2)) for d in gap["dependencies"]] == [("men", 49.57), ("women", 26.61)]
    assert gap["value"] == pytest.approx(49.57 - 26.61)
    unbanked = stored[("unbanked_share", "TUN", 2024)]
    assert unbanked["dependencies"][0]["kpi_id"] == "account_ownership"
    assert unbanked["dependencies"][0]["value"] == pytest.approx(37.844486)
    peers = stored[("account_ownership", "PEERS", 2024)]
    assert [(d["iso3"], d["included"]) for d in peers["dependencies"]] == [
        ("DZA", True), ("MAR", True), ("EGY", False), ("JOR", False)]
    assert peers["publication_status"] == "approved_with_review_note"
    missing = stored[("account_ownership", "EGY", 2024)]
    assert missing["value"] is None and missing["inputs"][0]["status"] == "missing_observation"


def test_gap_change_decomposes_into_subgroup_changes(world):
    from biflow.tools.audit_explain import explain_change
    stored, _ = _explanations(world)
    change = explain_change(stored[("gender_gap", "TUN", 2021)], stored[("gender_gap", "TUN", 2024)])
    assert change["kind"] == "years" and round(change["delta"], 2) == 6.57
    men, women = change["components"]
    assert (men["label"], round(men["delta"], 2), women["label"], round(women["delta"], 2)) == (
        "men", 4.43, "women", -2.14)
    assert change["delta"] == pytest.approx(men["contribution"] + women["contribution"])
    assert change["within_survey_noise"] is False


def test_peer_change_lists_each_peer_contribution(world):
    from biflow.tools.audit_explain import explain_change
    stored, _ = _explanations(world)
    change = explain_change(stored[("gender_gap", "PEERS", 2021)], stored[("gender_gap", "PEERS", 2024)])
    assert change["comparable"] and [c["label"] for c in change["components"]] == ["MAR"]
    assert change["delta"] == pytest.approx(sum(c["contribution"] for c in change["components"]))
    changed = explain_change(stored[("account_ownership", "PEERS", 2021)],
                             stored[("account_ownership", "PEERS", 2024)])
    assert changed["comparable"] is False and "pairs differents" in changed["reason"]
    noise = explain_change(stored[("account_ownership", "MAR", 2021)], stored[("account_ownership", "MAR", 2024)])
    assert noise["within_survey_noise"] is True


def test_decision_log_explains_each_step(world):
    audit = _execute(world)
    steps = {entry["step"]: entry for entry in audit["decision_log"]}
    assert list(steps) == ["collector", "snapshot", "quality", "etl", "semantic_kpi", "auditor"]
    assert "gate PASS" in steps["quality"]["decision"]
    assert steps["etl"]["decision"] == "annees 2011-2024 conservees"
    assert any("rejetee" in reason for reason in steps["etl"]["reasons"])
    assert steps["auditor"]["decision"] == "verdict pass_with_warnings"


# --------------------------------------------------------------------------- E : texte et LLM
def _with_llm(world, monkeypatch, answer, budget=3):
    from biflow.agents.base import BaseAgent
    calls = []
    monkeypatch.setattr(BaseAgent, "get_llm", lambda self: object())

    def ask_text(self, prompt, system=None):
        calls.append(prompt)
        return answer(prompt) if callable(answer) else answer

    monkeypatch.setattr(BaseAgent, "ask_text", ask_text)
    cfg = {**world.cfg, "llm": {"enabled": True}, "auditor": {**world.cfg["auditor"], "llm_examples": budget}}
    return AuditorAgent(cfg=cfg, run_id="audit_run").execute(world.ctx)["audit"]["examples"], calls


def test_every_explanation_has_fr_and_en_template(world):
    stored, _ = _explanations(world)
    for record in stored.values():
        assert record["narrative"]["origin"] == "template"
        assert record["narrative"]["fr"] and record["narrative"]["en"]


def test_report_examples_without_llm_use_templates(world, monkeypatch):
    from biflow.agents.base import BaseAgent
    monkeypatch.setattr(BaseAgent, "ask_text", lambda *a, **k: pytest.fail("aucun appel LLM attendu"))
    examples = _execute(world)["examples"]
    assert [e["title"] for e in examples] == ["Detention de compte", "Ecart hommes-femmes",
                                              "Densite d'agences et pairs"]
    assert all(e["origin"] == {"fr": "template", "en": "template"} for e in examples)
    assert "variation +6,6 pts. Decomposition : men +4,4 pts, women -2,1 pts." in examples[1]["text"]["fr"]
    assert "Pairs : MAR" in examples[2]["text"]["fr"]


def test_hallucinated_llm_number_falls_back_to_template(world, monkeypatch):
    examples, calls = _with_llm(world, monkeypatch, "Environ 40 % des adultes ont un compte en 2024.")
    assert len(calls) == 3
    for example in examples:
        assert example["origin"]["fr"] == "template" and example["text"]["fr"] == example["template"]["fr"]
        assert example["llm"]["llm_status"] == "rejected_ungrounded"
    assert "40" in examples[0]["llm"]["unsupported_numbers"]


def test_grounded_llm_rephrasing_is_kept_within_budget(world, monkeypatch):
    def faithful(prompt):  # reformule en gardant exactement les nombres du gabarit
        return "En clair : " + prompt.split("Texte : ", 1)[1]

    examples, calls = _with_llm(world, monkeypatch, faithful, budget=1)
    assert len(calls) == 1  # budget d'appels respecte
    assert examples[0]["origin"]["fr"] == "llm" and examples[0]["text"]["fr"].startswith("En clair : ")
    assert [e["origin"]["fr"] for e in examples[1:]] == ["template", "template"]


def test_explain_cli_reads_stored_explanations_only(world, monkeypatch, capsys):
    import sys
    import main as cli
    _execute(world)
    warehouse = str(world.tmp / "processed" / "warehouse.duckdb")
    original = duckdb.connect

    def read_only(*args, **kwargs):
        assert kwargs.get("read_only") is True
        return original(*args, **kwargs)

    monkeypatch.setattr(duckdb, "connect", read_only)
    monkeypatch.setattr(sys, "argv", ["main.py", "explain", "--kpi", "gender_gap", "--iso3", "tun", "--year",
                                      "2024", "--compare-year", "2021", "--warehouse", warehouse])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert out.startswith("# Account ownership gender gap - Tunisia 2024")
    assert "Decomposition : men +4,4 pts, women -2,1 pts." in out
    monkeypatch.setattr(sys, "argv", ["main.py", "explain", "--kpi", "branch_density", "--iso3", "TUN",
                                      "--year", "2023", "--compare-iso3", "PEERS", "--lang", "en",
                                      "--warehouse", warehouse])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "Peer average 2023 21.0 per 100 000 adults -> Tunisia 2023 18.0" in out and "Peers: MAR 21.0." in out
    monkeypatch.setattr(sys, "argv", ["main.py", "explain", "--kpi", "account_ownership", "--iso3", "TUN",
                                      "--year", "1999", "--warehouse", warehouse])
    assert cli.main() == 1


# --------------------------------------------------------------------------- F : insights
def test_insights_in_state_are_audited_without_affecting_publication(world):
    good = {"insight_id": "good", "text": "En 2024, 37,8 % des adultes tunisiens avaient un compte.",
            "claims": [{"kpi_id": "account_ownership", "iso3": "TUN", "year": 2024, "value": 37.8,
                        "unit": "percent"}], "recommendation": "-", "confidence": "high"}
    bad = {**good, "insight_id": "bad", "text": "En 2024, 41 % des adultes tunisiens avaient un compte."}
    before = _execute(world)
    audit = AuditorAgent(cfg=world.cfg, run_id="audit_run").execute({**world.ctx, "audit_insights": [good, bad]})["audit"]
    assert [(i["insight_id"], i["accepted"]) for i in audit["insight_audit"]] == [("good", True), ("bad", False)]
    f1 = next(c for c in audit["checks"] if c["check_id"] == "F1_insights_grounded")
    assert f1["result"] == "warn" and f1["affected_rows"][0]["insight_id"] == "bad"
    assert audit["publication"] == before["publication"]


def test_new_units_have_bounds_and_pct_of_gdp_is_not_capped():
    """Catalogue 1.4.0 : per_1k_adults et percent_of_gdp ont des bornes ; un % du PIB > 100
    reste plausible (seul le diagnostic qualite signale les valeurs extremes)."""
    from biflow.tools.audit_checks import unit_checks

    catalog = {"kpis": {"depositors_per_1k": {"unit": "per_1k_adults"},
                        "loans_pct_gdp": {"unit": "percent_of_gdp"}}}
    rows = [{"kpi_id": "depositors_per_1k", "iso3": "TUN", "year": 2018, "unit": "per_1k_adults", "value": 1063.3},
            {"kpi_id": "loans_pct_gdp", "iso3": "TUN", "year": 2024, "unit": "percent_of_gdp", "value": 145.0}]
    units, ranges = unit_checks(rows, catalog)
    assert units["result"] == ranges["result"] == "pass"
    rows[0]["value"] = -1.0
    units, ranges = unit_checks(rows, catalog)
    assert units["result"] == "pass" and ranges["result"] == "fail"
    assert [r["kpi_id"] for r in ranges["affected_rows"]] == ["depositors_per_1k"]
