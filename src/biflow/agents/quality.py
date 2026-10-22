
from __future__ import annotations

import json
import math
from typing import Any, Mapping

import pandas as pd

from biflow.agents.base import AgentError, BaseAgent
from biflow.agents.etl import FAS_REQUIRED, FINDEX_REQUIRED, GDP_REQUIRED, YEAR_RE
from biflow.config import resolve
from biflow.state import PipelineState
from biflow.tools.dictionary import FINDEX_LABELS, GDP_LABELS
from biflow.utils.countries import invalid_iso3, is_aggregate, normalize_iso3
from biflow.utils.io import load_source, save_json, write_csv

SEVERITY_WEIGHT = {"critical": 0.35, "high": 0.15, "medium": 0.06, "low": 0.02}
MANDATORY_SOURCES = ("findex", "fas", "gdp")
KEY_COLUMNS = {
    "findex": ["codewb", "year", "group", "group2"],
    "fas": ["SERIES_CODE"],
    "gdp": ["iso3", "year", "indicator_code"],
}
REQUIRED_COLUMNS = {"findex": FINDEX_REQUIRED, "fas": FAS_REQUIRED, "gdp": GDP_REQUIRED}
FAS_GDP_PERCENT_SERIES = {
    "OUTD_COMBANK.POGDP": "deposits_pct_gdp",
    "OUTL_COMBANK.POGDP": "loans_pct_gdp",
}
DIAGNOSTIC_COLUMNS = [
    "source", "code", "iso3", "country", "year", "series_code", "indicator_code",
    "original_value", "value", "unit", "threshold", "reason",
]


def _issue(
    code: str,
    severity: str,
    message: str,
    column: str | None = None,
    count: int | None = None,
    pct: float | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "column": column,
        "count": count,
        "pct": None if pct is None else round(float(pct), 2),
    }


def _check_ranges(name: str, df: pd.DataFrame, cfg: dict) -> list[dict]:
    issues: list[dict] = []
    if name == "findex":
        lo = float(cfg.get("rate_columns_min", 0.0))
        hi = float(cfg.get("rate_columns_max", 1.0))
        columns = [c for c in FINDEX_LABELS if c in df.columns]
        for column in columns:
            series = pd.to_numeric(df[column], errors="coerce").dropna()
            bad = int(((series < lo) | (series > hi + 0.001)).sum())
            if bad:
                issues.append(
                    _issue(
                        "rate_out_of_range",
                        "high",
                        f"[{name}] {column} contient des valeurs hors [{lo}, {hi}]",
                        column=column,
                        count=bad,
                        pct=bad / len(df) * 100 if len(df) else 0,
                    )
                )
    elif name == "fas":
        year_cols = [c for c in df.columns if str(c).isdigit()]
        if year_cols:
            values = df[year_cols].apply(pd.to_numeric, errors="coerce")
            negative = int((values < 0).sum().sum())
            if negative:
                issues.append(
                    _issue(
                        "negative_values",
                        "medium",
                        f"[{name}] {negative} valeurs negatives dans les colonnes annees",
                        count=negative,
                    )
                )
    return issues


def _country_check(name: str, df: pd.DataFrame) -> tuple[list[dict], dict]:
    issues: list[dict] = []
    if name == "findex" and "codewb" in df.columns:
        codes = df["codewb"].dropna().astype(str)
        aggregates = sorted({c for c in codes if is_aggregate(c)})
        unknown = invalid_iso3(codes)
        if unknown:
            issues.append(
                _issue(
                    "invalid_country_code",
                    "medium",
                    f"[{name}] codes pays inconnus : {unknown[:10]}",
                    count=len(unknown),
                )
            )
        return issues, {"aggregates": aggregates, "n_aggregates": len(aggregates)}
    if name == "fas" and "SERIES_CODE" in df.columns:
        codes = df["SERIES_CODE"].dropna().astype(str).str.split(".").str[0]
        unknown = invalid_iso3(codes)
        if unknown:
            issues.append(
                _issue(
                    "invalid_country_code",
                    "medium",
                    f"[{name}] codes pays inconnus : {unknown[:10]}",
                    count=len(unknown),
                )
            )
        return issues, {"n_prefixes": int(codes.nunique())}
    if name == "gdp" and "iso3" in df.columns:
        unknown = invalid_iso3(df["iso3"].dropna().astype(str))
        if unknown:
            issues.append(
                _issue(
                    "invalid_country_code",
                    "low",
                    f"[{name}] codes pays inconnus : {unknown[:10]}",
                    count=len(unknown),
                )
            )
        return issues, {}
    return issues, {}


