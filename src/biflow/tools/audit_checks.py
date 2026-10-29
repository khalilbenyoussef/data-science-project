"""Controles independants de l'Auditor sur kpi_values (lecture seule).

Volontairement independant du calcul KPI : aucun import de biflow.tools.kpi,
kpi_values, semantic_kpi ni kpi_provenance. Le catalogue YAML est relu ici,
ses formules sont interpretees par une liste blanche (jamais eval) et la table
`fact` est interrogee en SQL parametre. Chaque controle produit
{check_id, category, result: pass|warn|fail, detail, affected_rows}.
"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
import yaml

from biflow.utils.countries import normalize_iso3
from biflow.utils.io import read_csv_smart

PEERS_ISO3 = "PEERS"
YEAR_COLUMN = re.compile(r"^(19|20)\d{2}$")
GAP_FORMULA = re.compile(r"^100 \* \(value\[(?P<first>[^\]]+)\] - value\[(?P<second>[^\]]+)\]\)$")
# Formules du catalogue acceptees (toute autre formule est un echec du controle)
SIMPLE_FORMULAS = {
    "value": lambda v: v,
    "100 * value": lambda v: 100 * v,
    "100 * (1 - value)": lambda v: 100 * (1 - v),
}
# Transformation declaree entre fichier brut et fact.value, par source.
# Findex : fraction stockee telle quelle (le x100 n'existe que dans la formule KPI).
RAW_TO_FACT = {"findex": "identity", "fas": "identity", "gdp": "identity"}


# --------------------------------------------------------------------------- outils
def make_check(check_id: str, category: str, result: str, detail: str,
               affected_rows: Iterable[Mapping[str, Any]] = ()) -> dict[str, Any]:
    if result not in ("pass", "warn", "fail"):
        raise ValueError(f"resultat de controle invalide : {result}")
    return {"check_id": check_id, "category": category, "result": result,
            "detail": detail, "affected_rows": [dict(row) for row in affected_rows]}


def row_key(row: Mapping[str, Any]) -> tuple[str, str, int]:
    return row["kpi_id"], row["iso3"], int(row["year"])


def _ref(row: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    return {"kpi_id": row["kpi_id"], "iso3": row["iso3"], "year": int(row["year"]), **extra}


def load_catalog_file(path: str | Path) -> tuple[dict[str, Any], str]:
    """Catalogue relu depuis le fichier (aucun cache partage) + SHA-256 des octets."""
    content = Path(path).read_bytes()
    return yaml.safe_load(content), hashlib.sha256(content).hexdigest()


def read_kpi_rows(con) -> list[dict[str, Any]]:
    cursor = con.execute("SELECT * FROM kpi_values")
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, values)) for values in cursor.fetchall()]


# --------------------------------------------------------------------------- formules
def parse_formula(kpi: Mapping[str, Any]) -> tuple[str, Any]:
    """('simple', fonction) ou ('gap', (premier, second)) ; ValueError sinon."""
    text = str(kpi["formula"]["from_fact"]).strip()
    if text in SIMPLE_FORMULAS:
        return "simple", SIMPLE_FORMULAS[text]
    match = GAP_FORMULA.fullmatch(text)
    if match:
        return "gap", (match["first"], match["second"])
    raise ValueError(f"formule non reconnue : {text!r}")


def kpi_inputs(kpi: Mapping[str, Any]) -> list[dict[str, str]]:
    """Faits d'entree d'un KPI d'apres le catalogue (deux pour un ecart)."""
    w = kpi["warehouse"]
    kind, args = parse_formula(kpi)
    values = list(args) if kind == "gap" else [w["dimension_value"]]
    if kind == "gap" and values != [w["dimension_value"], w.get("subtrahend_dimension_value")]:
        raise ValueError("formule d'ecart incoherente avec warehouse")
    return [{"source": w["source"], "indicator_code": w["indicator_code"],
             "dimension": w["dimension"], "dimension_value": value} for value in values]


