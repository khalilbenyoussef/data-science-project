"""Controles independants de l'Auditor sur kpi_values (lecture seule).

Volontairement independant du calcul KPI : aucun import de biflow.tools.kpi,
kpi_values, semantic_kpi ni kpi_provenance. Le catalogue YAML est relu ici,
ses formules sont interpretees par une liste blanche (jamais eval) et la table
`fact` est interrogee en SQL parametre. Chaque controle produit
{check_id, category, result: pass|warn|fail, detail, affected_rows}.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd
import yaml

from biflow.tools.dictionary import FINDEX_UNVERIFIED
from biflow.utils.countries import is_aggregate, is_country, normalize_iso3
from biflow.utils.io import cached_sha256_file, read_csv_smart

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
# Sources utilisateur : transformation declaree dans le mapping (aucune ou percent/fraction explicite)
USER_STATUS = "user_declared"
USER_CONVERSIONS = {"none": lambda v: v, "percent_to_fraction": lambda v: v / 100,
                    "fraction_to_percent": lambda v: v * 100}


# Bornes de plausibilite par unite KPI
UNIT_BOUNDS = {"percent": (0.0, 100.0), "percentage_points": (-100.0, 100.0),
               "per_100k_adults": (0.0, math.inf), "per_1k_adults": (0.0, math.inf),
               # % du PIB : peut depasser 100 ; les valeurs implausibles relevent du
               # diagnostic qualite fas_pct_gdp_plausibility (lignes signalees seulement)
               "percent_of_gdp": (0.0, math.inf), "fraction": (0.0, 1.0)}


# --------------------------------------------------------------------------- outils
def make_check(check_id: str, category: str, result: str, detail: str,
               affected_rows: Iterable[Mapping[str, Any]] = (),
               affects_publication: bool = True) -> dict[str, Any]:
    """affects_publication=False : information (ex. variation entre vagues),
    sans effet sur le statut de publication des lignes citees."""
    if result not in ("pass", "warn", "fail"):
        raise ValueError(f"résultat de contrôle invalide : {result}")
    return {"check_id": check_id, "category": category, "result": result,
            "detail": detail, "affected_rows": [dict(row) for row in affected_rows],
            "affects_publication": affects_publication}


def row_key(row: Mapping[str, Any]) -> tuple[str, str, int]:
    return row["kpi_id"], row["iso3"], int(row["year"])


def _ref(row: Mapping[str, Any], **extra: Any) -> dict[str, Any]:
    return {"kpi_id": row["kpi_id"], "iso3": row["iso3"], "year": int(row["year"]), **extra}


def load_catalog_file(path: str | Path) -> tuple[dict[str, Any], str]:
    """Catalogue relu depuis le fichier (aucun cache partage) + SHA-256 des octets."""
    content = Path(path).read_bytes()
    return yaml.safe_load(content), hashlib.sha256(content).hexdigest()


def load_catalogs(path: str | Path, user_path: str | Path | None) -> tuple[dict[str, Any], str, str | None]:
    """Catalogue officiel + catalogue utilisateur (fusion relue independamment).
    Renvoie (catalogue fusionne, hash officiel, hash utilisateur ou None)."""
    catalog, digest = load_catalog_file(path)
    if not user_path or not Path(user_path).is_file():
        return catalog, digest, None
    user, user_digest = load_catalog_file(user_path)
    user = user or {}
    merged = dict(catalog)
    merged["kpis"] = {**catalog["kpis"], **{k: v for k, v in (user.get("kpis") or {}).items()
                                            if k not in catalog["kpis"]}}
    merged["references"] = {**(user.get("references") or {}), **catalog["references"]}
    merged["_user_kpis"] = sorted(user.get("kpis") or {})
    merged["_user_collisions"] = sorted(set(user.get("kpis") or {}) & set(catalog["kpis"]))
    return merged, digest, user_digest


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
        raise ValueError("formule d'écart incohérente avec warehouse")
    return [{"source": w["source"], "indicator_code": w["indicator_code"],
             "dimension": w["dimension"], "dimension_value": value} for value in values]


def observe(con, iso3: str, year: int, key: Mapping[str, str], input_unit: str,
            allow_negative: bool = False) -> dict[str, Any]:
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
    if (value < 0 and not allow_negative) or (unit == "fraction" and not 0 <= value <= 1):
        return {**out, "value": float(value), "status": "out_of_range_input"}
    return {**out, "value": float(value)}


def expected_value(con, kpi: Mapping[str, Any], iso3: str, year: int) -> dict[str, Any]:
    """Recalcul independant d'une ligne pays : {value, reason, inputs}."""
    if year not in kpi["valid_years"]:
        return {"value": None, "reason": "out_of_catalog_year", "inputs": []}
    kind, args = parse_formula(kpi)
    user = (kpi.get("verification") or {}).get("status") == USER_STATUS  # valeurs negatives admises
    inputs = [observe(con, iso3, year, key, kpi["warehouse"]["input_unit"], allow_negative=user)
              for key in kpi_inputs(kpi)]
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
                                        reason="valeur calculable mais publiée NULL"))
            elif published:
                null_issues.append(_ref(row, found=None, reason="statut available sans valeur"))
        elif exp["value"] is None:
            null_issues.append(_ref(row, expected=None, found=found,
                                    reason=f"valeur publiée sans observation valide ({exp['reason']})"))
        else:
            if abs(found - exp["value"]) > tolerance:
                mismatched.append(_ref(row, expected=exp["value"], found=found))
            if not published:
                null_issues.append(_ref(row, found=found, reason="valeur présente mais statut "
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
                   f"{len(recomputed)} lignes pays recalculées depuis fact (tolérance {tolerance:g}) ; "
                   f"{len(mismatched)} écart(s), {len(formula_issues)} formule(s) non reconnue(s)",
                   mismatched + formula_issues),
        make_check("A2_unavailable_rows_are_null", "recomputation", "fail" if null_issues else "pass",
                   "Lignes indisponibles : valeur NULL et observation reellement absente ou invalide "
                   f"dans fact ; {len(null_issues)} anomalie(s)", null_issues),
        make_check("A3_peers_recomputed", "recomputation", "fail" if peer_issues else "pass",
                   f"Lignes PEERS = moyenne simple des pairs disponibles ({', '.join(configured)}) ; "
                   f"{len(peer_issues)} anomalie(s)", peer_issues),
        make_check("A4_row_completeness", "recomputation", "fail" if completeness else "pass",
                   f"{len(expected_keys)} lignes attendues (KPI x pays x années valides), "
                   f"{len(rows)} présentes ; {len(completeness)} anomalie(s)", completeness),
    ]
    return checks, recomputed


