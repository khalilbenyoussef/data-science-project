
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from biflow.agents.base import AgentError, BaseAgent
from biflow.config import resolve
from biflow.utils.io import save_json

METRIC_LABELS = {
    "account_own": "Detention d'un compte (%)",
    "gender_gap_pp": "Ecart de genre (pp)",
    "atm_per_100k": "ATM pour 100 000 adultes",
    "brch_per_100k": "Agences pour 100 000 adultes",
    "depositors_per_1k": "Deposants pour 1 000 adultes",
    "borrowers_per_1k": "Emprunteurs pour 1 000 adultes",
    "gdp_pc": "PIB par habitant (USD)",
}


def _round(value: Any, digits: int = 2) -> float | None:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _latest_slice(df: pd.DataFrame, column: str, min_obs: int) -> tuple[int | None, pd.DataFrame]:
    sub = df.dropna(subset=[column])
    if sub.empty:
        return None, sub
    counts = sub.groupby("year").size()
    valid = counts[counts >= min_obs]
    year = int(valid.index.max()) if not valid.empty else int(counts.idxmax())
    return year, sub[sub["year"] == year]


def _rank(slice_df: pd.DataFrame, column: str, top_n: int, ascending: bool) -> list[dict]:
    data = slice_df.dropna(subset=[column]).drop_duplicates(subset=["iso3"])
    ordered = data.sort_values(column, ascending=ascending).head(top_n)
    return [
        {
            "iso3": row["iso3"],
            "country": row.get("country"),
            "value": _round(row[column]),
        }
        for _, row in ordered.iterrows()
    ]


def _improvers(df: pd.DataFrame, column: str, top_n: int) -> list[dict]:
    sub = df.dropna(subset=[column, "iso3"]).sort_values("year")
    rows = []
    for iso3, group in sub.groupby("iso3"):
        if group["year"].nunique() < 2:
            continue
        first = group.iloc[0]
        last = group.iloc[-1]
        rows.append(
            {
                "iso3": iso3,
                "country": last.get("country"),
                "first_year": int(first["year"]),
                "last_year": int(last["year"]),
                "first": _round(first[column]),
                "last": _round(last[column]),
                "delta": _round(last[column] - first[column]),
                "n_years": int(group["year"].nunique()),
            }
        )
    rows.sort(key=lambda item: -(item["delta"] or 0))
    return rows[:top_n]


def _correlation(df: pd.DataFrame, x: str, y: str, min_obs: int) -> dict | None:
    data = df[[x, y]].dropna()
    if len(data) < min_obs:
        return None
    corr = float(np.corrcoef(data[x], data[y])[0, 1])
    return {
        "x": x,
        "y": y,
        "r": _round(corr, 3),
        "n": int(len(data)),
        "strength": "forte" if abs(corr) >= 0.7 else "moderee" if abs(corr) >= 0.4 else "faible",
    }


def _kpi_trends(kpis: pd.DataFrame, min_years: int) -> list[dict]:
    global_rows = kpis[kpis["dimension"] == "global"]
    trends = []
    for kpi_id, group in global_rows.groupby("kpi_id"):
        group = group.sort_values("year")
        median_obs = float(group["n_obs"].median()) if "n_obs" in group else 0.0
        if median_obs:
            group = group[group["n_obs"] >= 0.5 * median_obs]
        if group.empty:
            continue
        first, last = group.iloc[0], group.iloc[-1]
        n_years = int(group["year"].nunique())
        span = max(1, int(last["year"]) - int(first["year"]))
        cagr = None
        if (
            n_years >= 2
            and last["unit"] not in ("%", "pp")
            and first["value"] > 0
            and last["value"] > 0
        ):
            cagr = _round(((last["value"] / first["value"]) ** (1 / span) - 1) * 100)
        trends.append(
            {
                "kpi_id": kpi_id,
                "label": last["label"],
                "unit": last["unit"],
                "direction": "up",
                "first_year": int(first["year"]),
                "last_year": int(last["year"]),
                "first": _round(first["value"]),
                "last": _round(last["value"]),
                "change": _round(last["value"] - first["value"]) if n_years >= 2 else None,
                "cagr_pct": cagr,
                "n_years": n_years,
            }
        )
    return trends


