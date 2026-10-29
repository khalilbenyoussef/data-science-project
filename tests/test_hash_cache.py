"""Hash des sources calcule une fois par run et reutilise par l'etape KPI."""
from __future__ import annotations

import os

import pytest

from biflow.agents.collector import CollectorAgent
from biflow.agents.etl import EtlAgent
from biflow.agents.semantic_kpi import SemanticKpiAgent
from biflow.utils import io
from biflow.utils.io import cached_sha256_file, file_stat, remember_sha256, sha256_file
from test_kpi_values import _inputs


@pytest.fixture
def counted(monkeypatch):
    monkeypatch.setattr(io, "_HASH_CACHE", {})
    calls = []
    original = io.sha256_file

    def counting(path, *args, **kwargs):
        calls.append(os.path.basename(str(path)))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(io, "sha256_file", counting)
    return calls


def test_unchanged_file_is_hashed_once_and_change_is_detected(tmp_path, counted):
    path = tmp_path / "source.csv"
    path.write_text("a,b\n1,2\n")
    first = cached_sha256_file(path)
    assert cached_sha256_file(path) == first and counted == ["source.csv"]
    path.write_text("a,b\n1,3\n")
    os.utime(path, ns=(1, 1))  # mtime differente garantie
    assert cached_sha256_file(path) == sha256_file(path) != first
    assert counted == ["source.csv", "source.csv"]  # un recalcul apres modification


def test_remembered_hash_requires_identical_size_and_mtime(tmp_path, counted):
    path = tmp_path / "source.csv"
    path.write_text("x\n")
    stat = file_stat(path)
    assert remember_sha256(path, "a" * 64, stat["size_bytes"], stat["mtime_ns"])
    assert cached_sha256_file(path) == "a" * 64 and counted == []
    assert not remember_sha256(path, "b" * 64, stat["size_bytes"] + 1, stat["mtime_ns"])
    assert not remember_sha256(tmp_path / "absent.csv", "b" * 64, 1, 1)
    assert not remember_sha256(path, "short", stat["size_bytes"], stat["mtime_ns"])


def test_collector_records_size_and_mtime_with_hash(tmp_path):
    path = tmp_path / "findex.csv"
    path.write_text("codewb,year\nTUN,2024\n")
    meta = CollectorAgent(cfg={"paths": {}}, run_id="t")._static("findex", {}, path)
    assert meta["sha256"] == sha256_file(path)
    assert (meta["size_bytes"], meta["mtime_ns"]) == tuple(file_stat(path).values())


def test_kpi_step_reuses_collector_hashes_without_rehashing_sources(tmp_path, counted):
    paths = _inputs(tmp_path)
    raw_meta = {name: {"path": p, "sha256": sha256_file(p), **file_stat(p)} for name, p in paths.items()}
    counted.clear()
    cfg = {
        "paths": {"processed": str(tmp_path / "processed"), "quality": str(tmp_path / "quality"),
                  "reports": str(tmp_path / "reports")},
        "etl": {"write_csv_copy": False},
        "kpi": {"focus": "TUN", "peers": ["MAR"]},
        "sources": {
            "findex": {"path": paths["findex"], "type": "csv", "indicators": ["account_t_d"]},
            "fas": {"path": paths["fas"], "type": "csv", "series": {"branch_density": "FA26N.PHTADLT_NUM"}},
            "gdp": {"path": paths["gdp"], "type": "csv"},
        },
    }
    state = {"run_id": "h", "sources": cfg["sources"], "raw_paths": paths, "raw_meta": raw_meta}
    state.update(EtlAgent(cfg=cfg, run_id="h").execute(state))
    out = SemanticKpiAgent(cfg=cfg, run_id="h").execute(state)
    assert out["kpi_summary"]["rows"] > 0
    assert not {"findex.csv", "fas.csv", "gdp.csv"} & set(counted)
