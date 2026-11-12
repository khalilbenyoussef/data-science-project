"""Integration des sources utilisateur dans le pipeline (fixtures, aucun reseau)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from biflow import graph
from biflow.agents.etl import EtlAgent
from biflow.agents.quality import QualityAgent
from biflow.config import register_user_sources
from biflow.tools.snapshots import SnapshotStore
from biflow.tools.user_sources.registry import register
from biflow.tools.user_sources.mapping import validate_mapping
from biflow.utils.io import file_stat, sha256_file
from test_auditor import _cfg
from test_kpi_values import _inputs

# Empreintes du code AVANT l'integration des sources utilisateur (commit bd2d300),
# calculees sur cette fixture : le pipeline officiel doit rester identique.
BASELINE_WAREHOUSE_CONTENT = "c453ab71b3f044743b21c43cef536162e9e102d8b4e8ccf2c32134319790d6c1"
BASELINE_FACT_DIGEST = "9c502ccd03e3e9b0bb6cd924bcb231ef7a3d4f64aed288ee32ec8caf27e87a12"
OFFICIAL = ("findex", "fas", "gdp")
AGENTS_CSV = "pays;annee;agents;succursales\nTunisie;2023;1 200,5;45\nMaroc;2023;980;30\nTunisie;2024;1 310;47\n"


def user_mapping(name, file):
    return {"schema_version": 1, "name": name, "fingerprint": "0" * 64, "file": str(file),
            "read": {"encoding": "utf-8-sig", "separator": ";", "decimal": ",", "header_row": 0},
            "layout": "wide_by_indicator",
            "columns": {"country": {"column": "pays", "kind": "name"}, "year": "annee",
                        "indicator_columns": {"agents": "agents", "succursales": "succursales"}},
            "indicators": {"agents": {"label": "Agents bancaires", "unit": "count"},
                           "succursales": {"label": "Succursales", "unit": "count"}}}


def add_user_source(base: Path, cfg: dict, monkeypatch, text: str = AGENTS_CSV, name: str = "agents"):
    upload = base / "incoming.csv"
    upload.write_text(text, encoding="utf-8")
    cfg["uploads"] = {"dir": str(base / "uploads"), "mappings_dir": str(base / "sources")}
    register(validate_mapping(user_mapping(name, upload)), upload, cfg)
    monkeypatch.setenv("BIFLOW_SOURCES_DIR", str(base / "sources"))
    assert register_user_sources(cfg) == [name]
    return base / "uploads" / f"{name}.csv"


def quality_and_etl(base: Path, cfg: dict):
    """Memes etapes que le calcul des empreintes de reference."""
    raw_paths = {n: s["path"] for n, s in cfg["sources"].items() if s.get("type") != "user"}
    raw_paths.update({n: s["path"] for n, s in cfg["sources"].items() if s.get("type") == "user"})
    raw_meta = {n: {"path": p, "sha256": sha256_file(p), **file_stat(p)} for n, p in raw_paths.items()}
    snap = SnapshotStore(base / "snapshots").prepare(raw_paths, cfg["sources"], run_id="r")
    state = {"run_id": "r", "sources": cfg["sources"], "raw_paths": raw_paths, "raw_meta": raw_meta,
             "snapshot": snap, "snapshot_id": snap["snapshot_id"]}
    for agent in (QualityAgent, EtlAgent):
        state.update(agent(cfg=cfg, run_id="r").execute(state))
    lineage = json.loads((base / "processed" / "lineage.json").read_text(encoding="utf-8"))
    with duckdb.connect(str(base / "processed" / "warehouse.duckdb"), read_only=True) as con:
        official = con.execute("SELECT * FROM fact WHERE source IN ('findex', 'fas', 'gdp') ORDER BY ALL").fetchall()
        user = con.execute("SELECT iso3, year, indicator_code, value, unit FROM fact "
                           "WHERE source LIKE 'user:%' ORDER BY ALL").fetchall()
    return state, lineage, hashlib.sha256(json.dumps(official, default=str).encode()).hexdigest(), user


@pytest.fixture
def base(tmp_path):
    (tmp_path / "raw").mkdir()
    return tmp_path


def test_official_outputs_are_unchanged_without_user_sources(base):
    cfg = _cfg(base, _inputs(base / "raw"))
    _, lineage, official_digest, user = quality_and_etl(base, cfg)
    assert user == []
    assert official_digest == BASELINE_FACT_DIGEST
    assert lineage["outputs"]["warehouse_content_sha256"] == BASELINE_WAREHOUSE_CONTENT


def test_official_facts_are_unchanged_with_a_user_source(base, monkeypatch):
    cfg = _cfg(base, _inputs(base / "raw"))
    add_user_source(base, cfg, monkeypatch)
    state, lineage, official_digest, user = quality_and_etl(base, cfg)
    assert official_digest == BASELINE_FACT_DIGEST  # lignes officielles identiques octet pour octet
    assert user == [("MAR", 2023, "agents.agents", 980.0, "count"), ("MAR", 2023, "agents.succursales", 30.0, "count"),
                    ("TUN", 2023, "agents.agents", 1200.5, "count"), ("TUN", 2023, "agents.succursales", 45.0, "count"),
                    ("TUN", 2024, "agents.agents", 1310.0, "count"), ("TUN", 2024, "agents.succursales", 47.0, "count")]
    assert lineage["outputs"]["warehouse_content_sha256"] != BASELINE_WAREHOUSE_CONTENT
    assert lineage["inputs"]["agents"]["user"] is True and lineage["inputs"]["agents"]["excluded"] is None
    assert state["quality"]["passed"] is True and state["quality"]["user_sources"]["agents"]["gate"] is True
    assert set(state["quality"]["checks"]) == set(OFFICIAL)  # gate officiel inchange


def test_official_sources_are_never_replaced_by_a_mapping(base, monkeypatch):
    cfg = _cfg(base, _inputs(base / "raw"))
    (base / "sources").mkdir()
    (base / "sources" / "findex.yaml").write_text("name: findex\nfile: autre.csv\n", encoding="utf-8")
    monkeypatch.setenv("BIFLOW_SOURCES_DIR", str(base / "sources"))
    assert register_user_sources(cfg) == [] and cfg["sources"]["findex"].get("type") != "user"


# --------------------------------------------------------------------------- pipeline complet
def full_cfg(base: Path) -> dict:
    cfg = _cfg(base, _inputs(base / "raw"))
    for source in cfg["sources"].values():
        source["static"] = True
    cfg["paths"]["profiles"] = str(base / "profiles")
    cfg["orchestrator"] = {"max_retries": 0}
    return cfg


def test_failing_user_source_is_excluded_and_recorded(base, monkeypatch):
    cfg = full_cfg(base)
    upload = add_user_source(base, cfg, monkeypatch)
    # Le fichier depose evolue : cles en conflit (critique) -> exclu, le pipeline officiel publie
    upload.write_text(AGENTS_CSV + "Tunisie;2023;1 250;45\n", encoding="utf-8")
    state = graph.run_pipeline(cfg=cfg, run_id="excl", use_llm=False)
    assert state["status"] == "success" and state["snapshot"]["status"] == "published"
    excluded, = state["excluded_sources"]
    assert (excluded["source"], excluded["step"]) == ("agents", "quality")
    assert "valeurs différentes" in excluded["reason"] and excluded["quality_score"] < 0.7
    run = json.loads((base / "reports" / "excl" / "run.json").read_text(encoding="utf-8"))
    assert run["excluded_sources"] == state["excluded_sources"]
    with duckdb.connect(str(base / "processed" / "warehouse.duckdb"), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM fact WHERE source LIKE 'user:%'").fetchone()[0] == 0
    report = json.loads((base / "audit" / "audit_report.json").read_text(encoding="utf-8"))
    step = next(e for e in report["decision_log"] if e["step"] == "user_sources")
    assert step["decision"] == "0 source(s) utilisateur incluse(s), 1 exclue(s)"
    assert "agents exclue à l'étape quality (score qualité 0,65)" in step["reasons"][0]
    assert report["verdict"] != "fail"
    md = (base / "quality" / "quality_report.md").read_text(encoding="utf-8")
    assert "FAIL (exclue)" in md and "Exclue : **agents**" in md


def test_broken_mapping_is_excluded_at_collection(base, monkeypatch):
    cfg = full_cfg(base)
    add_user_source(base, cfg, monkeypatch)
    (base / "sources" / "agents.yaml").write_text("name: agents\nlayout: inconnu\n", encoding="utf-8")
    state = graph.run_pipeline(cfg=cfg, run_id="broken", use_llm=False)
    assert state["status"] == "success"
    excluded, = state["excluded_sources"]
    assert excluded["step"] == "collector" and "Mapping invalide" in excluded["reason"]
    assert "agents" not in state["raw_paths"]


def test_included_user_source_passes_the_audit(base, monkeypatch):
    cfg = full_cfg(base)
    add_user_source(base, cfg, monkeypatch)
    state = graph.run_pipeline(cfg=cfg, run_id="incl", use_llm=False)
    assert state["status"] == "success" and not state["excluded_sources"]
    checks = {c["check_id"]: c for c in state["audit"]["checks"]}
    assert checks["A6_user_source_facts"]["result"] == "pass"
    assert "agents" in checks["A6_user_source_facts"]["detail"]
    assert checks["B6_source_hashes"]["result"] == "pass"
    manifest = SnapshotStore(base / "snapshots").manifest(state["snapshot_id"])
    assert "agents" in manifest["sources"]  # versionnee comme les autres sources


def test_offline_official_job_changes_only_the_user_source(base, monkeypatch):
    """Job « Mes données » : les sources officielles viennent du snapshot publie (aucun
    reseau) ; le nouveau snapshot ne differe que par la source utilisateur."""
    from biflow.agents.collector import CollectorAgent

    cfg = full_cfg(base)
    first = graph.run_pipeline(cfg=cfg, run_id="officiel", use_llm=False)
    assert first["snapshot"]["status"] == "published"
    store = SnapshotStore(base / "snapshots")
    before = store.manifest(first["snapshot_id"])["sources"]

    cfg["sources"]["gdp"].update(static=False, dynamic=True)  # source dynamique : jamais rafraichie ici
    for method in ("_refresh", "_fas_api", "_get", "_get_text"):
        monkeypatch.setattr(CollectorAgent, method, lambda *a, **k: pytest.fail("appel reseau interdit"))
    add_user_source(base, cfg, monkeypatch)
    added = graph.run_pipeline(cfg=cfg, run_id="ajout", use_llm=False, offline_official=True)
    assert added["status"] == "success" and added["snapshot"]["status"] == "published"
    after = store.manifest(added["snapshot_id"])["sources"]
    changed = {name for name in after if (before.get(name) or {}).get("sha256") != after[name]["sha256"]}
    assert changed == {"agents"}
    assert {name: after[name]["sha256"] for name in OFFICIAL} == {name: before[name]["sha256"] for name in OFFICIAL}

    (base / "sources" / "agents.yaml").unlink()
    cfg["sources"].pop("agents")
    removed = graph.run_pipeline(cfg=cfg, run_id="retrait", use_llm=False, offline_official=True)
    final = store.manifest(removed["snapshot_id"])["sources"]
    assert set(final) == set(OFFICIAL)
    assert {name: final[name]["sha256"] for name in OFFICIAL} == {name: before[name]["sha256"] for name in OFFICIAL}
    with duckdb.connect(str(base / "processed" / "warehouse.duckdb"), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM fact WHERE source LIKE 'user:%'").fetchone()[0] == 0