# --------------------------------------------------------------------------- A5 : brut -> fact
class RawSources:
    """Lecture des fichiers bruts du snapshot (parseur declare de l'ETL : pandas).

    Les valeurs numeriques sont lues comme le fait l'ETL (read_csv_smart) pour
    une egalite exacte ; le texte brut est conserve pour les explications.
    """

    def __init__(self, paths: Mapping[str, str | Path], sources: Mapping[str, Any],
                 aliases: Mapping[str, str] | None = None):
        self.paths = {name: Path(path) for name, path in paths.items()}
        self.sources = sources
        self.aliases = dict(aliases or {})
        self._frames: dict[str, tuple[pd.DataFrame, pd.DataFrame]] = {}
        self._user: dict[str, dict[str, Any]] = {}

    def user_source(self, name: str) -> dict[str, Any]:
        """Observations du mapping + cellules du blob relues independamment (ligne -> champs)."""
        if name not in self._user:
            from biflow.tools.user_sources.loader import load_user_canonical, user_mapping

            source_cfg = self.sources.get(name) or {}
            mapping = user_mapping(source_cfg)
            frame, _, _ = load_user_canonical(source_cfg, self.paths[name], self.aliases)
            read = mapping.read
            text = self.paths[name].read_bytes().decode(read.encoding)
            reader = csv.reader(io.StringIO(text), delimiter=read.separator)
            cells, header, index = {}, None, -1
            while True:
                line = reader.line_num + 1
                try:
                    record = next(reader)
                except StopIteration:
                    break
                if not any(field.strip() for field in record):
                    continue
                index += 1
                if index < read.header_row:
                    continue
                if header is None:
                    header = [h.strip().lstrip("\ufeff") for h in record]
                    continue
                cells[line] = dict(zip(header, record))
            index_by_key = {(r.iso3, int(r.year), r.indicator_code, r.dimension, r.dimension_value): r
                            for r in frame.itertuples(index=False)}
            self._user[name] = {"mapping": mapping, "frame": frame, "cells": cells, "index": index_by_key}
        return self._user[name]

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
        if str(source).startswith("user:"):
            return self._lookup_user(fact_key)
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
            return {**out, "error": f"{count} enregistrement(s) brut(s) pour la clé"}
        raw_value = numeric.loc[matches, column].iloc[0]
        out["raw_text"] = str(text.loc[matches, column].iloc[0])
        for name in ("codewb", "SERIES_CODE"):  # code tel qu'ecrit dans le fichier (alias inclus)
            if name in text.columns:
                record[name] = str(text.loc[matches, name].iloc[0])
        out["raw_value"] = None if pd.isna(raw_value) else float(raw_value)
        return out