def observe(con, iso3: str, year: int, key: Mapping[str, str], input_unit: str) -> dict[str, Any]:
    """Un fait d'entree : valeur brute de fact + statut (ok ou raison d'indisponibilite)."""
    rows = con.execute(
        "SELECT value, unit FROM fact WHERE iso3 = ? AND year = ? AND source = ? "
        "AND indicator_code = ? AND dimension = ? AND dimension_value = ?",
        [iso3, year, key["source"], key["indicator_code"], key["dimension"], key["dimension_value"]],
    ).fetchall()
    fact_key = [iso3, year, key["source"], key["indicator_code"], key["dimension"], key["dimension_value"]]
    out = {"fact_key": fact_key, "value": None, "unit": None, "status": "ok"}
    if not rows:
        return {**out, "status": "missing_observation"}
    if len(rows) > 1:
        return {**out, "status": "duplicate_observations"}
    value, unit = rows[0]
    out.update(unit=unit)
    if unit != input_unit:
        return {**out, "status": "unexpected_input_unit"}
    if value is None or not math.isfinite(value):
        return {**out, "status": "missing_or_nonfinite_input"}
    if value < 0 or (unit == "fraction" and value > 1):
        return {**out, "value": float(value), "status": "out_of_range_input"}
    return {**out, "value": float(value)}


def expected_value(con, kpi: Mapping[str, Any], iso3: str, year: int) -> dict[str, Any]:
    """Recalcul independant d'une ligne pays : {value, reason, inputs}."""
    if year not in kpi["valid_years"]:
        return {"value": None, "reason": "out_of_catalog_year", "inputs": []}
    kind, args = parse_formula(kpi)
    inputs = [observe(con, iso3, year, key, kpi["warehouse"]["input_unit"]) for key in kpi_inputs(kpi)]
    failed = next((item for item in inputs if item["status"] != "ok"), None)
    if failed is not None:
        return {"value": None, "reason": failed["status"], "inputs": inputs}
    if kind == "gap":
        value = 100 * (inputs[0]["value"] - inputs[1]["value"])
    else:
        value = args(inputs[0]["value"])
    return {"value": value, "reason": None, "inputs": inputs}