def build_facts(cy: pd.DataFrame, kpis: pd.DataFrame, cfg: dict) -> dict[str, Any]:
    top_n = int(cfg.get("top_n", 10))
    min_years = int(cfg.get("min_years", 3))
    min_obs = int(cfg.get("correlation_min_obs", 30))

    countries = cy[cy["is_country"].fillna(False).astype(bool)]
    facts: dict[str, Any] = {
        "coverage": {
            "rows": int(len(countries)),
            "countries": int(countries["iso3"].nunique()),
            "year_min": int(countries["year"].min()) if len(countries) else None,
            "year_max": int(countries["year"].max()) if len(countries) else None,
            "aggregates_excluded": int((~cy["is_country"].fillna(False).astype(bool)).sum()),
        },
        "kpi_trends": _kpi_trends(kpis, min_years),
        "rankings": {},
        "improvers": {},
        "correlations": [],
        "outliers": [],
        "regional": [],
    }

    for column in ("account_own", "gender_gap_pp", "atm_per_100k", "brch_per_100k",
                   "depositors_per_1k", "borrowers_per_1k", "gdp_pc"):
        if column not in countries.columns:
            continue
        year, latest = _latest_slice(countries, column, min_obs=min_obs)
        if year is None or latest.empty:
            continue
        facts["rankings"][column] = {
            "year": year,
            "n_countries": int(latest["iso3"].nunique()),
            "top": _rank(latest, column, top_n, ascending=False),
            "bottom": _rank(latest, column, top_n, ascending=True),
        }

    for column in ("account_own", "atm_per_100k", "brch_per_100k"):
        if column in countries.columns:
            facts["improvers"][column] = _improvers(countries, column, top_n)

    year, latest_inclusion = _latest_slice(countries, "account_own", min_obs=min_obs)
    if year is not None and not latest_inclusion.empty:
        for other in ("gdp_pc", "atm_per_100k", "brch_per_100k", "depositors_per_1k",
                      "borrowers_per_1k", "gender_gap_pp"):
            if other in latest_inclusion.columns:
                corr = _correlation(latest_inclusion, "account_own", other, min_obs)
                if corr:
                    corr["year"] = year
                    facts["correlations"].append(corr)
        values = latest_inclusion["account_own"].dropna()
        if len(values) >= 10:
            mean, std = float(values.mean()), float(values.std())
            if std > 0:
                for _, row in latest_inclusion.dropna(subset=["account_own"]).iterrows():
                    z = (row["account_own"] - mean) / std
                    if abs(z) >= 2.5:
                        facts["outliers"].append(
                            {
                                "iso3": row["iso3"],
                                "country": row.get("country"),
                                "value": _round(row["account_own"]),
                                "z_score": _round(z),
                                "year": int(row["year"]),
                            }
                        )
        facts["outliers"].sort(key=lambda item: -abs(item["z_score"] or 0))

    if "region" in countries.columns:
        region_year, region_slice = _latest_slice(countries, "account_own", min_obs=min_obs)
        if region_year is not None and "region" in region_slice.columns:
            grouped = (
                region_slice.dropna(subset=["region"])
                .groupby("region")
                .agg(
                    account_own=("account_own", "mean"),
                    atm_per_100k=("atm_per_100k", "mean"),
                    brch_per_100k=("brch_per_100k", "mean"),
                    gender_gap_pp=("gender_gap_pp", "mean"),
                    n_countries=("iso3", "nunique"),
                )
                .reset_index()
                .sort_values("account_own", ascending=False)
            )
            facts["regional"] = [
                {
                    "region": row["region"],
                    "year": region_year,
                    "account_own": _round(row["account_own"]),
                    "atm_per_100k": _round(row["atm_per_100k"]),
                    "brch_per_100k": _round(row["brch_per_100k"]),
                    "gender_gap_pp": _round(row["gender_gap_pp"]),
                    "n_countries": int(row["n_countries"]),
                }
                for _, row in grouped.iterrows()
            ]

    return facts