def _check_schema(name: str, df: pd.DataFrame, source_cfg: dict) -> tuple[list[dict], dict]:
    """Validate ETL structure, not completeness of survey waves or observations."""
    if name not in REQUIRED_COLUMNS:
        return [], {}
    issues = []
    missing_columns = [c for c in REQUIRED_COLUMNS[name] if c not in df.columns]
    if missing_columns:
        issues.append(_issue(
            "missing_required_columns", "critical",
            f"[{name}] colonnes obligatoires absentes : {', '.join(missing_columns)}",
            count=len(missing_columns),
        ))

    for column in KEY_COLUMNS[name]:
        if column not in df.columns:
            continue
        text = df[column].astype("string").str.strip()
        missing = df[column].isna() | text.str.upper().isin(["", "NAN", "<NA>", "NONE", "NULL", "NAT"])
        if missing.any():
            issues.append(_issue(
                "missing_key", "critical", f"[{name}] cle manquante : {column}",
                column=column, count=int(missing.sum()),
            ))
        valid = pd.Series(True, index=df.index)
        if column in ("codewb", "iso3"):
            valid = df[column].map(normalize_iso3).map(
                lambda value: isinstance(value, str) and len(value) == 3
                and value.isascii() and value.isalpha()
            )
        elif column == "year":
            numeric = pd.to_numeric(df[column], errors="coerce")
            valid = numeric.notna() & numeric.mod(1).eq(0)
        elif column == "SERIES_CODE":
            valid = text.str.upper().str.fullmatch(
                r"[A-Z]{3}\.[A-Z0-9_]+(?:\.[A-Z0-9_]+)+\.A", na=False,
            )
            prefix = text.str.split(".").str[0].map(normalize_iso3)
            valid &= prefix.notna()
        elif column == "indicator_code":
            valid = df[column].astype("string").str.fullmatch(
                r"[A-Z0-9_]+(?:\.[A-Z0-9_]+)+", na=False,
            )
        else:
            valid = df[column].map(lambda value: isinstance(value, str))
        invalid = ~valid.fillna(False) & ~missing
        if invalid.any():
            issues.append(_issue(
                "invalid_key", "critical", f"[{name}] cle invalide : {column}",
                column=column, count=int(invalid.sum()),
            ))

    if name == "findex":
        expected = list(source_cfg.get("indicators", []) if source_cfg else FINDEX_LABELS)
        available = [code for code in expected if code in df.columns]
    elif name == "fas":
        years = [c for c in df.columns if YEAR_RE.fullmatch(str(c))]
        if not years:
            issues.append(_issue(
                "missing_year_columns", "critical", "[fas] aucune colonne annee exploitable",
            ))
        codes = df["SERIES_CODE"].astype("string").str.strip().str.upper() if "SERIES_CODE" in df else pd.Series(dtype="string")
        suffixes = set(codes.str.split(".", n=1).str[1].str.rsplit(".", n=1).str[0].dropna())
        # Without source configuration, only structural series coverage can be checked.
        expected = list((source_cfg.get("series") or {}).values())
        available = sorted(suffixes.intersection(expected) if source_cfg else suffixes)
    else:
        expected = list(source_cfg.get("indicators", GDP_LABELS))
        codes = set(df["indicator_code"].dropna()) if "indicator_code" in df else set()
        available = [code for code in expected if code in codes]
    if not available:
        issues.append(_issue(
            "missing_indicator_coverage", "critical",
            f"[{name}] aucun indicateur requis present (minimum : 1)",
        ))
    return issues, {
        "missing_required_columns": missing_columns,
        "available_indicators": available,
        "missing_configured_indicators": sorted(set(expected) - set(available)),
        "minimum_indicators": 1,
    }


