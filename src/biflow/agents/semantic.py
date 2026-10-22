
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import duckdb
import pandas as pd
import yaml

from biflow.agents.base import AgentError, BaseAgent
from biflow.config import resolve
from biflow.utils.io import save_json, write_csv

VALUE_COLUMNS = [
    "kpi_id",
    "label",
    "unit",
    "source",
    "year",
    "dimension",
    "dimension_value",
    "value",
    "n_obs",
]

_AVG_RE = re.compile(r"^\s*avg\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$", re.I)


def _obs_expr(expr: str) -> str:
    match = _AVG_RE.match(expr)
    return f"count({match.group(1)})" if match else "count(*)"


def load_catalog(path: str | Path) -> dict[str, Any]:
    catalog_path = resolve(path)
    if not catalog_path.exists():
        raise AgentError(f"catalogue KPI introuvable : {catalog_path}")
    with open(catalog_path, encoding="utf-8") as handle:
        catalog = yaml.safe_load(handle) or {}
    if not catalog.get("kpis"):
        raise AgentError("le catalogue KPI ne contient aucune entree 'kpis'")
    return catalog


def _sql_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


class SemanticAgent(BaseAgent):
    name = "semantic"

    def _global_series(self, conn: duckdb.DuckDBPyConnection, expr: str) -> pd.DataFrame:
        query = f"""
            SELECT year, {expr} AS value, {_obs_expr(expr)} AS n_obs
            FROM cy
            WHERE is_country
            GROUP BY year
            ORDER BY year
        """
        return conn.execute(query).df().dropna(subset=["value"])

    def _by_dimension(
        self, conn: duckdb.DuckDBPyConnection, expr: str, dimension: str, year: int
    ) -> pd.DataFrame:
        query = f"""
            SELECT {dimension} AS dimension_value, {expr} AS value,
                   {_obs_expr(expr)} AS n_obs
            FROM cy
            WHERE is_country AND year = ? AND {dimension} IS NOT NULL
            GROUP BY {dimension}
            ORDER BY {dimension}
        """
        return conn.execute(query, [year]).df().dropna(subset=["value"])

    def _note(self, summaries: list[dict], issues: list[str]) -> str:
        compact = [
            {
                "kpi": item["id"],
                "annee": item["latest_year"],
                "valeur": item["latest_value"],
                "variation": item["change"],
                "unite": item["unit"],
            }
            for item in summaries[:14]
        ]
        result = self.ask_json(
            "Voici les derniers KPI calcules par le pipeline BI sur l'inclusion "
            "financiere mondiale. Ecris une lecture en francais (4 phrases max) : "
            "niveaux, tendances et limites. Ne recalcule aucun chiffre, n'invente rien. "
            'Reponds en JSON : {"lecture_fr": "..."}.\n'
            f"KPI : {json.dumps(compact, ensure_ascii=False)}\nAnomalies : {issues}",
            system="Tu es analyste BI senior. Tu commentes uniquement les chiffres fournis.",
            fallback={},
        )
        if isinstance(result, dict) and result.get("lecture_fr"):
            return str(result["lecture_fr"])
        if not summaries:
            return "Aucun KPI n'a pu etre calcule."
        best = max(summaries, key=lambda item: abs(item["change"] or 0))
        return (
            f"{len(summaries)} KPI calcules. La variation la plus forte concerne "
            f"{best['label']} ({best['change']:+.2f} {best['unit']} sur la derniere periode)."
        )

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        cfg = self.cfg.get("kpis") or {}
        catalog = load_catalog(cfg.get("catalog", "config/kpis.yaml"))
        entries = catalog["kpis"]

        year_path = Path(
            (ctx.get("staging_paths") or {}).get("country_year")
            or resolve("data/processed/country_year.parquet")
        )
        if not year_path.exists():
            raise AgentError(f"table pays-annee introuvable : {year_path}")

        conn = duckdb.connect()
        try:
            conn.execute(
                f"CREATE VIEW cy AS SELECT * FROM read_parquet('{_sql_path(year_path)}')"
            )
            columns = {row[0] for row in conn.execute("DESCRIBE cy").fetchall()}
            rows: list[dict[str, Any]] = []
            summaries: list[dict[str, Any]] = []
            issues: list[str] = []

            for entry in entries:
                kpi_id = entry["id"]
                expr = entry["expr"]
                label = entry.get("label", kpi_id)
                unit = entry.get("unit", "")
                try:
                    series = self._global_series(conn, expr)
                except duckdb.Error as exc:
                    issues.append(f"{kpi_id}: requete invalide ({exc})")
                    self.log.warning("[%s] KPI ignore : %s", kpi_id, exc)
                    continue
                if series.empty:
                    issues.append(f"{kpi_id}: aucune valeur disponible")
                    continue

                series = series.sort_values("year")
                median_obs = float(series["n_obs"].median())
                for year, n_obs in zip(series["year"], series["n_obs"]):
                    if median_obs and n_obs < 0.5 * median_obs:
                        issues.append(
                            f"{kpi_id}: annee {int(year)} partielle ({int(n_obs)} pays)"
                        )
                valid = series
                if median_obs:
                    valid = series[series["n_obs"] >= 0.5 * median_obs]
                if valid.empty:
                    valid = series
                for _, row in series.iterrows():
                    rows.append(
                        {
                            "kpi_id": kpi_id,
                            "label": label,
                            "unit": unit,
                            "source": entry.get("source"),
                            "year": int(row["year"]),
                            "dimension": "global",
                            "dimension_value": "all",
                            "value": float(row["value"]),
                            "n_obs": int(row["n_obs"]),
                        }
                    )

                latest = valid.iloc[-1]
                previous = valid.iloc[-2] if len(valid) > 1 else None
                summaries.append(
                    {
                        "id": kpi_id,
                        "label": label,
                        "unit": unit,
                        "source": entry.get("source"),
                        "direction": entry.get("direction", "up"),
                        "decimals": int(entry.get("decimals", 1)),
                        "latest_year": int(latest["year"]),
                        "latest_value": round(float(latest["value"]), 2),
                        "previous_value": round(float(previous["value"]), 2)
                        if previous is not None
                        else None,
                        "change": round(float(latest["value"] - previous["value"]), 2)
                        if previous is not None
                        else None,
                        "n_years": int(len(valid)),
                        "n_obs": int(latest["n_obs"]),
                    }
                )

                for dimension in entry.get("by", []) or []:
                    if dimension not in columns:
                        issues.append(f"{kpi_id}: dimension absente '{dimension}'")
                        continue
                    try:
                        by_dim = self._by_dimension(
                            conn, expr, dimension, int(latest["year"])
                        )
                    except duckdb.Error as exc:
                        issues.append(f"{kpi_id}/{dimension}: {exc}")
                        continue
                    for _, row in by_dim.iterrows():
                        rows.append(
                            {
                                "kpi_id": kpi_id,
                                "label": label,
                                "unit": unit,
                                "source": entry.get("source"),
                                "year": int(latest["year"]),
                                "dimension": dimension,
                                "dimension_value": str(row["dimension_value"]),
                                "value": float(row["value"]),
                                "n_obs": int(row["n_obs"]),
                            }
                        )
        finally:
            conn.close()

        if not rows:
            raise AgentError("aucun KPI calcule (verifier data/processed/country_year)")

        values = pd.DataFrame(rows, columns=VALUE_COLUMNS).sort_values(
            ["kpi_id", "dimension", "dimension_value", "year"]
        )
        out_dir = resolve(cfg.get("output", "outputs/kpis"))
        out_dir.mkdir(parents=True, exist_ok=True)
        values_path = out_dir / "kpi_values.parquet"
        values.to_parquet(values_path, index=False)
        write_csv(values, out_dir / "kpi_values.csv")

        catalog_out = out_dir / "kpi_catalog.yaml"
        shutil.copyfile(resolve(cfg.get("catalog", "config/kpis.yaml")), catalog_out)

        note = self._note(summaries, issues)
        summary = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "run_id": ctx.get("run_id"),
            "domain": catalog.get("domain"),
            "catalog": str(catalog_out),
            "values_path": str(values_path),
            "count": len(summaries),
            "items": summaries,
            "issues": issues,
            "llm_note": note,
        }
        summary_path = out_dir / "kpi_summary.json"
        save_json(summary, summary_path)

        lines = [
            "# Catalogue KPI - resultats",
            "",
            f"Domaine : {catalog.get('domain', '')}",
            "",
            "| KPI | Derniere annee | Valeur | Variation | Unite |",
            "|---|---|---|---|---|",
        ]
        for item in summaries:
            change = "n/a" if item["change"] is None else f"{item['change']:+.2f}"
            lines.append(
                f"| {item['label']} | {item['latest_year']} | "
                f"{item['latest_value']:.2f} | {change} | {item['unit']} |"
            )
        if issues:
            lines += ["", "## Points d'attention", ""] + [f"- {issue}" for issue in issues]
        lines += ["", "## Lecture", "", note]
        (out_dir / "kpi_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

        self.log.info("[semantic] %d KPI calcules -> %s", len(summaries), values_path)
        notes = dict(ctx.get("llm_notes") or {})
        notes["semantic"] = note
        return {
            "kpis": {
                "catalog": str(catalog_out),
                "values_path": str(values_path),
                "summary_path": str(summary_path),
                "count": len(summaries),
                "items": summaries,
                "issues": issues,
            },
            "kpi_values_path": str(values_path),
            "llm_notes": notes,
        }