def fallback_narrative(facts: dict) -> dict[str, Any]:
    trends = [t for t in facts["kpi_trends"] if t["change"] is not None]
    rising = sorted(trends, key=lambda t: -(t["change"] or 0))[:3]
    falling = sorted(trends, key=lambda t: (t["change"] or 0))[:2]
    findings = []
    for item in rising:
        findings.append(
            f"{item['label']} : {item['first']} ({item['first_year']}) -> "
            f"{item['last']} ({item['last_year']}), soit {item['change']:+.2f} {item['unit']}."
        )
    for item in falling:
        findings.append(
            f"{item['label']} recule de {item['change']:+.2f} {item['unit']} "
            f"entre {item['first_year']} et {item['last_year']}."
        )
    inclusion = facts["rankings"].get("account_own")
    if inclusion and inclusion["top"] and inclusion["bottom"]:
        findings.append(
            f"En {inclusion['year']}, {inclusion['top'][0]['country']} affiche "
            f"{inclusion['top'][0]['value']:.1f} % de detention de compte contre "
            f"{inclusion['bottom'][0]['value']:.1f} % pour {inclusion['bottom'][0]['country']}."
        )
    gap = next((t for t in trends if t["kpi_id"] == "gender_gap"), None)
    if gap:
        findings.append(
            f"L'ecart de genre reste de {gap['last']:.1f} points de pourcentage en {gap['last_year']}."
        )
    summary = (
        "L'inclusion financiere progresse sur la periode, portee par les pays a "
        "revenu intermediaire, mais les ecarts entre pays et entre genres restent "
        "importants. Les densites d'agences et d'ATM expliquent une partie des "
        "differences observees."
    )
    recommendations = [
        "Cibler les pays du bas du classement avec les densites d'agences et d'ATM les plus faibles.",
        "Prioriser les programmes d'inclusion des femmes dans les regions ou l'ecart de genre depasse 15 pp.",
        "Suivre les comptes inactifs : l'ouverture d'un compte ne garantit pas l'usage.",
    ]
    return {
        "executive_summary": summary,
        "key_findings": findings[:6],
        "recommendations": recommendations,
    }


def _markdown(facts: dict, narrative: dict) -> str:
    coverage = facts["coverage"]
    lines = [
        "# Rapport d'insights BI - Inclusion financiere",
        "",
        f"Periode : {coverage['year_min']} - {coverage['year_max']} | "
        f"{coverage['countries']} pays | {coverage['rows']:,} observations pays-annee",
        "",
        "## Synthese",
        "",
        narrative.get("executive_summary", ""),
        "",
        "## KPI mondiaux",
        "",
        "| KPI | Premier | Dernier | Variation | CAGR |",
        "|---|---|---|---|---|",
    ]
    for item in facts["kpi_trends"]:
        change = "n/a" if item["change"] is None else f"{item['change']:+.2f}"
        cagr = "n/a" if item["cagr_pct"] is None else f"{item['cagr_pct']:+.2f} %"
        lines.append(
            f"| {item['label']} | {item['first']:.2f} ({item['first_year']}) | "
            f"{item['last']:.2f} ({item['last_year']}) | {change} | {cagr} |"
        )
    inclusion = facts["rankings"].get("account_own")
    if inclusion:
        lines += [
            "",
            f"## Classement detention de compte ({inclusion['year']})",
            "",
            "**Top 5** : "
            + ", ".join(
                f"{row['country']} ({row['value']:.1f} %)" for row in inclusion["top"][:5]
            ),
            "",
            "**Bas 5** : "
            + ", ".join(
                f"{row['country']} ({row['value']:.1f} %)" for row in inclusion["bottom"][:5]
            ),
        ]
    if facts["improvers"].get("account_own"):
        lines += ["", "## Plus fortes progressions (comptes)", ""]
        lines += [
            f"- {row['country']} : {row['first']:.1f} % ({row['first_year']}) -> "
            f"{row['last']:.1f} % ({row['last_year']})"
            for row in facts["improvers"]["account_own"][:5]
        ]
    if facts["correlations"]:
        lines += ["", "## Correlations (coupe transversale)", ""]
        lines += [
            f"- {METRIC_LABELS.get(c['x'], c['x'])} vs {METRIC_LABELS.get(c['y'], c['y'])} : "
            f"r = {c['r']} ({c['strength']}, n = {c['n']})"
            for c in facts["correlations"]
        ]
    if facts["outliers"]:
        lines += ["", "## Pays atypiques (|z| >= 2.5)", ""]
        lines += [
            f"- {row['country']} : {row['value']:.1f} % (z = {row['z_score']})"
            for row in facts["outliers"][:6]
        ]
    lines += ["", "## Recommandations", ""] + [
        f"- {item}" for item in narrative.get("recommendations", [])
    ]
    lines += ["", "## Limites", "",
              "- Les KPI sont des moyennes simples de pays, non ponderees par la population.",
              "- Findex est enquete par vagues ; FAS est annuel mais incomplet pour certains pays.",
              "- Les correlations sont descriptives et ne prouvent pas de causalite."]
    return "\n".join(lines) + "\n"


