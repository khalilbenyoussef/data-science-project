"""Forme canonique d'une source utilisateur (une ligne par observation).

Utilisee par le dry-run, l'ETL (user_long) et l'Auditor (controle brut -> fact) :
une seule implementation du mapping. Chaque observation garde le texte brut,
la colonne et le numero de ligne d'origine. Valeurs inchangees, sauf
conversion percent/fraction declaree explicitement dans le mapping.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

import pandas as pd

from biflow.tools.user_sources.countries import CountryResolver
from biflow.tools.user_sources.detect import parse_number
from biflow.tools.user_sources.mapping import SourceMapping

CANONICAL_COLUMNS = ["iso3", "year", "indicator_code", "indicator_label", "dimension", "dimension_value",
                     "value", "unit", "raw_value", "raw_column", "line", "country_raw"]
CONVERSIONS = {"none": lambda v: v, "percent_to_fraction": lambda v: v / 100,
               "fraction_to_percent": lambda v: v * 100}


def source_label(name: str) -> str:
    return f"user:{name}"


def indicator_code(name: str, code: str) -> str:
    """Code dans fact : prefixe par la source, jamais en collision avec un code officiel."""
    return f"{name}.{code}"


def _cells(mapping: SourceMapping, df: pd.DataFrame):
    """(ligne, texte pays, texte annee, code indicateur, colonne valeur, texte valeur, dimension)."""
    c = mapping.columns
    single = next(iter(mapping.indicators)) if len(mapping.indicators) == 1 else None
    for _, row in df.iterrows():
        dimension = (c.dimension.name, str(row[c.dimension.column]).strip()) if c.dimension else ("all", "all")
        base = (int(row["_line"]), str(row[c.country.column]))
        if mapping.layout == "long":
            label = str(row[c.indicator]).strip() if c.indicator else None
            code = mapping.indicator_values.get(label) if label is not None else single
            yield (*base, str(row[c.year]), code, c.value, str(row[c.value]), dimension)
        elif mapping.layout == "wide_by_year":
            label = str(row[c.indicator]).strip() if c.indicator else None
            code = mapping.indicator_values.get(label) if label is not None else single
            for column in c.year_columns:
                yield (*base, column, code, column, str(row[column]), dimension)
        else:
            for column, code in c.indicator_columns.items():
                yield (*base, str(row[c.year]), code, column, str(row[column]), dimension)


def canonical(mapping: SourceMapping, df: pd.DataFrame, resolver: CountryResolver | None = None,
              ) -> tuple[pd.DataFrame, dict[str, Any]]:
    """(observations canoniques retenues, rapport de dry-run)."""
    resolver = resolver or CountryResolver(mapping.country_names)
    kind = mapping.columns.country.kind
    rows, missing, non_numeric, bad_years, unknown_indicator = [], 0, [], [], 0
    unmapped: Counter = Counter()
    reasons: dict[str, str] = {}
    cache: dict[str, tuple[str | None, str | None]] = {}
    total = 0
    for line, country_raw, year_text, code, column, raw, (dim, dim_value) in _cells(mapping, df):
        total += 1
        if raw.strip() == "":
            missing += 1
            continue
        if country_raw not in cache:
            cache[country_raw] = resolver.resolve(country_raw, kind)
        iso3, why = cache[country_raw]
        if iso3 is None:
            unmapped[country_raw.strip()] += 1
            reasons[country_raw.strip()] = why
            continue
        if not re.fullmatch(r"(19|20)\d{2}", year_text.strip()):
            bad_years.append({"line": line, "column": column, "year": year_text})
            continue
        if code is None:
            unknown_indicator += 1
            continue
        try:
            number = parse_number(raw, mapping.read.decimal)
        except ValueError:
            non_numeric.append({"line": line, "column": column, "text": raw})
            continue
        spec = mapping.indicators[code]
        rows.append({
            "iso3": iso3, "year": int(year_text.strip()), "indicator_code": indicator_code(mapping.name, code),
            "indicator_label": spec.label, "dimension": dim, "dimension_value": dim_value,
            "value": CONVERSIONS[spec.transform](number), "unit": spec.stored_unit, "raw_value": raw,
            "raw_column": column, "line": line, "country_raw": country_raw,
        })
    frame = pd.DataFrame(rows, columns=CANONICAL_COLUMNS)
    key = ["iso3", "year", "indicator_code", "dimension", "dimension_value"]
    exact = frame.duplicated(subset=key + ["value"], keep="first")
    conflicts = frame[~exact & frame.duplicated(subset=key, keep=False)]
    frame = frame[~exact].reset_index(drop=True)
    filled = total - missing
    report = {
        "observations": total, "empty_cells": missing, "mapped": int(len(frame)),
        "mapped_pct": round(100 * len(frame) / filled, 1) if filled else 0.0,
        "unmapped_countries": {name: {"rows": n, "reason": reasons[name]} for name, n in sorted(unmapped.items())},
        "non_numeric": {"count": len(non_numeric), "examples": non_numeric[:20]},
        "invalid_years": {"count": len(bad_years), "examples": bad_years[:20]},
        "unknown_indicator_cells": unknown_indicator,
        "duplicates": {"exact_removed": int(exact.sum()),
                       "conflicting_keys": int(conflicts.groupby(key).ngroups) if len(conflicts) else 0,
                       "examples": conflicts.head(10)[key + ["value", "line"]].to_dict(orient="records")},
        "year_range": [int(frame["year"].min()), int(frame["year"].max())] if len(frame) else None,
        "countries": sorted(frame["iso3"].unique().tolist()),
        "indicators": {code: {"label": spec.label, "unit": spec.stored_unit, "transform": spec.transform}
                       for code, spec in mapping.indicators.items()},
        "preview": frame.head(10).drop(columns=["country_raw"]).to_dict(orient="records"),
    }
    return frame, report


def format_report(report: dict[str, Any]) -> str:
    """Rapport de dry-run lisible (francais)."""
    lines = [
        f"Observations : {report['observations']} cellules, {report['empty_cells']} vides, "
        f"{report['mapped']} retenues ({report['mapped_pct']} % des cellules remplies)",
        f"Annees : {report['year_range'][0]}-{report['year_range'][1]}" if report["year_range"] else "Annees : aucune",
        f"Pays reconnus : {', '.join(report['countries']) or 'aucun'}",
    ]
    if report["unmapped_countries"]:
        lines.append("Pays non reconnus (lignes exclues) : " + ", ".join(
            f"{name!r} x{info['rows']} ({info['reason']})" for name, info in report["unmapped_countries"].items()))
    lines.append(f"Valeurs non numeriques : {report['non_numeric']['count']}" + (
        " (ex. " + ", ".join(f"ligne {e['line']} {e['column']}={e['text']!r}"
                             for e in report["non_numeric"]["examples"][:5]) + ")"
        if report["non_numeric"]["count"] else ""))
    if report["invalid_years"]["count"]:
        lines.append(f"Annees invalides : {report['invalid_years']['count']}")
    dup = report["duplicates"]
    lines.append(f"Doublons : {dup['exact_removed']} exact(s) retire(s), {dup['conflicting_keys']} cle(s) "
                 "en conflit" + (" -> a corriger avant confirmation" if dup["conflicting_keys"] else ""))
    lines.append("Indicateurs : " + ", ".join(f"{code} ({info['unit']}"
                                              + (f", {info['transform']}" if info["transform"] != "none" else "")
                                              + ")" for code, info in report["indicators"].items()))
    lines += ["", "Apercu (10 premieres observations canoniques) :",
              "| iso3 | annee | indicateur | valeur | unite | brut | ligne |", "|---|---|---|---|---|---|---|"]
    lines += [f"| {r['iso3']} | {r['year']} | {r['indicator_code']} | {r['value']:g} | {r['unit']} | "
              f"{r['raw_value']} | {r['line']} |" for r in report["preview"]]
    return "\n".join(lines)


__all__ = ["CANONICAL_COLUMNS", "canonical", "format_report", "indicator_code", "source_label"]