def _parse_declared(text: str, decimal: str) -> float:
    """Re-lecture independante d'un nombre (decimale declaree, milliers en espaces)."""
    value = re.sub(r"[ \u00a0\u202f]", "", text.strip())
    if decimal == ",":
        if "." in value:
            raise ValueError(text)
        value = value.replace(",", ".")
    elif "," in value:
        raise ValueError(text)
    return float(value)


def _lookup_user(self, fact_key: list) -> dict[str, Any]:
    iso3, year, source, indicator, dimension, dimension_value = fact_key
    name = str(source).split(":", 1)[1]
    out = {"source": source, "key": None, "column": None, "raw_text": None, "raw_value": None,
           "file": str(self.paths.get(name))}
    if name not in self.paths:
        return {**out, "error": "source utilisateur absente du snapshot"}
    data = self.user_source(name)
    row = data["index"].get((iso3, int(year), indicator, dimension, dimension_value))
    if row is None:
        return {**out, "error": "aucune observation du mapping pour ce fait"}
    cell = (data["cells"].get(int(row.line)) or {}).get(row.raw_column)
    out.update(key={"line": int(row.line), "column": row.raw_column, "country": row.country_raw},
               column=row.raw_column, raw_text=cell)
    if cell is None or cell != row.raw_value:
        return {**out, "error": f"cellule ligne {row.line} colonne {row.raw_column!r} différente du mapping"}
    code = indicator.split(".", 1)[1]
    spec = data["mapping"].indicators[code]
    try:
        out["raw_value"] = USER_CONVERSIONS[spec.transform](_parse_declared(cell, data["mapping"].read.decimal))
    except (ValueError, KeyError):
        return {**out, "error": f"valeur brute non numérique {cell!r}"}
    out["transform"] = spec.transform
    return out


RawSources._lookup_user = _lookup_user