# --------------------------------------------------------------------------- A : recalcul
def recompute_checks(con, catalog: Mapping[str, Any], rows: list[dict[str, Any]], focus: str,
                     peers: list[str], tolerance: float = 1e-9) -> tuple[list[dict], dict]:
    """A1-A4 : valeurs recalculees, NULL reels, lignes PEERS, completude."""
    kpis = catalog["kpis"]
    recomputed: dict[tuple, dict[str, Any]] = {}
    mismatched, null_issues, peer_issues, formula_issues = [], [], [], []

    for row in rows:
        if row["iso3"] == PEERS_ISO3 or row["kpi_id"] not in kpis:
            continue
        try:
            exp = expected_value(con, kpis[row["kpi_id"]], row["iso3"], int(row["year"]))
        except (ValueError, KeyError, TypeError) as exc:
            formula_issues.append(_ref(row, reason=str(exc)))
            continue
        recomputed[row_key(row)] = exp
        found = row["value"]
        if found is not None and isinstance(found, float) and math.isnan(found):
            found = None
        published = row.get("availability_status") == "available"
        if found is None:
            if exp["value"] is not None:
                null_issues.append(_ref(row, expected=exp["value"], found=None,
                                        reason="valeur calculable mais publiee NULL"))
            elif published:
                null_issues.append(_ref(row, found=None, reason="statut available sans valeur"))
        elif exp["value"] is None:
            null_issues.append(_ref(row, expected=None, found=found,
                                    reason=f"valeur publiee sans observation valide ({exp['reason']})"))
        else:
            if abs(found - exp["value"]) > tolerance:
                mismatched.append(_ref(row, expected=exp["value"], found=found))
            if not published:
                null_issues.append(_ref(row, found=found, reason="valeur presente mais statut "
                                        f"{row.get('availability_status')}"))

    configured = [p for p in peers if p != focus]
    for row in rows:
        if row["iso3"] != PEERS_ISO3 or row["kpi_id"] not in kpis:
            continue
        values = {p: (recomputed.get((row["kpi_id"], p, int(row["year"]))) or {}).get("value")
                  for p in configured}
        included = [p for p in configured if values[p] is not None]
        missing = [p for p in configured if values[p] is None]
        expected = sum(values[p] for p in included) / len(included) if included else None
        problems = []
        if list(row.get("peers_included") or []) != included:
            problems.append(f"peers_included={row.get('peers_included')} attendu {included}")
        if list(row.get("missing_peers") or []) != missing:
            problems.append(f"missing_peers={row.get('missing_peers')} attendu {missing}")
        found = row["value"]
        if (found is None) != (expected is None):
            problems.append(f"valeur {found} attendu {expected}")
        elif expected is not None and abs(found - expected) > tolerance:
            problems.append(f"moyenne {found} attendu {expected}")
        if problems:
            peer_issues.append(_ref(row, expected=expected, found=found, reason="; ".join(problems)))

    expected_keys = {(kpi_id, iso3, year) for kpi_id, kpi in kpis.items()
                     for year in kpi["valid_years"]
                     for iso3 in [focus, *configured, PEERS_ISO3]}
    seen: dict[tuple, int] = {}
    for row in rows:
        seen[row_key(row)] = seen.get(row_key(row), 0) + 1
    completeness = (
        [{"kpi_id": k, "iso3": i, "year": y, "reason": "ligne manquante"} for k, i, y in sorted(expected_keys - set(seen))]
        + [{"kpi_id": k, "iso3": i, "year": y, "reason": "ligne inattendue"} for k, i, y in sorted(set(seen) - expected_keys)]
        + [{"kpi_id": k, "iso3": i, "year": y, "reason": f"{n} lignes"} for (k, i, y), n in sorted(seen.items()) if n > 1]
    )

    checks = [
        make_check("A1_recomputed_values", "recomputation", "fail" if mismatched or formula_issues else "pass",
                   f"{len(recomputed)} lignes pays recalculees depuis fact (tolerance {tolerance:g}) ; "
                   f"{len(mismatched)} ecart(s), {len(formula_issues)} formule(s) non reconnue(s)",
                   mismatched + formula_issues),
        make_check("A2_unavailable_rows_are_null", "recomputation", "fail" if null_issues else "pass",
                   "Lignes indisponibles : valeur NULL et observation reellement absente ou invalide "
                   f"dans fact ; {len(null_issues)} anomalie(s)", null_issues),
        make_check("A3_peers_recomputed", "recomputation", "fail" if peer_issues else "pass",
                   f"Lignes PEERS = moyenne simple des pairs disponibles ({', '.join(configured)}) ; "
                   f"{len(peer_issues)} anomalie(s)", peer_issues),
        make_check("A4_row_completeness", "recomputation", "fail" if completeness else "pass",
                   f"{len(expected_keys)} lignes attendues (KPI x pays x annees valides), "
                   f"{len(rows)} presentes ; {len(completeness)} anomalie(s)", completeness),
    ]
    return checks, recomputed


