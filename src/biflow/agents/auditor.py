"""S12 - BI Auditor / XAI : verification independante des KPI publies.

Deterministe : recalcul depuis `fact` sans le code KPI, controles de
coherence et de tracabilite. Un verdict FAIL est une decision (jamais retente).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Mapping

import duckdb

from biflow.agents.base import AgentError, BaseAgent
from biflow.config import resolve
from biflow.tools.audit_explain import build_explanations, decision_log, explain_change
from biflow.tools.audit_report import build_report, write_report
from biflow.tools.audit_text import change_text, rephrase, template_text
from biflow.tools.insights import audit_insights
from biflow.tools.audit_checks import (
    RawSources,
    caveat_checks,
    catalog_checks,
    count_results,
    entity_checks,
    load_catalogs,
    user_fact_check,
    make_check,
    provenance_checks,
    publication_decisions,
    quality_gate_check,
    raw_to_fact_check,
    read_kpi_rows,
    recompute_checks,
    unit_checks,
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

    # ------------------------------------------------------------------ textes
    def _ask(self):
        """Fonction de reformulation LLM, ou None (LLM desactive / indisponible)."""
        if self.get_llm() is None:
            return None
        return lambda prompt, system: self.ask_text(prompt, system=system)

    def examples(self, explanations: list[dict[str, Any]], focus: str,
                 min_change_pp: float, budget: int) -> list[dict[str, Any]]:
        """3 explications du rapport : niveau (detention de compte), variation
        (ecart hommes-femmes entre les deux dernieres vagues), comparaison aux pairs
        (densite d'agences). Seules celles-ci peuvent etre reformulees par LLM."""
        by_key = {(e["kpi_id"], e["iso3"], e["year"]): e for e in explanations}

        def latest(kpi_id, iso3, n=None):
            """Les n dernieres annees disponibles (toutes si n est None)."""
            years = sorted(y for (k, i, y), e in by_key.items()
                           if k == kpi_id and i == iso3 and e["value"] is not None)
            if n is None:
                return years
            return years[-n:] if len(years) >= n else []

        specs = []
        if latest("account_ownership", focus, 1):
            year, = latest("account_ownership", focus, 1)
            specs.append(("Détention de compte", by_key[("account_ownership", focus, year)], None, None))
        if len(latest("gender_gap", focus, 2)) == 2:
            before, after = latest("gender_gap", focus, 2)
            left, right = by_key[("gender_gap", focus, before)], by_key[("gender_gap", focus, after)]
            specs.append(("Écart hommes-femmes", right, left, explain_change(left, right, min_change_pp)))
        common = sorted(set(latest("branch_density", focus)) & set(latest("branch_density", "PEERS")))
        if common:
            left, right = by_key[("branch_density", "PEERS", common[-1])], by_key[("branch_density", focus, common[-1])]
            specs.append(("Densité d'agences et pairs", right, left, explain_change(left, right, min_change_pp)))

        ask = self._ask()
        out = []
        for title, record, other, change in specs:
            templates = {lang: (change_text(change, other, record, lang) if change else template_text(record, lang))
                         for lang in ("fr", "en")}
            french = rephrase(templates["fr"], "fr", ask if len(out) < budget else None)
            self.log.info("[auditor] exemple '%s' : texte %s%s", title, french["origin"],
                          f" (LLM écarté : nombres non justifiés {french['unsupported_numbers']})"
                          if french.get("llm_status") == "rejected_ungrounded" else "")
            out.append({
                "title": title, "kpi_id": record["kpi_id"], "iso3": record["iso3"], "year": record["year"],
                "compare": None if other is None else {"iso3": other["iso3"], "year": other["year"]},
                "change": change, "template": templates,
                "text": {"fr": french["text"], "en": templates["en"]},
                "origin": {"fr": french["origin"], "en": "template"},
                "llm": {k: v for k, v in french.items() if k not in ("text", "origin")},
                "record": record,
            })
        return out

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
        index = _read_json(snapshot_root / "index.json")
        index_entry = next((e for e in index.get("snapshots") or []
                            if e.get("snapshot_id") == snapshot_id), None)
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
            "index_entry": index_entry,
            "raw_paths": raw_paths,
            "catalog_path": resolve(audit_cfg.get("catalog", DEFAULT_CATALOG_PATH)),
            # Meme regle que le calcul KPI : variable d'environnement ou chemin par defaut
            "user_catalog_path": resolve(os.getenv("BIFLOW_USER_CATALOG") or "config/kpi_catalog.user.yaml"),
            "aliases": ((self.cfg.get("countries") or {}).get("name_to_iso3")) or {},
            "audit_dir": resolve(paths.get("audit", "data/audit")),
            "source_meta": {
                name: {"file": str(raw_paths[name]) if name in raw_paths else None,
                       "sha256": ((manifest.get("sources") or {}).get(name) or {}).get("sha256")
                       or ((lineage.get("inputs") or {}).get(name) or {}).get("sha256")}
                for name in set(raw_paths) | set(lineage.get("inputs") or {})
            },
            "focus": focus,
            "peers": [p for p in peers if p and p != focus],
            "tolerance": float(audit_cfg.get("tolerance", 1e-9)),
            "min_change_pp": float(audit_cfg.get("min_meaningful_change_pp", 2.0)),
            # ETL execute dans ce run : lineage, qualite et KPI doivent porter ce run_id
            "require_same_run": bool(ctx.get("staging_paths")),
            "sources": ctx.get("sources") or self.cfg.get("sources") or {},
            "run_id": ctx.get("run_id") or self.run_id,
        }

    # ------------------------------------------------------------------ audit
    def audit(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        """Controles A (recalcul) et B (coherence, tracabilite, avertissements)."""
        inp = self._inputs(ctx)
        catalog, catalog_sha256, user_catalog_sha256 = load_catalogs(inp["catalog_path"], inp["user_catalog_path"])
        fas_series = (inp["sources"].get("fas") or {}).get("series") or {}
        with duckdb.connect(str(inp["warehouse"]), read_only=True) as con:
            rows = read_kpi_rows(con)
            dim = con.execute("SELECT iso3, country, is_aggregate FROM country_dim").fetchall()
            checks, recomputed = recompute_checks(
                con, catalog, rows, inp["focus"], inp["peers"], inp["tolerance"])
            raw = RawSources(inp["raw_paths"], inp["sources"], inp["aliases"])
            raw_check, raw_lookups = raw_to_fact_check(recomputed, raw, fas_series)
            checks.append(raw_check)
            checks.append(user_fact_check(con, raw, inp["lineage"]))
            checks += unit_checks(rows, catalog)
            checks += entity_checks(con, rows, inp["focus"], inp["peers"])
            checks += provenance_checks(
                con, rows, run_id=inp["run_id"], require_same_run=inp["require_same_run"],
                snapshot_id=inp["snapshot_id"], index_entry=inp["index_entry"], manifest=inp["manifest"],
                snapshot_root=inp["snapshot_root"] if inp["manifest"] else None,
                lineage=inp["lineage"], quality=inp["quality"])
        checks += catalog_checks(rows, catalog, catalog_sha256, user_catalog_sha256)
        checks.append(quality_gate_check(inp["quality"]))
        checks += caveat_checks(rows, catalog, inp["quality"], recomputed, inp["min_change_pp"])
        return {"inputs": inp, "catalog": catalog, "catalog_sha256": catalog_sha256, "rows": rows,
                "country_names": {iso3: name for iso3, name, _ in dim},
                "aggregates": sorted(iso3 for iso3, _, aggregate in dim if aggregate),
                "recomputed": recomputed, "raw_lookups": raw_lookups, "checks": checks}

    @staticmethod
    def write_outputs(warehouse: Path, decisions: Mapping[tuple, str],
                      explanations: list[dict[str, Any]], audit_dir: Path) -> Path:
        """Seules ecritures de l'Auditor : kpi_values.publication_status, table
        kpi_explanations (+ explanations.jsonl) et export Parquet. Ces tables
        n'entrent pas dans l'empreinte du contenu du warehouse."""
        parquet = warehouse.with_name("kpi_values.parquet")
        tmp = parquet.with_name(f".{parquet.name}.tmp")
        documents = [((e["kpi_id"], e["iso3"], e["year"]), json.dumps(e, ensure_ascii=False, default=str))
                     for e in explanations]
        with duckdb.connect(str(warehouse)) as con:
            con.execute("BEGIN TRANSACTION")
            try:
                con.executemany(
                    "UPDATE kpi_values SET publication_status = ? WHERE kpi_id = ? AND iso3 = ? AND year = ?",
                    [(status, *key) for key, status in sorted(decisions.items())])
                con.execute("CREATE OR REPLACE TABLE kpi_explanations (kpi_id VARCHAR NOT NULL, "
                            "iso3 VARCHAR NOT NULL, year INTEGER NOT NULL, explanation JSON NOT NULL, "
                            "PRIMARY KEY (kpi_id, iso3, year))")
                if documents:
                    con.executemany("INSERT INTO kpi_explanations VALUES (?, ?, ?, ?)",
                                    [(*key, document) for key, document in documents])
                con.execute("COMMIT")
            except Exception:
                con.execute("ROLLBACK")
                raise
            target = str(tmp).replace("'", "''")
            con.execute(f"COPY (SELECT * FROM kpi_values ORDER BY kpi_id, iso3, year) "
                        f"TO '{target}' (FORMAT PARQUET)")
        os.replace(tmp, parquet)
        audit_dir.mkdir(parents=True, exist_ok=True)
        jsonl = audit_dir / "explanations.jsonl"
        jsonl_tmp = jsonl.with_name(f".{jsonl.name}.tmp")
        jsonl_tmp.write_text("".join(document + "\n" for _, document in documents), encoding="utf-8")
        os.replace(jsonl_tmp, jsonl)
        return parquet

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        result = self.audit(ctx)
        checks = result["checks"]
        decisions = publication_decisions(result["rows"], checks)
        insight_audit = None
        if ctx.get("audit_insights") is not None:  # insights a auditer (liste d'Insight)
            insight_audit = audit_insights(ctx["audit_insights"], result["rows"], decisions)
            rejected = [i for i in insight_audit if not i["accepted"]]
            checks.append(make_check(
                "F1_insights_grounded", "insight", "warn" if rejected else "pass",
                f"{len(insight_audit)} insight(s) audité(s), {len(rejected)} rejeté(s) : claims conformes à "
                "kpi_values (valeur, unité, année, ligne approuvée) et nombres du texte justifiés",
                [{"insight_id": i["insight_id"], "reasons": i["reasons"]} for i in rejected],
                affects_publication=False))
            for item in rejected:
                self.log.warning("[auditor] insight %s rejete : %s", item["insight_id"], "; ".join(item["reasons"]))
        verdict = verdict_of(checks)
        counts = count_results(checks)
        inp = result["inputs"]
        explanations = build_explanations(
            result["rows"], result["recomputed"], result["raw_lookups"], result["catalog"],
            result["catalog_sha256"], decisions, checks, inp["quality"], inp["source_meta"],
            result["country_names"], inp["snapshot_id"])
        for record in explanations:  # gabarits deterministes, toujours disponibles
            record["narrative"] = {"fr": template_text(record, "fr"), "en": template_text(record, "en"),
                                   "origin": "template"}
        audit_cfg = self.cfg.get("auditor") or {}
        examples = self.examples(explanations, inp["focus"], inp["min_change_pp"],
                                 int(audit_cfg.get("llm_examples", 3)))
        self.write_outputs(inp["warehouse"], decisions, explanations, inp["audit_dir"])
        by_status = {status: 0 for status in ("approved", "approved_with_review_note", "blocked")}
        for status in decisions.values():
            by_status[status] += 1
        self.log.info("[auditor] verdict %s : %d pass, %d warn, %d fail (%d lignes KPI)",
                      verdict, counts["pass"], counts["warn"], counts["fail"], len(result["rows"]))
        self.log.info("[auditor] publication : %s", by_status)
        for check in checks:
            if check["result"] == "fail":
                self.log.warning("[auditor] %s : %s", check["check_id"], check["detail"])
        notes = dict(ctx.get("llm_notes") or {})
        notes["auditor"] = f"verdict {verdict} ({counts['fail']} échec(s), {counts['warn']} alerte(s))"
        audit = {
            "verdict": verdict,
            "counts": counts,
            "run_id": result["inputs"]["run_id"],
            "snapshot_id": result["inputs"]["snapshot_id"],
            "rows": len(result["rows"]),
            "publication": by_status,
            "checks": checks,
            "decision_log": decision_log(
                snapshot=ctx.get("snapshot") or {"snapshot_id": inp["snapshot_id"],
                                                 "status": (inp["index_entry"] or {}).get("status")},
                lineage=inp["lineage"], quality=inp["quality"], aggregates=result["aggregates"],
                kpi_rows=result["rows"], audit_counts=counts, verdict=verdict),
            "explanations_path": str(inp["audit_dir"] / "explanations.jsonl"),
            "examples": examples,
            "insight_audit": insight_audit,
        }
        elapsed = time.perf_counter() - started
        audit["timing_s"] = round(elapsed, 3)
        audit["report_paths"] = write_report(build_report(audit, decisions, elapsed), inp["audit_dir"])
        self.log.info("[auditor] rapport : %s (%.1f s)", audit["report_paths"]["markdown"], elapsed)
        return {"audit": audit, "llm_notes": notes}