def user_fact_check(con, raw: RawSources, lineage: Mapping[str, Any]) -> dict[str, Any]:
    """A6 : faits de chaque source utilisateur = observations du mapping sur la periode de l'ETL."""
    period = lineage.get("period") or {}
    low, high = period.get("min_year", 0), period.get("max_year", 9999)
    issues, checked = [], []
    for name, meta in sorted((lineage.get("inputs") or {}).items()):
        if not (isinstance(meta, dict) and meta.get("user")) or meta.get("excluded"):
            continue
        checked.append(name)
        try:
            frame = raw.user_source(name)["frame"]
        except Exception as exc:  # noqa: BLE001 - mapping ou blob illisible
            issues.append({"source": name, "reason": f"source illisible : {exc}"})
            continue
        frame = frame[frame["year"].between(low, high)]
        expected = {(r.iso3, int(r.year), r.indicator_code, r.dimension, r.dimension_value): r.value
                    for r in frame.itertuples(index=False)}
        found = {(i, int(y), c, d, v): val for i, y, c, d, v, val in con.execute(
            "SELECT iso3, year, indicator_code, dimension, dimension_value, value FROM fact WHERE source = ?",
            [f"user:{name}"]).fetchall()}
        for key in sorted(set(expected) | set(found), key=str):
            if expected.get(key) != found.get(key):
                issues.append({"source": name, "fact_key": list(key), "expected": expected.get(key),
                               "found": found.get(key)})
    return make_check("A6_user_source_facts", "recomputation", "fail" if issues else "pass",
                      f"Sources utilisateur {', '.join(checked) or 'aucune'} : faits identiques aux observations "
                      f"du mapping relues dans le snapshot ; {len(issues)} écart(s)", issues[:50])


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
            transform = "declared_mapping" if str(fact_key[2]).startswith("user:") else RAW_TO_FACT.get(fact_key[2])
            if found.get("error"):
                issues.append({"kpi_id": kpi_id, "iso3": iso3, "year": year,
                               "fact_key": list(fact_key), "reason": found["error"]})
            elif transform not in ("identity", "declared_mapping") or found["raw_value"] != item["value"]:
                issues.append({"kpi_id": kpi_id, "iso3": iso3, "year": year, "fact_key": list(fact_key),
                               "expected": found["raw_value"], "found": item["value"],
                               "reason": f"fact.value différent du brut (transformation {transform})"})
    check = make_check(
        "A5_raw_to_fact", "recomputation", "fail" if issues else "pass",
        f"{len(lookups)} faits d'entrée comparés au fichier brut du snapshot "
        "(Findex : fraction identique ; FAS, WDI : valeur identique) ; "
        f"{len(issues)} écart(s)", issues)
    return check, lookups


# --------------------------------------------------------------------------- B : coherence
def content_digest(con, tables: Iterable[str]) -> str:
    """Re-implementation independante de l'empreinte de contenu du lineage :
    [table, colonnes] puis une ligne JSON par enregistrement, ORDER BY ALL."""
    digest = hashlib.sha256()
    for table in tables:
        if not re.fullmatch(r"[a-z_]+", str(table)):
            raise ValueError(f"nom de table invalide : {table!r}")
        cursor = con.execute(f"SELECT * FROM {table} ORDER BY ALL")
        digest.update(json.dumps([table, [c[0] for c in cursor.description]]).encode("utf-8") + b"\n")
        while batch := cursor.fetchmany(10_000):
            for record in batch:
                digest.update(json.dumps(record, default=str, separators=(",", ":")).encode("utf-8") + b"\n")
    return digest.hexdigest()


def unit_checks(rows: list[dict[str, Any]], catalog: Mapping[str, Any]) -> list[dict]:
    """B1 : une unite par KPI (celle du catalogue) et bornes de plausibilite."""
    kpis = catalog["kpis"]
    unit_issues, range_issues = [], []
    for row in rows:
        kpi = kpis.get(row["kpi_id"])
        if kpi is None:
            continue
        if row["unit"] != kpi["unit"]:
            unit_issues.append(_ref(row, expected=kpi["unit"], found=row["unit"]))
            continue
        low, high = UNIT_BOUNDS.get(kpi["unit"], (None, None))
        user = (kpi.get("verification") or {}).get("status") == USER_STATUS
        if low is None and user:
            continue  # unite declaree par l'utilisateur : pas de borne connue
        if low is None:
            unit_issues.append(_ref(row, found=kpi["unit"], reason="unité sans bornes déclarées"))
        elif row["value"] is not None and not (low <= row["value"] <= high):
            range_issues.append(_ref(row, found=row["value"], reason=f"hors [{low}, {high}]"))
    return [
        make_check("B1_one_unit_per_kpi", "units", "fail" if unit_issues else "pass",
                   f"Unité de chaque ligne = unité du catalogue ; {len(unit_issues)} anomalie(s)", unit_issues),
        make_check("B2_value_ranges", "units", "fail" if range_issues else "pass",
                   "percent dans [0,100], points de % dans [-100,100], densités >= 0 ; "
                   f"{len(range_issues)} anomalie(s)", range_issues),
    ]