# --------------------------------------------------------------------------- A5 : brut -> fact
class RawSources:
    """Lecture des fichiers bruts du snapshot (parseur declare de l'ETL : pandas).

    Les valeurs numeriques sont lues comme le fait l'ETL (read_csv_smart) pour
    une egalite exacte ; le texte brut est conserve pour les explications.
    """

    def __init__(self, paths: Mapping[str, str | Path], sources: Mapping[str, Any]):
        self.paths = {name: Path(path) for name, path in paths.items()}
        self.sources = sources
        self._frames: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}

    def _frame(self, source: str) -> tuple[pd.DataFrame, pd.DataFrame]:
        if source not in self._frames:
            cfg = self.sources.get(source) or {}
            marker = cfg.get("header_marker")
            path = self.paths[source]
            usecols = None
            if source == "fas":
                usecols = lambda c: str(c).strip() == "SERIES_CODE" or bool(YEAR_COLUMN.match(str(c).strip()))  # noqa: E731
            numeric = read_csv_smart(path, header_marker=marker, usecols=usecols)
            text = read_csv_smart(path, header_marker=marker, usecols=usecols, dtype=str,
                                  keep_default_na=False)
            if source == "findex":
                key = numeric["codewb"].map(normalize_iso3) + "|" + numeric["year"].astype(str) \
                    + "|" + numeric["group"].astype(str) + "|" + numeric["group2"].astype(str)
            elif source == "fas":
                codes = numeric["SERIES_CODE"].astype(str).str.strip().str.upper()
                prefix = codes.str.split(".", n=1).str[0].map(normalize_iso3)
                key = prefix + "." + codes.str.split(".", n=1).str[1]
            else:
                key = numeric["iso3"].map(normalize_iso3) + "|" + numeric["indicator_code"].astype(str) \
                    + "|" + numeric["year"].astype(str)
            numeric.index = key.values
            text.index = key.values
            self._frames[source] = (numeric, text)
        return self._frames[source]

    def lookup(self, fact_key: list, fas_series: Mapping[str, str]) -> dict[str, Any]:
        """Enregistrement brut d'un fait : {source, key, column, raw_text, raw_value} ou erreur."""
        iso3, year, source, indicator, dimension, dimension_value = fact_key
        numeric, text = self._frame(source)
        if source == "findex":
            key, column = f"{iso3}|{year}|{dimension}|{dimension_value}", indicator
            record = {"codewb": iso3, "year": year, "group": dimension, "group2": dimension_value}
        elif source == "fas":
            series = fas_series.get(indicator)
            key, column = f"{iso3}.{series}.A", str(year)
            record = {"SERIES_CODE": key, "year_column": str(year)}
        else:
            key, column = f"{iso3}|{indicator}|{year}", "value"
            record = {"iso3": iso3, "indicator_code": indicator, "year": year}
        out = {"source": source, "key": record, "column": column, "raw_text": None, "raw_value": None,
               "file": str(self.paths[source])}
        if column not in numeric.columns:
            return {**out, "error": f"colonne {column} absente du fichier brut"}
        matches = numeric.index == key
        count = int(matches.sum())
        if count != 1:
            return {**out, "error": f"{count} enregistrement(s) brut(s) pour la cle"}
        raw_value = numeric.loc[matches, column].iloc[0]
        out["raw_text"] = str(text.loc[matches, column].iloc[0])
        out["raw_value"] = None if pd.isna(raw_value) else float(raw_value)
        return out


def raw_to_fact_check(recomputed: Mapping[tuple, Mapping[str, Any]], raw: RawSources,
                      fas_series: Mapping[str, str]) -> tuple[dict, dict]:
    """A5 : chaque fait d'entree egal au fichier brut selon la transformation declaree."""
    issues, lookups = [], {}
    for (kpi_id, iso3, year), exp in sorted(recomputed.items()):
        for item in exp["inputs"]:
            if item["value"] is None:
                continue
            fact_key = tuple(item["fact_key"])
            if fact_key not in lookups:
                lookups[fact_key] = raw.lookup(list(fact_key), fas_series)
            found = lookups[fact_key]
            transform = RAW_TO_FACT.get(fact_key[2])
            if found.get("error"):
                issues.append({"kpi_id": kpi_id, "iso3": iso3, "year": year,
                               "fact_key": list(fact_key), "reason": found["error"]})
            elif transform != "identity" or found["raw_value"] != item["value"]:
                issues.append({"kpi_id": kpi_id, "iso3": iso3, "year": year, "fact_key": list(fact_key),
                               "expected": found["raw_value"], "found": item["value"],
                               "reason": f"fact.value different du brut (transformation {transform})"})
    check = make_check(
        "A5_raw_to_fact", "recomputation", "fail" if issues else "pass",
        f"{len(lookups)} faits d'entree compares au fichier brut du snapshot "
        "(Findex : fraction identique ; FAS, WDI : valeur identique) ; "
        f"{len(issues)} ecart(s)", issues)
    return check, lookups


def verdict_of(checks: Iterable[Mapping[str, Any]]) -> str:
    results = {check["result"] for check in checks}
    return "fail" if "fail" in results else "pass_with_warnings" if "warn" in results else "pass"


def count_results(checks: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for check in checks:
        counts[check["result"]] += 1
    return counts


__all__ = [
    "PEERS_ISO3", "RAW_TO_FACT", "RawSources", "count_results", "expected_value", "kpi_inputs",
    "load_catalog_file", "make_check", "observe", "parse_formula", "raw_to_fact_check",
    "read_kpi_rows", "recompute_checks", "row_key", "verdict_of",
]
