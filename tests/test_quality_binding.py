"""Liaison rapport qualite <-> run / hash des sources (fichiers temporaires uniquement)."""
from __future__ import annotations

import hashlib
import json

import pytest

from biflow.agents.quality import QualityAgent, input_hashes
from biflow.tools.kpi import KpiCalculator
from test_kpi import warehouse  # noqa: F401 - fixture reutilisee
from test_quality import _mandatory_frames


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def sources(tmp_path):
    out = {}
    for name, frame in _mandatory_frames().items():
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        out[name] = {"type": "csv", "path": str(path)}
    out["findex"]["indicators"] = ["account_t_d"]
    out["fas"]["series"] = {"test": "FA0.NUM"}
    out["gdp"]["indicators"] = ["NY.GDP.MKTP.CD"]
    return out


def _run_quality(tmp_path, sources, run_id, raw_meta=None):
    cfg = {"paths": {"reports": str(tmp_path / "reports"), "quality": str(tmp_path / "quality")},
           "llm": {"enabled": False}, "quality": {"min_rows": 10, "score_threshold": 0.9}}
    ctx = {"run_id": run_id, "snapshot_id": "v3", "sources": sources,
           "raw_paths": {name: s["path"] for name, s in sources.items()}}
    if raw_meta is not None:
        ctx["raw_meta"] = raw_meta
    QualityAgent(cfg=cfg, run_id=run_id).execute(ctx)
    path = tmp_path / "quality" / "quality_report.json"
    return path, json.loads(path.read_text(encoding="utf-8"))


def test_report_records_run_created_at_and_collector_hashes(tmp_path, sources):
    raw_meta = {name: {"path": s["path"], "sha256": "a" * 64} for name, s in sources.items()}
    _, report = _run_quality(tmp_path, sources, "run_q", raw_meta)
    assert report["run_id"] == "run_q" and report["created_at"]
    assert report["snapshot_id"] == "v3"
    assert set(report["inputs"]) == {"findex", "fas", "gdp"}
    for name, meta in report["inputs"].items():
        # Hash du collector reutilise tel quel (pas de recalcul)
        assert meta == {"path": sources[name]["path"], "sha256": "a" * 64, "hash_origin": "collector"}
    md = (tmp_path / "quality" / "quality_report.md").read_text(encoding="utf-8")
    assert "run_q" in md


def test_hash_is_computed_when_collector_metadata_is_absent(tmp_path, sources):
    _, report = _run_quality(tmp_path, sources, "run_q")
    for name, meta in report["inputs"].items():
        assert meta["sha256"] == _sha(tmp_path / f"{name}.csv")
        assert meta["hash_origin"] == "quality"


def test_collector_hash_for_another_path_is_not_reused(tmp_path, sources):
    raw_meta = {"findex": {"path": str(tmp_path / "other.csv"), "sha256": "b" * 64}}
    report = input_hashes({"findex": sources["findex"]["path"]}, raw_meta)
    assert report["findex"]["sha256"] == _sha(tmp_path / "findex.csv")


def _calculate(warehouse, quality_path, lineage):
    lineage_path = warehouse.with_name("lineage.json")
    lineage_path.write_text(json.dumps(lineage), encoding="utf-8")
    return KpiCalculator(warehouse, lineage_path=lineage_path,
                         quality_report_path=quality_path).calculate("TUN", 2024, "account_ownership")


def _lineage(warehouse, sources, run_id):
    raw = warehouse.parent / "findex.csv"
    return {"run_id": run_id, "created_at": "2026-10-29T10:00:00",
            "inputs": {"findex": {"path": str(raw), "sha256": _sha(raw), "rows": 100}},
            "outputs": {"warehouse": str(warehouse)}}


def test_matching_run_and_hashes_remove_binding_review_reason(warehouse, sources):
    tmp_path = warehouse.parent
    lineage = _lineage(warehouse, sources, "run_same")
    raw_meta = {"findex": dict(lineage["inputs"]["findex"])}
    quality_path, _ = _run_quality(tmp_path, sources, "run_same", raw_meta)
    result = _calculate(warehouse, quality_path, lineage)
    issues = result.provenance.issues
    assert result.provenance.quality_association_status == "matches_lineage"
    assert "quality_provenance_unverified" not in issues
    assert "quality_provenance_mismatch" not in issues
    assert "quality_provenance_unverified" not in result.review_reasons
    assert result.value == pytest.approx(42)


@pytest.mark.parametrize("mismatch", ["run_id", "sha256"])
def test_mismatched_run_or_hash_keeps_review_reason(warehouse, sources, mismatch):
    tmp_path = warehouse.parent
    lineage = _lineage(warehouse, sources, "run_etl")
    run_id = "run_older_quality" if mismatch == "run_id" else "run_etl"
    quality_path, _ = _run_quality(tmp_path, sources, run_id)
    if mismatch == "sha256":
        lineage["inputs"]["findex"]["sha256"] = "0" * 64
    result = _calculate(warehouse, quality_path, lineage)
    assert result.provenance.quality_association_status == "inconsistent"
    assert "quality_provenance_mismatch" in result.review_reasons
    assert result.requires_review and result.value == pytest.approx(42)


def test_report_without_binding_stays_unverified(warehouse, sources):
    tmp_path = warehouse.parent
    lineage = _lineage(warehouse, sources, "run_x")
    quality_path, report = _run_quality(tmp_path, sources, "run_x")
    for key in ("run_id", "inputs"):
        report.pop(key)
    quality_path.write_text(json.dumps(report), encoding="utf-8")
    result = _calculate(warehouse, quality_path, lineage)
    assert "quality_provenance_unverified" in result.review_reasons
