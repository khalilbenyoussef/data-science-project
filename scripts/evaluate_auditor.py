"""Evaluation de l'Auditor par injection de fautes.

Copie le warehouse, le lineage, le rapport qualite et l'index des snapshots
dans un dossier temporaire (blobs en lien physique, jamais modifies), injecte
une faute a la fois, relance l'Auditor et compte les fautes detectees. Les
donnees reelles ne sont jamais modifiees. Sortie : evaluation.md / .json.

    python scripts/evaluate_auditor.py [--out data/audit]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402
import yaml  # noqa: E402

from biflow.agents.auditor import DEFAULT_CATALOG_PATH, AuditorAgent  # noqa: E402
from biflow.config import load_config, resolve  # noqa: E402
from biflow.utils.countries import normalize_iso3  # noqa: E402


class Workspace:
    """Copie isolee des artefacts audites."""

    def __init__(self, cfg: dict[str, Any], base: Path):
        paths = cfg.get("paths") or {}
        processed = resolve(paths.get("processed", "data/processed"))
        quality = resolve(paths.get("quality", "data/quality"))
        snapshots = resolve((cfg.get("snapshots") or {}).get("root", "data/snapshots"))
        self.base = base
        (base / "processed").mkdir(parents=True)
        (base / "quality").mkdir()
        for name in ("warehouse.duckdb", "lineage.json"):
            shutil.copyfile(processed / name, base / "processed" / name)
        shutil.copyfile(quality / "quality_report.json", base / "quality" / "quality_report.json")
        if (snapshots / "index.json").exists():
            for path in snapshots.rglob("*"):
                target = base / "snapshots" / path.relative_to(snapshots)
                if path.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif path.parent.name == "blobs":
                    target.parent.mkdir(parents=True, exist_ok=True)
                    try:  # lien physique : aucune copie de 128 Mo ; aucune faute n'ecrit un blob
                        os.link(path, target)
                    except OSError:
                        shutil.copyfile(path, target)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
        self.cfg = deepcopy(cfg)
        self.cfg.setdefault("paths", {}).update(
            processed=str(base / "processed"), quality=str(base / "quality"),
            audit=str(base / "audit"), reports=str(base / "reports"))
        self.cfg.setdefault("snapshots", {})["root"] = str(base / "snapshots")
        self.cfg.setdefault("llm", {})["enabled"] = False
        self.warehouse = base / "processed" / "warehouse.duckdb"
        self.quality_path = base / "quality" / "quality_report.json"
        lineage = json.loads((base / "processed" / "lineage.json").read_text(encoding="utf-8"))
        self.ctx: dict[str, Any] = {
            "warehouse_path": str(self.warehouse), "quality_paths": {"json": str(self.quality_path)},
            "sources": self.cfg.get("sources") or {}, "run_id": lineage.get("run_id"),
            "snapshot_id": lineage.get("snapshot_id"), "staging_paths": {"evaluation": "copie"},
        }

    def sql(self, statement: str, params: list | None = None) -> None:
        with duckdb.connect(str(self.warehouse)) as con:
            con.execute(statement, params or [])

    def query(self, statement: str, params: list | None = None):
        with duckdb.connect(str(self.warehouse), read_only=True) as con:
            return con.execute(statement, params or []).fetchone()

    def edit_json(self, path: Path, change: Callable[[dict], None]) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data), encoding="utf-8")

    def audit(self) -> dict[str, Any]:
        return AuditorAgent(cfg=self.cfg, run_id=self.ctx["run_id"]).execute(self.ctx)["audit"]


def _faults(focus: str) -> list[dict[str, Any]]:
    """Fautes injectees : (identifiant, description, controle attendu, application)."""

    def latest(ws: Workspace, kpi_id: str) -> int:
        return ws.query("SELECT max(year) FROM kpi_values WHERE kpi_id = ? AND iso3 = ? AND value IS NOT NULL",
                        [kpi_id, focus])[0]

    def tamper(ws):
        ws.sql("UPDATE kpi_values SET value = value + 0.05 WHERE kpi_id='account_ownership' AND iso3=? AND year=?",
               [focus, latest(ws, "account_ownership")])

    def unit(ws):
        ws.sql("UPDATE kpi_values SET unit='percent' WHERE kpi_id='branch_density' AND iso3=? AND year=?",
               [focus, latest(ws, "branch_density")])

    def aggregate(ws):
        ws.sql("INSERT INTO kpi_values SELECT * REPLACE ('WLD' AS iso3) FROM kpi_values "
               "WHERE kpi_id='account_ownership' AND iso3=? AND year=?", [focus, latest(ws, "account_ownership")])

    def zero(ws):
        kpi_id, iso3, year = ws.query("SELECT kpi_id, iso3, year FROM kpi_values WHERE value IS NULL "
                                      "AND iso3 <> 'PEERS' ORDER BY kpi_id, iso3, year LIMIT 1")
        ws.sql("UPDATE kpi_values SET value = 0 WHERE kpi_id=? AND iso3=? AND year=?", [kpi_id, iso3, year])

    def snapshot(ws):
        ws.sql("UPDATE kpi_values SET snapshot_id = 'v999' WHERE kpi_id='account_ownership' AND iso3=? AND year=?",
               [focus, latest(ws, "account_ownership")])

    def source_hash(ws):
        ws.edit_json(ws.quality_path, lambda q: q["inputs"]["findex"].update(sha256="0" * 64))

    def provisional(ws):
        catalog = yaml.safe_load(resolve(DEFAULT_CATALOG_PATH).read_text(encoding="utf-8"))
        catalog["kpis"]["saving_rate"]["verification"]["status"] = "provisional"
        path = ws.base / "catalog_provisional.yaml"
        path.write_text(yaml.safe_dump(catalog, sort_keys=False), encoding="utf-8")
        ws.cfg.setdefault("auditor", {})["catalog"] = str(path)

    def _insight(ws, value: float, text: str) -> dict[str, Any]:
        year = latest(ws, "account_ownership")
        return {"insight_id": "evaluation", "text": text.format(year=year),
                "claims": [{"kpi_id": "account_ownership", "iso3": focus, "year": year,
                            "value": value, "unit": "percent"}],
                "recommendation": "-", "confidence": "medium"}

    def wrong_number(ws):
        value = round(ws.query("SELECT value FROM kpi_values WHERE kpi_id='account_ownership' AND iso3=? "
                               "AND year=?", [focus, latest(ws, "account_ownership")])[0], 1) + 1.0
        ws.ctx["audit_insights"] = [_insight(ws, value, f"En {{year}}, {value:.1f} % des adultes avaient un compte.")]

    def uncited(ws):
        value = round(ws.query("SELECT value FROM kpi_values WHERE kpi_id='account_ownership' AND iso3=? "
                               "AND year=?", [focus, latest(ws, "account_ownership")])[0], 1)
        ws.ctx["audit_insights"] = [_insight(ws, value, f"En {{year}}, {value:.1f} % des adultes avaient un compte, "
                                                  "dont 99 % en ville.")]

    return [
        {"id": "tampered_value", "label": "Valeur KPI modifiee (+0,05)", "expected": "A1_recomputed_values", "apply": tamper},
        {"id": "wrong_unit", "label": "Mauvaise unite (densite en percent)", "expected": "B1_one_unit_per_kpi", "apply": unit},
        {"id": "aggregate_row", "label": "Ligne agregat WLD dans kpi_values", "expected": "B3_country_entities_only", "apply": aggregate},
        {"id": "zero_for_null", "label": "Zero au lieu de NULL", "expected": "A2_unavailable_rows_are_null", "apply": zero},
        {"id": "snapshot_mismatch", "label": "snapshot_id incoherent", "expected": "B5_snapshot_and_run_ids", "apply": snapshot},
        {"id": "source_hash", "label": "Hash source modifie (rapport qualite)", "expected": "B6_source_hashes", "apply": source_hash},
        {"id": "provisional_kpi", "label": "KPI provisoire dans le catalogue", "expected": "B8_catalog_definitions", "apply": provisional},
        {"id": "insight_wrong_number", "label": "Insight citant un mauvais chiffre", "expected": "F1_insights_grounded", "apply": wrong_number},
        {"id": "insight_uncited_number", "label": "Insight avec un nombre non cite", "expected": "F1_insights_grounded", "apply": uncited},
    ]


def evaluate(cfg: dict[str, Any] | None = None, out_dir: str | Path | None = None) -> dict[str, Any]:
    cfg = deepcopy(cfg or load_config())
    focus = normalize_iso3((cfg.get("kpi") or {}).get("focus"))
    out_dir = resolve(out_dir or (cfg.get("paths") or {}).get("audit", "data/audit"))
    results = []
    with tempfile.TemporaryDirectory(prefix="biflow_eval_") as tmp:
        baseline = Workspace(cfg, Path(tmp) / "baseline").audit()
        for fault in _faults(focus):
            ws = Workspace(cfg, Path(tmp) / fault["id"])
            fault["apply"](ws)
            audit = ws.audit()
            by_id = {c["check_id"]: c for c in audit["checks"]}
            expected = by_id.get(fault["expected"]) or {}
            if fault["expected"].startswith("F1"):
                detected = expected.get("result") == "warn" and not audit["insight_audit"][0]["accepted"]
                evidence = "; ".join(audit["insight_audit"][0]["reasons"])
            else:
                detected = expected.get("result") == "fail"
                evidence = str(expected.get("affected_rows", [])[:1])
            results.append({
                "id": fault["id"], "label": fault["label"], "expected_check": fault["expected"],
                "detected": detected, "verdict": audit["verdict"],
                "failing_checks": [c["check_id"] for c in audit["checks"] if c["result"] == "fail"],
                "evidence": evidence[:300],
            })
    summary = {
        "baseline": {"verdict": baseline["verdict"], "counts": baseline["counts"],
                     "publication": baseline["publication"], "timing_s": baseline["timing_s"]},
        "faults": results,
        "detected": sum(r["detected"] for r in results),
        "total": len(results),
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evaluation.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "evaluation.md").write_text(render(summary), encoding="utf-8")
    return summary


def render(summary: dict[str, Any]) -> str:
    base = summary["baseline"]
    lines = [
        "# Evaluation de l'Auditor par injection de fautes", "",
        f"Reference sans faute : verdict **{base['verdict']}** ({base['counts']}), "
        f"publication {base['publication']}, duree de l'audit {base['timing_s']} s.", "",
        f"**Fautes detectees : {summary['detected']} / {summary['total']}**", "",
        "| Faute injectee | Controle attendu | Detectee | Verdict | Controles en echec | Preuve |",
        "|---|---|---|---|---|---|",
    ]
    for r in summary["faults"]:
        lines.append(f"| {r['label']} | {r['expected_check']} | {'oui' if r['detected'] else 'NON'} | "
                     f"{r['verdict']} | {', '.join(r['failing_checks']) or '-'} | "
                     f"{r['evidence'].replace('|', '/')} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluation de l'Auditor par injection de fautes")
    parser.add_argument("--out", default=None, help="dossier de sortie (defaut : paths.audit)")
    args = parser.parse_args()
    summary = evaluate(out_dir=args.out)
    print(render(summary))
    return 0 if summary["detected"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