def _fas_percentage_diagnostics(df: pd.DataFrame, cfg: dict) -> list[dict]:
    """Non-scoring review flags across all raw years; never change source values."""
    threshold = float(cfg.get("fas_pct_gdp_threshold", 1000.0))
    if not math.isfinite(threshold) or threshold <= 0:
        raise ValueError("quality.fas_pct_gdp_threshold must be finite and positive")
    if "SERIES_CODE" not in df.columns:
        return []
    codes = df["SERIES_CODE"].astype("string").str.strip().str.upper()
    parts = codes.str.extract(r"^([A-Z]{3})\.(.+)\.A$")
    suffixes = parts[1]
    selected = suffixes.isin(FAS_GDP_PERCENT_SERIES)
    diagnostics = []
    for index in df.index[selected]:
        row = df.loc[index]
        iso3 = normalize_iso3(parts.loc[index, 0])
        country = row.get("COUNTRY")
        for year in (c for c in df.columns if YEAR_RE.fullmatch(str(c))):
            numeric = pd.to_numeric(row[year], errors="coerce")
            if pd.isna(numeric) or not math.isfinite(numeric) or numeric <= threshold:
                continue
            diagnostics.append({
                "source": "fas",
                "code": "fas_pct_gdp_plausibility",
                "iso3": iso3,
                "country": country if pd.notna(country) else iso3,
                "year": int(year),
                "series_code": row["SERIES_CODE"],
                "indicator_code": FAS_GDP_PERCENT_SERIES[suffixes.loc[index]],
                "original_value": row[year],
                "value": float(numeric),
                "unit": "percent_of_gdp",
                "threshold": threshold,
                "reason": f"Value exceeds diagnostic threshold of {threshold:g}% GDP; "
                "review source value, scale and GDP denominator before KPI use.",
            })
    return diagnostics


def check_frame(
    name: str, df: pd.DataFrame, cfg: dict | None = None, source_cfg: dict | None = None,
) -> dict[str, Any]:
    """Controles qualite d'une source -> rapport + score [0, 1]."""
    cfg = cfg or {}
    issues: list[dict] = []
    n, p = df.shape
    min_rows = int(cfg.get("min_rows", 100))
    max_dup = float(cfg.get("max_duplicate_pct", 0.5))
    max_missing = float(cfg.get("max_missing_cells_pct", 45))
    max_missing_col = float(cfg.get("max_missing_column_pct", 99.5))

    if n == 0 or p == 0:
        issues.append(_issue("empty_source", "critical", f"[{name}] source vide"))
        return {
            "source": name,
            "rows": n,
            "cols": p,
            "score": 0.0,
            "issues": issues,
            "issue_counts": {"critical": 1},
            "gate": False,
            "metrics": {},
            "diagnostics": [],
        }

    schema_issues, schema_metrics = _check_schema(name, df, source_cfg or {})
    issues += schema_issues

    if n < min_rows:
        issues.append(
            _issue("too_few_rows", "high", f"[{name}] seulement {n} lignes", count=n)
        )

    duplicates = int(df.duplicated().sum())
    dup_pct = duplicates / n * 100
    if dup_pct > max_dup:
        severity = "high" if dup_pct > 5 else "medium"
        issues.append(
            _issue(
                "duplicate_rows",
                severity,
                f"[{name}] {duplicates} lignes dupliquees ({dup_pct:.2f} %)",
                count=duplicates,
                pct=dup_pct,
            )
        )

    key_columns = [c for c in KEY_COLUMNS.get(name, []) if c in df.columns]
    if key_columns:
        key_dups = int(df.duplicated(subset=key_columns).sum())
        if key_dups:
            issues.append(
                _issue(
                    "duplicate_key",
                    "critical",
                    f"[{name}] cle {key_columns} non unique ({key_dups} doublons)",
                    count=key_dups,
                )
            )

    missing_pct = df.isna().mean() * 100
    missing_cells = float(df.isna().sum().sum()) / (n * p) * 100
    if missing_cells > max_missing:
        issues.append(
            _issue(
                "high_missing_cells",
                "high",
                f"[{name}] {missing_cells:.1f} % de cellules vides",
                pct=missing_cells,
            )
        )
    fully_empty = missing_pct[missing_pct == 100].index.tolist()
    if fully_empty:
        issues.append(
            _issue(
                "empty_columns",
                "medium",
                f"[{name}] {len(fully_empty)} colonnes 100 % vides",
                count=len(fully_empty),
            )
        )
    near_empty = missing_pct[(missing_pct > max_missing_col) & (missing_pct < 100)]
    if len(near_empty) > 3:
        issues.append(
            _issue(
                "near_empty_columns",
                "low",
                f"[{name}] {len(near_empty)} colonnes remplies a moins de "
                f"{100 - max_missing_col:.1f} %",
                count=int(len(near_empty)),
            )
        )

    issues += _check_ranges(name, df, cfg)
    country_issues, country_meta = _country_check(name, df)
    issues += country_issues

    penalty = sum(SEVERITY_WEIGHT.get(i["severity"], 0.0) for i in issues)
    score = max(0.0, min(1.0, 1.0 - penalty))
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue["severity"]] = counts.get(issue["severity"], 0) + 1

    return {
        "source": name,
        "rows": int(n),
        "cols": int(p),
        "score": round(score, 4),
        "issues": issues,
        "diagnostics": _fas_percentage_diagnostics(df, cfg) if name == "fas" else [],
        "issue_counts": counts,
        "gate": score >= float(cfg.get("score_threshold", 0.7))
        and counts.get("critical", 0) == 0,
        "metrics": {
            "duplicates": duplicates,
            "duplicate_pct": round(dup_pct, 3),
            "missing_cells_pct": round(missing_cells, 2),
            "key_columns": key_columns,
            "fully_empty_columns": fully_empty,
            "schema": schema_metrics,
            **country_meta,
        },
    }