def entity_checks(con, rows: list[dict[str, Any]], focus: str, peers: list[str]) -> list[dict]:
    """B3-B4 : uniquement des pays (hors PEERS) ; PEERS = exactement les pairs configures."""
    dim = {iso3: (c, a) for iso3, c, a in con.execute(
        "SELECT iso3, is_country, is_aggregate FROM country_dim").fetchall()}
    entity_issues, peer_issues = [], []
    allowed = {focus, *peers}
    for row in rows:
        iso3 = row["iso3"]
        if iso3 == PEERS_ISO3:
            listed = list(row.get("peers_included") or []) + list(row.get("missing_peers") or [])
            if sorted(listed) != sorted(peers) or len(set(listed)) != len(listed):
                peer_issues.append(_ref(row, expected=peers, found=listed))
            continue
        reasons = []
        if iso3 not in allowed:
            reasons.append("hors pays focus et pairs configures")
        if is_aggregate(iso3) or not is_country(iso3):
            reasons.append("agrégat ou code non-pays")
        if dim.get(iso3) not in (None, (True, False)):
            reasons.append(f"country_dim is_country/is_aggregate = {dim.get(iso3)}")
        if reasons:
            entity_issues.append(_ref(row, reason="; ".join(reasons)))
    return [
        make_check("B3_country_entities_only", "entities", "fail" if entity_issues else "pass",
                   f"Aucun agrégat ni code non-pays hors PEERS ; {len(entity_issues)} ligne(s) en cause",
                   entity_issues),
        make_check("B4_peers_are_configured_peers", "entities", "fail" if peer_issues else "pass",
                   f"PEERS couvre exactement {', '.join(peers)} ; {len(peer_issues)} anomalie(s)", peer_issues),
    ]