class AnalystAgent(BaseAgent):
    name = "analyst"

    def _narrative(self, facts: dict) -> dict[str, Any]:
        fallback = fallback_narrative(facts)
        gap = next((item for item in facts["kpi_trends"] if item["kpi_id"] == "gender_gap"), None)
        compact = {
            "kpi_trends": facts["kpi_trends"][:12],
            "top": facts["rankings"].get("account_own", {}).get("top", [])[:5],
            "bottom": facts["rankings"].get("account_own", {}).get("bottom", [])[:5],
            "correlations": facts["correlations"],
            "improvers": facts["improvers"].get("account_own", [])[:5],
            "outliers": facts["outliers"][:5],
            "gender_gap_direction": None
            if gap is None
            else ("hausse" if (gap["change"] or 0) > 0 else "baisse"),
        }
        result = self.ask_json(
            "Tu rediges un rapport BI sur l'inclusion financiere mondiale. "
            "Tu dois REUTILISER uniquement les faits verifies ci-dessous : "
            "n'ajoute aucun chiffre, aucune cause et aucun pays absent de ces faits. "
            "Le champ change donne le sens (positif = hausse). Pour une baisse, "
            "exprime la variation en valeur absolue (ex: 'a recule de 4,04 points'), "
            "jamais 'de -4,04'. Pour un KPI exprime en %, une variation est en points "
            "de pourcentage (pp). "
            "Reponds en francais, JSON strict avec les cles : executive_summary (str), "
            "key_findings (list[str], 4 a 6), recommendations (list[str], 3 a 5).\n"
            f"Faits verifies : {json.dumps(fallback['key_findings'], ensure_ascii=False)}\n"
            f"Donnees : {json.dumps(compact, ensure_ascii=False)}",
            system="Tu es analyste BI senior specialise en inclusion financiere.",
            fallback={},
        )
        if (
            isinstance(result, dict)
            and isinstance(result.get("executive_summary"), str)
            and isinstance(result.get("key_findings"), list)
            and isinstance(result.get("recommendations"), list)
        ):
            return {
                "executive_summary": result["executive_summary"],
                "key_findings": [str(item) for item in result["key_findings"]][:6],
                "recommendations": [str(item) for item in result["recommendations"]][:5],
            }
        return fallback_narrative(facts)

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        cy_path = Path(
            (ctx.get("staging_paths") or {}).get("country_year")
            or resolve("data/processed/country_year.parquet")
        )
        kpi_path = Path(
            ctx.get("kpi_values_path") or resolve("outputs/kpis/kpi_values.parquet")
        )
        if not cy_path.exists() or not kpi_path.exists():
            raise AgentError(
                f"entrees manquantes : country_year={cy_path.exists()}, kpi_values={kpi_path.exists()}"
            )

        cy = pd.read_parquet(cy_path)
        kpis = pd.read_parquet(kpi_path)
        facts = build_facts(cy, kpis, self.cfg.get("analysis") or {})
        narrative = self._narrative(facts)

        out_dir = resolve("outputs/insights")
        out_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "run_id": ctx.get("run_id"),
            "narrative": narrative,
            "facts": facts,
        }
        json_path = out_dir / "insights.json"
        save_json(payload, json_path)
        md_path = out_dir / "insights.md"
        md_path.write_text(_markdown(facts, narrative), encoding="utf-8")

        self.log.info(
            "[analyst] %d KPI, %d correlations, %d atypiques -> %s",
            len(facts["kpi_trends"]),
            len(facts["correlations"]),
            len(facts["outliers"]),
            json_path,
        )
        notes = dict(ctx.get("llm_notes") or {})
        notes["analyst"] = narrative["executive_summary"]
        return {
            "insights": {
                "path": str(json_path),
                "markdown": str(md_path),
                "summary": narrative["executive_summary"],
                "key_findings": narrative["key_findings"],
                "recommendations": narrative["recommendations"],
                "n_kpis": len(facts["kpi_trends"]),
            },
            "insights_path": str(json_path),
            "llm_notes": notes,
        }