def build_report(
    frames: dict[str, pd.DataFrame], cfg: dict, sources: dict | None = None,
) -> dict[str, Any]:
    checks = {name: check_frame(name, df, cfg, (sources or {}).get(name)) for name, df in frames.items()}
    for name in MANDATORY_SOURCES:
        if name not in checks:
            checks[name] = check_frame(name, pd.DataFrame(), cfg)
    total_rows = sum(c["rows"] for c in checks.values())
    overall = (
        sum(c["score"] * c["rows"] for c in checks.values()) / total_rows
        if total_rows
        else 0.0
    )
    critical = sum(c["issue_counts"].get("critical", 0) for c in checks.values())
    issue_rows = [
        {"source": name, **issue} for name, check in checks.items() for issue in check["issues"]
    ]
    return {
        "overall_score": round(overall, 4),
        "passed": overall >= float(cfg.get("score_threshold", 0.7))
        and critical == 0
        and all(checks[name]["gate"] for name in MANDATORY_SOURCES),
        "critical_issues": critical,
        "checks": checks,
        "issue_counts": {
            severity: sum(c["issue_counts"].get(severity, 0) for c in checks.values())
            for severity in SEVERITY_WEIGHT
        },
        "issues": issue_rows,
        "diagnostics": [d for check in checks.values() for d in check.get("diagnostics", [])],
    }


def _markdown(report: dict) -> str:
    lines = [
        "# Data Quality Report",
        "",
        f"Score global : **{report['overall_score']:.2%}**",
        f"Quality gate : **{'PASS' if report['passed'] else 'FAIL'}**",
        f"Issues critiques : {report['critical_issues']}",
        "",
        "| Source | Lignes | Colonnes | Score | Gate | Issues |",
        "|---|---|---|---|---|---|",
    ]
    for name, check in report["checks"].items():
        lines.append(
            f"| {name} | {check['rows']:,} | {check['cols']} | {check['score']:.2%} | "
            f"{'PASS' if check['gate'] else 'FAIL'} | {len(check['issues'])} |"
        )
    lines += ["", "## Issues", ""]
    if not report["issues"]:
        lines.append("Aucune anomalie bloquante detectee.")
    for issue in report["issues"]:
        lines.append(
            f"- **{issue['source']}** `{issue['code']}` ({issue['severity']}) : "
            f"{issue['message']}"
        )
    if report.get("diagnostics"):
        lines += ["", "## Plausibility diagnostics (review only)", "",
                  "These flags do not affect quality scores or the gate. Values are unchanged.", "",
                  "| Country | ISO3 | Year | Series | Original value | Reason |",
                  "|---|---|---|---|---|---|"]
        for diagnostic in report["diagnostics"]:
            fields = [diagnostic[k] for k in ("country", "iso3", "year", "series_code", "original_value", "reason")]
            lines.append("| " + " | ".join(str(v).replace("|", "/") for v in fields) + " |")
    if report.get("llm_plan"):
        lines += ["", "## Plan de remediation (LLM)", ""]
        lines += [f"{index}. {step}" for index, step in enumerate(report["llm_plan"], 1)]
    return "\n".join(lines) + "\n"