def provenance_checks(con, rows: list[dict[str, Any]], *, run_id: str | None, require_same_run: bool,
                      snapshot_id: str | None, index_entry: Mapping[str, Any] | None,
                      manifest: Mapping[str, Any], snapshot_root: Path | None,
                      lineage: Mapping[str, Any], quality: Mapping[str, Any]) -> list[dict]:
    """B5-B7 : snapshot_id et run_id identiques partout, hash des sources concordants,
    empreinte du contenu du warehouse re-verifiee."""
    ids_issues = []
    kv_snapshots = sorted({str(r.get("snapshot_id")) for r in rows})
    kv_runs = sorted({str(r.get("run_id")) for r in rows})
    expected_snapshot = str(snapshot_id)
    for label, value in (("kpi_values", kv_snapshots), ("lineage.json", [str(lineage.get("snapshot_id"))]),
                         ("quality_report.json", [str(quality.get("snapshot_id"))])):
        if value != [expected_snapshot]:
            ids_issues.append({"artifact": label, "field": "snapshot_id", "expected": expected_snapshot, "found": value})
    if snapshot_id is None:
        ids_issues.append({"artifact": "state", "field": "snapshot_id", "reason": "aucun snapshot candidat"})
    elif index_entry is None:
        ids_issues.append({"artifact": "snapshots/index.json", "field": "snapshot_id",
                           "expected": expected_snapshot, "reason": "absent de l'index"})
    elif index_entry.get("status") not in ("pending", "published"):
        ids_issues.append({"artifact": "snapshots/index.json", "field": "status",
                           "found": index_entry.get("status"), "reason": "candidat ni pending ni publié"})
    elif index_entry.get("status") == "pending" and index_entry.get("run_id") != run_id:
        ids_issues.append({"artifact": "snapshots/index.json", "field": "run_id",
                           "expected": run_id, "found": index_entry.get("run_id")})
    reference_run = str(lineage.get("run_id"))
    for label, value in (("kpi_values", kv_runs), ("quality_report.json", [str(quality.get("run_id"))])):
        if value != [reference_run]:
            ids_issues.append({"artifact": label, "field": "run_id", "expected": reference_run, "found": value})
    if require_same_run and reference_run != str(run_id):
        ids_issues.append({"artifact": "lineage.json", "field": "run_id", "expected": run_id, "found": reference_run})

    hash_issues = []
    lineage_inputs = lineage.get("inputs") or {}
    quality_inputs = quality.get("inputs") or {}
    manifest_sources = manifest.get("sources") or {}
    for source in sorted(set(lineage_inputs) | set(quality_inputs) | set(manifest_sources)):
        found = {
            "lineage": (lineage_inputs.get(source) or {}).get("sha256"),
            "quality_report": (quality_inputs.get(source) or {}).get("sha256"),
            "manifest": (manifest_sources.get(source) or {}).get("sha256"),
        }
        blob = (manifest_sources.get(source) or {}).get("blob")
        if blob:
            found["blob_name"] = Path(blob).stem
            blob_path = Path(snapshot_root) / blob if snapshot_root else None
            found["blob_content"] = cached_sha256_file(blob_path) if blob_path and blob_path.is_file() else None
        if len(set(found.values())) != 1 or None in found.values():
            hash_issues.append({"source": source, "found": found})

    outputs = lineage.get("outputs") or {}
    recorded = outputs.get("warehouse_content_sha256")
    tables = outputs.get("warehouse_content_tables") or []
    digest_issues = []
    if not recorded or not tables:
        digest_issues.append({"reason": "aucune empreinte de contenu enregistrée dans lineage.json"})
    else:
        try:
            observed = content_digest(con, tables)
        except Exception as exc:  # noqa: BLE001 - table absente ou illisible
            observed = None
            digest_issues.append({"reason": f"empreinte non recalculable : {exc}"})
        if observed is not None and observed != recorded:
            digest_issues.append({"tables": list(tables), "expected": recorded, "found": observed})

    return [
        make_check("B5_snapshot_and_run_ids", "provenance", "fail" if ids_issues else "pass",
                   f"snapshot_id {expected_snapshot} et run_id {reference_run} identiques dans index, lineage, "
                   f"rapport qualité et kpi_values ; {len(ids_issues)} anomalie(s)", ids_issues),
        make_check("B6_source_hashes", "provenance", "fail" if hash_issues else "pass",
                   "SHA-256 des sources identiques : rapport qualité = lineage = manifeste = nom et contenu "
                   f"du blob ; {len(hash_issues)} source(s) en écart", hash_issues),
        make_check("B7_warehouse_content_digest", "provenance", "fail" if digest_issues else "pass",
                   f"Empreinte du contenu ({', '.join(tables) or 'aucune table'}) recalculée "
                   f"indépendamment ; {len(digest_issues)} anomalie(s)", digest_issues),
    ]


def catalog_checks(rows: list[dict[str, Any]], catalog: Mapping[str, Any], catalog_sha256: str,
                   user_catalog_sha256: str | None = None) -> list[dict]:
    """B8 : definitions verifiees, codes verifies, preuves presentes, catalogue inchange."""
    issues = []
    references = catalog.get("references") or {}
    for kpi_id, kpi in catalog["kpis"].items():
        verification = kpi.get("verification") or {}
        if verification.get("status") == "provisional":
            issues.append({"kpi_id": kpi_id, "reason": "définition provisoire"})
        if verification.get("status") == USER_STATUS and (
                not str(kpi["warehouse"]["source"]).startswith("user:")
                or (kpi.get("formula") or {}).get("from_fact") != "value"):
            issues.append({"kpi_id": kpi_id, "reason": "user_declared hors source user:* ou formule autre que value"})
        if kpi["warehouse"]["indicator_code"] in FINDEX_UNVERIFIED:
            issues.append({"kpi_id": kpi_id, "reason": f"code non vérifié {kpi['warehouse']['indicator_code']}"})
        evidence = verification.get("evidence") or []
        if not evidence or any(ref not in references for ref in evidence):
            issues.append({"kpi_id": kpi_id, "reason": f"preuve absente ou inconnue : {evidence}"})
    for kpi_id in catalog.get("_user_collisions") or []:
        issues.append({"kpi_id": kpi_id, "reason": "le catalogue utilisateur redefinit un KPI officiel"})
    stale = sorted({(r["kpi_id"], r.get("catalog_sha256"), r.get("catalog_version")) for r in rows
                    if r.get("catalog_sha256") != catalog_sha256
                    or r.get("catalog_version") != catalog.get("catalog_version")
                    or r.get("user_catalog_sha256") != user_catalog_sha256})
    for kpi_id, digest, version in stale:
        issues.append({"kpi_id": kpi_id, "reason": "kpi_values calculé avec un autre catalogue",
                       "expected": [catalog.get("catalog_version"), catalog_sha256], "found": [version, digest]})
    return [make_check("B8_catalog_definitions", "catalog", "fail" if issues else "pass",
                       f"Catalogue {catalog.get('catalog_version')} : aucune définition provisoire ni code "
                       f"non vérifié, preuves présentes, hash identique à kpi_values ; {len(issues)} anomalie(s)",
                       issues)]


