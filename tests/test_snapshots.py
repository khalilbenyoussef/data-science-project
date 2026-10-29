"""Snapshots des sources brutes et collecte FAS via API (fixtures, aucun reseau)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from biflow import graph
from biflow.agents.collector import CollectorAgent, CollectorAPIError, SdmxFormatError, sdmx_to_fas_wide
from biflow.tools.snapshots import SnapshotStore, content_sha256, count_rows

FIXTURE = Path(__file__).parent / "fixtures" / "imf_fas_sdmx_fa26_sample.csv"


def _write(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- empreinte
def test_content_hash_ignores_row_order_and_line_endings(tmp_path):
    a = _write(tmp_path / "a.csv", ["iso3,year,value", "TUN,2024,0.37", "MAR,2024,0.44"])
    b = _write(tmp_path / "b.csv", ["iso3,year,value", "MAR,2024,0.44", "TUN,2024,0.37"])
    c = tmp_path / "c.csv"
    c.write_bytes(b"\xef\xbb\xbfiso3,year,value\r\nTUN,2024,0.37\r\nMAR,2024,0.44\r\n")
    d = _write(tmp_path / "d.csv", ["iso3,year,value", "TUN,2024,0.38", "MAR,2024,0.44"])
    assert content_sha256(a) == content_sha256(b) == content_sha256(c)
    assert content_sha256(d) != content_sha256(a)


def test_count_rows_uses_header_marker(tmp_path):
    path = _write(tmp_path / "fas.csv", ["Dataset,FAS", "SERIES_CODE,2024", "TUN.X.A,1", "MAR.X.A,2"])
    assert count_rows(path, "SERIES_CODE") == 2 and count_rows(path) == 3


def test_count_rows_counts_records_not_physical_lines(tmp_path):
    # Champ entre guillemets sur 3 lignes (comme FULL_DESCRIPTION dans fas.csv)
    path = tmp_path / "fas.csv"
    path.write_text('Column1;Column2;Column3\nSERIES_CODE;NOTE;2024\n'
                    'TUN.X.A;"ligne 1\nligne 2\nligne 3";1\n\nMAR.X.A;"court";2\n', encoding="utf-8")
    assert count_rows(path, "SERIES_CODE") == 2


# --------------------------------------------------------------------------- store
@pytest.fixture
def raw(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    paths = {
        "findex": _write(raw / "findex.csv", ["codewb,year,group,group2,account_t_d", "TUN,2024,all,all,0.378445"]),
        "fas": _write(raw / "fas.csv", ["SERIES_CODE,2024", "TUN.FA26N.PHTADLT_NUM.A,22.4"]),
        "gdp": _write(raw / "gdp.csv", ["iso3,indicator_code,year,value", "TUN,NY.GDP.MKTP.KD.ZG,2024,1.6"]),
    }
    return {name: str(path) for name, path in paths.items()}


def test_new_data_creates_v2_and_keeps_v1_with_shared_blobs(tmp_path, raw):
    store = SnapshotStore(tmp_path / "snapshots")
    first = store.prepare(raw, run_id="r1")
    assert first == {**first, "status": "new", "snapshot_id": "v1", "previous": None}
    store.finalize("v1", published=True)
    assert store.prepare(raw, run_id="r2")["status"] == "no_change"

    _write(Path(raw["gdp"]), ["iso3,indicator_code,year,value", "TUN,NY.GDP.MKTP.KD.ZG,2024,1.7"])
    second = store.prepare(raw, run_id="r3")
    assert (second["status"], second["snapshot_id"], second["previous"]) == ("new", "v2", "v1")
    store.finalize("v2", published=True)

    index = store.load_index()
    assert index["published"] == "v2"
    assert [(e["snapshot_id"], e["status"]) for e in index["snapshots"]] == [("v1", "superseded"), ("v2", "published")]
    v1, v2 = store.manifest("v1"), store.manifest("v2")
    assert v1["sources"]["findex"]["blob"] == v2["sources"]["findex"]["blob"]  # stocke une seule fois
    assert v1["sources"]["gdp"]["blob"] != v2["sources"]["gdp"]["blob"]
    assert len(list((tmp_path / "snapshots" / "blobs").iterdir())) == 4
    for manifest in (v1, v2):
        assert {"created_at", "run_id", "content_key", "sources"} <= set(manifest)
        for name, source in manifest["sources"].items():
            blob = tmp_path / "snapshots" / source["blob"]
            assert source["blob"] == f"blobs/{source['sha256']}.csv" and blob.exists()
            assert source["rows"] == 1 and len(source["content_sha256"]) == 64
    # Le blob v1 est une copie exacte de l'ancien fichier
    assert "1.6" in (tmp_path / "snapshots" / v1["sources"]["gdp"]["blob"]).read_text(encoding="utf-8")


def test_failed_run_keeps_previous_published_and_gc_keeps_indexed_blobs(tmp_path, raw):
    store = SnapshotStore(tmp_path / "snapshots")
    store.prepare(raw)
    store.finalize("v1", published=True)
    _write(Path(raw["findex"]), ["codewb,year,group,group2,account_t_d", "TUN,2024,all,all,0.5"])
    store.prepare(raw)
    orphan = tmp_path / "snapshots" / "blobs" / ("f" * 64 + ".csv")
    orphan.write_text("orphelin")
    store.finalize("v2", published=False, reason="quality_failed")
    index = store.load_index()
    assert index["published"] == "v1"
    assert [(e["snapshot_id"], e["status"], e.get("reason")) for e in index["snapshots"]] == [
        ("v1", "published", None), ("v2", "not_published", "quality_failed")]
    assert not orphan.exists()
    for snapshot_id in ("v1", "v2"):
        for source in store.manifest(snapshot_id)["sources"].values():
            assert (tmp_path / "snapshots" / source["blob"]).exists()
    # Le contenu de v2 differe toujours du publie : un nouveau run recree une version
    assert store.prepare(raw)["snapshot_id"] == "v3"


# --------------------------------------------------------------------------- pipeline
class _Fake:
    def __init__(self, name, log):
        self.name, self.log = name, log

    def run(self, state):
        self.log["calls"].append(self.name)
        outputs = {"quality": {"passed": self.log["passed"]}} if self.name == "quality" else {}
        return {"status": "success", "outputs": outputs, "errors": []}


@pytest.fixture(params=["langgraph", "sequential"])
def pipeline(request, tmp_path, raw, monkeypatch):
    if request.param == "langgraph" and not graph.LANGGRAPH_AVAILABLE:
        pytest.skip("LangGraph unavailable")
    monkeypatch.setattr(graph, "LANGGRAPH_AVAILABLE", request.param == "langgraph")
    monkeypatch.setattr(graph.time, "sleep", lambda s: None)
    log = {"calls": [], "passed": True}
    for name in ("profiler", "quality", "etl", "semantic_kpi"):
        monkeypatch.setitem(graph.AGENT_CLASSES, name, lambda name=name, **kw: _Fake(name, log))
    sources = {name: {"type": "csv", "static": True, "path": path} for name, path in raw.items()}
    cfg = {"paths": {"reports": str(tmp_path / "reports")}, "llm": {"enabled": False},
           "collector": {"retries": 1}, "orchestrator": {"max_retries": 1, "retry_backoff_s": 0},
           "snapshots": {"enabled": True, "root": str(tmp_path / "snapshots")}, "sources": sources}
    counter = iter(range(1, 100))

    def run():
        log["calls"].clear()
        state = graph.run_pipeline(cfg=cfg, run_id=f"run{next(counter)}", use_llm=False)
        return state, log["calls"]

    return run, cfg, log, SnapshotStore(tmp_path / "snapshots")


def test_pipeline_publishes_then_skips_unchanged_data(pipeline, raw):
    run, _, _, store = pipeline
    state, calls = run()
    assert state["status"] == "success" and state["snapshot_id"] == "v1"
    assert state["snapshot"]["status"] == "published" and calls[-2:] == ["etl", "semantic_kpi"]

    state, calls = run()
    assert state["status"] == "no_change" and calls == []  # ni profil, ni qualite, ni ETL, ni KPI
    assert state["snapshot"] == {**state["snapshot"], "status": "no_change", "snapshot_id": "v1"}
    summary = json.loads((store.root.parent / "reports" / "run2" / "run.json").read_text(encoding="utf-8"))
    assert summary["status"] == "no_change" and summary["snapshot"]["snapshot_id"] == "v1"

    lines = Path(raw["findex"]).read_text(encoding="utf-8").splitlines()
    _write(Path(raw["findex"]), [lines[0], lines[1], "MAR,2024,all,all,0.44"])  # nouvelle ligne
    state, _ = run()
    assert state["snapshot_id"] == "v2"
    _write(Path(raw["findex"]), [lines[0], "MAR,2024,all,all,0.44", lines[1]])  # ordre seul
    state, calls = run()
    assert state["status"] == "no_change" and calls == []
    assert store.load_index()["published"] == "v2"


def test_quality_fail_does_not_publish_new_snapshot(pipeline, raw):
    run, _, log, store = pipeline
    run()
    _write(Path(raw["gdp"]), ["iso3,indicator_code,year,value", "TUN,NY.GDP.MKTP.KD.ZG,2024,9.9"])
    log["passed"] = False
    state, calls = run()
    assert state["status"] == "quality_failed" and "etl" not in calls
    assert state["snapshot"]["status"] == "not_published"
    assert store.load_index()["published"] == "v1"


def test_partial_run_without_etl_is_not_published(pipeline):
    run, cfg, _, store = pipeline
    state = graph.run_pipeline(cfg=cfg, run_id="partial", stop="quality", use_llm=False)
    assert state["status"] == "success" and state["snapshot"]["status"] == "not_published"
    assert state["snapshot"]["reason"] == "partial_run" and store.load_index()["published"] is None


# --------------------------------------------------------------------------- FAS API
def _api_cfg(cfg, tmp_path):
    cfg["sources"]["fas"] = {
        "type": "csv", "static": True, "path": str(tmp_path / "raw" / "fas.csv"),
        "header_marker": "SERIES_CODE",
        "series": {"branch_density": "FA26N.PHTADLT_NUM", "atm_density": "FA18N.PHTADLT_NUM"},
        "api": {"enabled": True, "path": str(tmp_path / "raw" / "fas_api.csv"), "countries": "*",
                "base_url": "https://example.invalid/FAS/~/",
                "series": {"FA26N.PHTADLT_NUM": "FA26._Z._Z._T.PHTADLT_NUM.A"}},
    }


def test_sdmx_conversion_keeps_values_verbatim():
    wide = sdmx_to_fas_wide({"FA26N.PHTADLT_NUM": FIXTURE.read_text(encoding="utf-8")})
    tun = wide[wide.SERIES_CODE == "TUN.FA26N.PHTADLT_NUM.A"].iloc[0]
    assert tun["2019"] == "22.15207025152383" and tun["2023"] == "22.42043754671602"
    assert pd.isna(wide[wide.SERIES_CODE == "MAR.FA26N.PHTADLT_NUM.A"].iloc[0]["2022"])
    assert "AIA.FA26N.PHTADLT_NUM.A" not in set(wide.SERIES_CODE)  # serie sans observation


@pytest.mark.parametrize("column,value", [("SCALE", "3"), ("FREQUENCY", "Q")])
def test_sdmx_unverified_scale_or_frequency_is_rejected(column, value):
    df = pd.read_csv(FIXTURE, dtype=str, keep_default_na=False)
    df.loc[1, column] = value
    with pytest.raises(SdmxFormatError):
        sdmx_to_fas_wide({"FA26N.PHTADLT_NUM": df.to_csv(index=False)})


def test_api_new_data_v2_then_api_down_keeps_last_snapshot(pipeline, tmp_path, monkeypatch):
    run, cfg, _, store = pipeline
    _api_cfg(cfg, tmp_path)
    responses = {"text": FIXTURE.read_text(encoding="utf-8")}

    def fake_get_text(self, url, accept):
        assert accept == "text/csv" and url == "https://example.invalid/FAS/~/*.FA26._Z._Z._T.PHTADLT_NUM.A"
        if responses["text"] is None:
            raise CollectorAPIError("API IMF injoignable : timed out")
        return responses["text"]

    monkeypatch.setattr(CollectorAgent, "_get_text", fake_get_text)
    state, _ = run()
    assert state["snapshot_id"] == "v1" and state["raw_paths"]["fas"].endswith("fas_api.csv")
    assert any("FA18N.PHTADLT_NUM" in w for w in state["warnings"])  # serie non mappee signalee
    assert store.manifest("v1")["sources"]["fas"]["original_path"].endswith("fas_api.csv")

    responses["text"] = responses["text"].replace("22.42043754671602", "22.5")
    state, _ = run()
    assert state["snapshot_id"] == "v2" and state["snapshot"]["status"] == "published"
    assert [e["snapshot_id"] for e in store.load_index()["snapshots"]] == ["v1", "v2"]
    v1_blob = store.root / store.manifest("v1")["sources"]["fas"]["blob"]
    assert "22.42043754671602" in v1_blob.read_text(encoding="utf-8")  # v1 conserve

    responses["text"] = None  # API en panne : cache local conserve
    state, calls = run()
    assert state["status"] == "no_change" and calls == []
    assert any("cache conserve" in w for w in state["warnings"])
    assert store.load_index()["published"] == "v2"


def test_api_down_without_cache_fails_and_keeps_published(pipeline, tmp_path, monkeypatch):
    run, cfg, _, store = pipeline
    run()  # v1 publie depuis les CSV statiques
    _api_cfg(cfg, tmp_path)

    def down(self, url, accept):
        raise CollectorAPIError("API IMF injoignable : 503")

    monkeypatch.setattr(CollectorAgent, "_get_text", down)
    state, calls = run()
    assert state["status"] == "failed" and calls == []
    assert len([e for e in state["errors"] if e.startswith("[collector] tentative")]) == 2
    index = store.load_index()
    assert index["published"] == "v1" and len(index["snapshots"]) == 1