class QualityAgent(BaseAgent):
    name = "quality"

    def _plan(self, report: dict) -> list[str]:
        summary = [
            {
                "source": issue["source"],
                "code": issue["code"],
                "severity": issue["severity"],
                "message": issue["message"],
            }
            for issue in report["issues"][:30]
        ]
        result = self.ask_json(
            "Voici les anomalies detectees par le controle qualite. Propose un plan "
            'de remediation prioritaire en francais. Reponds en JSON : {"plan": ["etape 1", ...]}. '
            f"Score global : {report['overall_score']}. Anomalies : "
            f"{json.dumps(summary, ensure_ascii=False)}",
            system="Tu es data steward. Tu priorises des corrections de qualite de donnees.",
            fallback={},
        )
        if isinstance(result, dict) and isinstance(result.get("plan"), list):
            return [str(step) for step in result["plan"]][:8]
        fallback = [
            "Corriger en priorite les anomalies critiques (cles dupliquees, source vide).",
            "Documenter les colonnes structurellement vides au lieu de les supprimer.",
            "Verifier les codes pays inconnus et les valeurs hors plage avant l'ETL.",
        ]
        return fallback if report["issues"] else ["Aucune action bloquante : passer a l'ETL."]

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        sources = ctx.get("sources") or self.cfg.get("sources") or {}
        raw_paths = ctx.get("raw_paths") or {}
        if not sources:
            raise AgentError("aucune source a controler")

        frames: dict[str, pd.DataFrame] = {}
        for name, source_cfg in sources.items():
            source_cfg = dict(source_cfg)
            if name in raw_paths:
                source_cfg["path"] = raw_paths[name]
            frames[name] = load_source(source_cfg)

        report = build_report(frames, self.cfg.get("quality") or {}, sources)
        report["llm_plan"] = self._plan(report)

        quality_dir = resolve(self.cfg["paths"].get("quality", "data/quality"))
        quality_dir.mkdir(parents=True, exist_ok=True)
        report_path = quality_dir / "quality_report.json"
        save_json(report, report_path)
        write_csv(pd.DataFrame(report["issues"]), quality_dir / "quality_issues.csv")
        diagnostics_path = quality_dir / "quality_diagnostics.csv"
        write_csv(pd.DataFrame(report["diagnostics"], columns=DIAGNOSTIC_COLUMNS), diagnostics_path)
        md_path = quality_dir / "quality_report.md"
        md_path.write_text(_markdown(report), encoding="utf-8")

        for name, check in report["checks"].items():
            self.log.info(
                "[%s] score=%.2f gate=%s issues=%d",
                name,
                check["score"],
                check["gate"],
                len(check["issues"]),
            )
        if not report["passed"]:
            self.log.warning(
                "quality gate FAIL (score=%.2f, critiques=%d)",
                report["overall_score"],
                report["critical_issues"],
            )

        notes = dict(ctx.get("llm_notes") or {})
        notes["quality"] = f"score global {report['overall_score']:.2%}, gate " + (
            "PASS" if report["passed"] else "FAIL"
        )
        return {
            "quality": report,
            "quality_paths": {
                "json": str(report_path),
                "csv": str(quality_dir / "quality_issues.csv"),
                "markdown": str(md_path),
                "diagnostics_csv": str(diagnostics_path),
            },
            "llm_notes": notes,
        }