def quality_gate_check(quality: Mapping[str, Any]) -> dict[str, Any]:
    """B9 : quality gate PASS pour ce run."""
    passed = quality.get("passed") is True
    return make_check("B9_quality_gate", "quality", "pass" if passed else "fail",
                      f"Quality gate {'PASS' if passed else 'FAIL ou absent'} (score "
                      f"{quality.get('overall_score')}, {quality.get('critical_issues')} critique(s))",
                      [] if passed else [{"reason": "quality.passed != true"}])


def caveat_checks(rows: list[dict[str, Any]], catalog: Mapping[str, Any], quality: Mapping[str, Any],
                  recomputed: Mapping[tuple, Mapping[str, Any]], min_change_pp: float) -> list[dict]:
    """C1-C4 : avertissements (jamais des echecs) : vague partielle, pairs partiels,
    constats qualite sur une entree, variations dans le bruit d'enquete."""
    partial_years = set((catalog.get("missing_data_policy") or {}).get("partial_wave_years") or [])
    findex_kpis = {k for k, kpi in catalog["kpis"].items() if kpi["warehouse"]["source"] == "findex"}
    partial_wave = [_ref(r) for r in rows if int(r["year"]) in partial_years and r["value"] is not None
                    and r["kpi_id"] in findex_kpis]
    partial_peers = [_ref(r, missing_peers=list(r.get("missing_peers") or []))
                     for r in rows if r["iso3"] == PEERS_ISO3 and r.get("peer_status") == "partial"]

    findings = []
    records = [("diagnostics", i, d) for i, d in enumerate(quality.get("diagnostics") or [])]
    for (kpi_id, iso3, year), exp in recomputed.items():
        for item in exp["inputs"]:
            if item["value"] is None:  # entree absente : rien a qualifier
                continue
            _, _, source, indicator, dimension, dimension_value = item["fact_key"]
            for collection, index, record in records:
                if ((record.get("source"), normalize_iso3(record.get("iso3")), record.get("year"),
                        record.get("indicator_code")) == (source, iso3, year, indicator)
                        and record.get("dimension", dimension) == dimension
                        and record.get("dimension_value", dimension_value) == dimension_value):
                    findings.append({"kpi_id": kpi_id, "iso3": iso3, "year": year,
                                     "reference": f"quality_report.json#/{collection}/{index}",
                                     "reason": record.get("reason")})

    by_series: dict[tuple, list] = {}
    for row in rows:
        if row["iso3"] == PEERS_ISO3 or row["value"] is None:
            continue
        kpi = catalog["kpis"].get(row["kpi_id"])
        if kpi and kpi["warehouse"]["source"] == "findex":
            by_series.setdefault((row["kpi_id"], row["iso3"]), []).append(row)
    noise = []
    for (kpi_id, iso3), series in sorted(by_series.items()):
        series.sort(key=lambda r: int(r["year"]))
        for before, after in zip(series, series[1:]):
            delta = after["value"] - before["value"]
            if abs(delta) < min_change_pp:
                noise.append({"kpi_id": kpi_id, "iso3": iso3, "year": int(after["year"]),
                              "from_year": int(before["year"]), "change_pp": round(delta, 2)})

    return [
        make_check("C1_partial_survey_wave", "caveat", "warn" if partial_wave else "pass",
                   f"Vague Findex partielle {sorted(partial_years)} : couverture pays incomplete ; "
                   f"{len(partial_wave)} valeur(s) concernee(s)", partial_wave),
        make_check("C2_partial_peer_coverage", "caveat", "warn" if partial_peers else "pass",
                   f"Moyenne des pairs calculée sans tous les pairs ; {len(partial_peers)} ligne(s)", partial_peers),
        make_check("C3_input_quality_findings", "caveat", "warn" if findings else "pass",
                   "Diagnostics du rapport qualité portant exactement sur une entrée d'un KPI ; "
                   f"{len(findings)} constat(s)", findings),
        make_check("C4_within_survey_noise", "caveat", "warn" if noise else "pass",
                   f"Variations d'une vague à l'autre inférieures à {min_change_pp:g} pt (Findex : environ "
                   "1 000 entretiens par pays, aucune erreur type dans le fichier) : a presenter comme "
                   f"\"dans le bruit d'enquete\" ; {len(noise)} variation(s)", noise, affects_publication=False),
    ]


