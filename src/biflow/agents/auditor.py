"""S12 - BI Auditor / XAI : verification independante des KPI publies.

Deterministe : recalcul depuis `fact` sans le code KPI, controles de
coherence et de tracabilite. Un verdict FAIL est une decision (jamais retente).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import duckdb

from biflow.agents.base import AgentError, BaseAgent
from biflow.config import resolve
from biflow.tools.audit_checks import (
    RawSources,
    count_results,
    load_catalog_file,
    raw_to_fact_check,
    read_kpi_rows,
    recompute_checks,
    verdict_of,
)
from biflow.utils.countries import normalize_iso3

DEFAULT_CATALOG_PATH = "config/kpi_catalog.v1.yaml"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


class AuditorAgent(BaseAgent):
    name = "auditor"

    # ------------------------------------------------------------------ entrees
    def _inputs(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        paths = self.cfg.get("paths") or {}
        audit_cfg = self.cfg.get("auditor") or {}
        warehouse = Path(ctx.get("warehouse_path") or resolve(
            Path(paths.get("processed", "data/processed")) / "warehouse.duckdb"))
        if not warehouse.is_file():
            raise AgentError(f"warehouse introuvable : {warehouse}")
        quality_path = Path((ctx.get("quality_paths") or {}).get("json") or resolve(
            Path(paths.get("quality", "data/quality")) / "quality_report.json"))
        lineage = _read_json(warehouse.with_name("lineage.json"))
        snapshot_id = ctx.get("snapshot_id") or lineage.get("snapshot_id")
        snapshot_root = resolve((self.cfg.get("snapshots") or {}).get("root", "data/snapshots"))
        manifest = _read_json(snapshot_root / str(snapshot_id) / "manifest.json") if snapshot_id else {}
        if manifest.get("sources"):
            raw_paths = {name: snapshot_root / source["blob"] for name, source in manifest["sources"].items()}
        else:  # snapshots desactives : fichiers enregistres dans le lineage
            raw_paths = {name: Path(meta["path"]) for name, meta in (lineage.get("inputs") or {}).items()
                         if isinstance(meta, dict) and meta.get("path")}
        kpi_cfg = self.cfg.get("kpi") or {}
        focus = normalize_iso3(kpi_cfg.get("focus"))
        peers = [normalize_iso3(p) for p in kpi_cfg.get("peers") or []]
        return {
            "warehouse": warehouse,
            "lineage_path": warehouse.with_name("lineage.json"),
            "lineage": lineage,
            "quality_path": quality_path,
            "quality": _read_json(quality_path),
            "snapshot_id": snapshot_id,
            "snapshot_root": snapshot_root,
            "manifest": manifest,
            "raw_paths": raw_paths,
            "catalog_path": resolve(audit_cfg.get("catalog", DEFAULT_CATALOG_PATH)),
            "focus": focus,
            "peers": [p for p in peers if p and p != focus],
            "tolerance": float(audit_cfg.get("tolerance", 1e-9)),
            "sources": ctx.get("sources") or self.cfg.get("sources") or {},
            "run_id": ctx.get("run_id") or self.run_id,
        }

    # ------------------------------------------------------------------ audit
    def audit(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        """Controles A (recalcul) ; renvoie aussi les donnees intermediaires."""
        inp = self._inputs(ctx)
        catalog, catalog_sha256 = load_catalog_file(inp["catalog_path"])
        fas_series = (inp["sources"].get("fas") or {}).get("series") or {}
        with duckdb.connect(str(inp["warehouse"]), read_only=True) as con:
            rows = read_kpi_rows(con)
            checks, recomputed = recompute_checks(
                con, catalog, rows, inp["focus"], inp["peers"], inp["tolerance"])
        raw = RawSources(inp["raw_paths"], inp["sources"])
        raw_check, raw_lookups = raw_to_fact_check(recomputed, raw, fas_series)
        checks.append(raw_check)
        return {"inputs": inp, "catalog": catalog, "catalog_sha256": catalog_sha256, "rows": rows,
                "recomputed": recomputed, "raw_lookups": raw_lookups, "checks": checks}

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        result = self.audit(ctx)
        checks = result["checks"]
        verdict = verdict_of(checks)
        counts = count_results(checks)
        self.log.info("[auditor] verdict %s : %d pass, %d warn, %d fail (%d lignes KPI)",
                      verdict, counts["pass"], counts["warn"], counts["fail"], len(result["rows"]))
        for check in checks:
            if check["result"] == "fail":
                self.log.warning("[auditor] %s : %s", check["check_id"], check["detail"])
        notes = dict(ctx.get("llm_notes") or {})
        notes["auditor"] = f"verdict {verdict} ({counts['fail']} echec(s), {counts['warn']} alerte(s))"
        return {
            "audit": {
                "verdict": verdict,
                "counts": counts,
                "run_id": result["inputs"]["run_id"],
                "snapshot_id": result["inputs"]["snapshot_id"],
                "rows": len(result["rows"]),
                "checks": checks,
            },
            "llm_notes": notes,
        }