# --------------------------------------------------------------------------- publication
PUBLICATION_STATUSES = ("approved", "approved_with_review_note", "blocked")


def touched_rows(check: Mapping[str, Any], rows: list[dict[str, Any]]) -> set[tuple]:
    """Lignes visees par un controle : (kpi, iso3, annee) explicites, tout un KPI
    (kpi_id seul) ou toutes les lignes (controle de niveau run)."""
    keys = {row_key(r) for r in rows}
    touched: set[tuple] = set()
    for ref in check["affected_rows"]:
        if {"kpi_id", "iso3", "year"} <= set(ref):
            touched.add((ref["kpi_id"], ref["iso3"], int(ref["year"])))
        elif "kpi_id" in ref:
            touched |= {k for k in keys if k[0] == ref["kpi_id"]}
        else:
            return keys
    return touched or (keys if check["result"] == "fail" else set())


def publication_decisions(rows: list[dict[str, Any]],
                          checks: Iterable[Mapping[str, Any]]) -> dict[tuple, str]:
    """approved / approved_with_review_note / blocked pour chaque ligne de kpi_values."""
    blocked: set[tuple] = set()
    noted: set[tuple] = set()
    for check in checks:
        if not check.get("affects_publication", True) or check["result"] == "pass":
            continue
        (blocked if check["result"] == "fail" else noted).update(touched_rows(check, rows))
    by_key = {row_key(r): r for r in rows}
    for key, row in by_key.items():  # une ligne PEERS herite du blocage d'un pair inclus
        if row["iso3"] == PEERS_ISO3 and any(
                (key[0], peer, key[2]) in blocked for peer in row.get("peers_included") or []):
            blocked.add(key)
    decisions = {}
    for key, row in by_key.items():
        if key in blocked:
            decisions[key] = "blocked"
        elif (key in noted or row.get("requires_review") or row.get("review_reasons")
              or row.get("definition_status") == USER_STATUS):  # source utilisateur : toujours une note
            decisions[key] = "approved_with_review_note"
        else:
            decisions[key] = "approved"
    return decisions


def verdict_of(checks: Iterable[Mapping[str, Any]]) -> str:
    results = {check["result"] for check in checks}
    return "fail" if "fail" in results else "pass_with_warnings" if "warn" in results else "pass"


def count_results(checks: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"pass": 0, "warn": 0, "fail": 0}
    for check in checks:
        counts[check["result"]] += 1
    return counts


__all__ = [
    "PEERS_ISO3", "PUBLICATION_STATUSES", "load_catalogs", "user_fact_check", "RAW_TO_FACT", "publication_decisions", "RawSources", "caveat_checks", "catalog_checks", "content_digest",
    "count_results", "entity_checks", "expected_value", "kpi_inputs", "load_catalog_file", "make_check",
    "observe", "parse_formula", "provenance_checks", "quality_gate_check", "raw_to_fact_check",
    "read_kpi_rows", "recompute_checks", "row_key", "touched_rows", "unit_checks", "verdict_of",
]
