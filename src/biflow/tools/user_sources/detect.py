"""Detection deterministe de la structure d'un CSV utilisateur.

Lecture : encodage verifie sur TOUT le fichier, separateur, ligne d'en-tete,
decimale virgule. Ces regles ne concernent que les sources utilisateur : les
sources officielles gardent read_csv_smart tel quel.

Disposition detectee : long (une ligne par observation), wide_by_year
(colonnes annees) ou wide_by_indicator (une colonne par indicateur), avec les
colonnes candidates pays / annee / indicateur / valeur et leurs preuves.
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

import pandas as pd

from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.countries import CountryResolver
from biflow.utils.countries import is_aggregate

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")
SEPARATORS = (";", ",", "\t", "|")
YEAR_NAME = re.compile(r"^(19|20)\d{2}$")
DOT_NUMBER = re.compile(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?$")
COMMA_NUMBER = re.compile(r"^[+-]?(\d+(,\d*)?|,\d+)([eE][+-]?\d+)?$")
# Separateur de milliers : espace (ou espace insecable) entre groupes stricts de 3 chiffres
THOUSANDS = re.compile(r"^([+-]?\d{1,3})((?:[   ]\d{3})+)([.,]\d+)?$")
SAMPLE_LINES = 200
DEFAULT_MAX_FILE_MB = 200
ALLOWED_SUFFIXES = (".csv", ".txt")


def check_file(path: str | Path, max_file_mb: float | None = None) -> Path:
    """Garde-fous avant lecture : existence, extension CSV, taille maximale, contenu texte."""
    path = Path(path)
    if not path.is_file():
        raise UserSourceError(f"Fichier introuvable : {path}")
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise UserSourceError(f"Format refuse ({path.suffix or 'sans extension'}) : seuls les fichiers CSV "
                              f"({', '.join(ALLOWED_SUFFIXES)}) sont acceptés")
    limit = float(max_file_mb if max_file_mb is not None else DEFAULT_MAX_FILE_MB)
    size_mb = path.stat().st_size / 1e6
    if size_mb > limit:
        raise UserSourceError(f"Fichier trop volumineux : {size_mb:.1f} Mo > {limit:g} Mo (uploads.max_file_mb)")
    with open(path, "rb") as handle:
        if b"\x00" in handle.read(1 << 16):
            raise UserSourceError(f"Contenu binaire détecté dans {path.name} : un fichier CSV texte est attendu")
    return path


# --------------------------------------------------------------------------- lecture
def detect_encoding(raw: bytes) -> str:
    """Premier encodage qui decode le fichier entier (latin-1 decode tout)."""
    for encoding in ENCODINGS[:-1]:
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return ENCODINGS[-1]


def _records(text: str, separator: str, limit: int = SAMPLE_LINES) -> list[list[str]]:
    reader = csv.reader(io.StringIO(text), delimiter=separator)
    out = []
    for record in reader:
        if any(field.strip() for field in record):
            out.append(record)
        if len(out) >= limit:
            break
    return out


def detect_separator(text: str) -> str:
    """Separateur donnant le plus de lignes avec le meme nombre (> 1) de champs."""
    best, best_score = ",", (-1, -1)
    for separator in SEPARATORS:
        records = _records(text, separator)
        counts = [len(r) for r in records]
        if not counts:
            continue
        modal = max(set(counts), key=lambda c: (counts.count(c), c))
        if modal < 2:
            continue
        score = (counts.count(modal), modal)
        if score > best_score:
            best, best_score = separator, score
    return best


def detect_header_row(records: list[list[str]]) -> int:
    """Premiere ligne au nombre de champs modal dont les champs ne sont pas numeriques."""
    counts = [len(r) for r in records]
    modal = max(set(counts), key=lambda c: (counts.count(c), c))
    for index, record in enumerate(records):
        if len(record) == modal:
            numeric = sum(bool(DOT_NUMBER.match(f.strip()) or COMMA_NUMBER.match(f.strip()))
                          and not YEAR_NAME.match(f.strip()) for f in record)
            if numeric <= len(record) // 2:
                return index
    return 0


def detect_decimal(records: list[list[str]], separator: str) -> str:
    """Virgule decimale si les cellules '12,5' dominent les cellules '12.5'."""
    if separator == ",":
        return "."
    comma = dot = 0
    for record in records:
        for field in record:
            field = field.strip()
            if "," in field and COMMA_NUMBER.match(field):
                comma += 1
            elif "." in field and DOT_NUMBER.match(field):
                dot += 1
    return "," if comma > dot else "."


def detect_read_params(path: str | Path) -> dict[str, Any]:
    raw = Path(path).read_bytes()
    if not raw.strip():
        raise UserSourceError(f"Fichier vide : {Path(path).name}")
    encoding = detect_encoding(raw)
    text = raw.decode(encoding)
    separator = detect_separator(text)
    records = _records(text, separator)
    header_row = detect_header_row(records)
    decimal = detect_decimal(records[header_row + 1:], separator)
    return {"encoding": encoding, "separator": separator, "header_row": header_row, "decimal": decimal}


def read_user_csv(path: str | Path, read: dict[str, Any]) -> pd.DataFrame:
    """Toutes les cellules en texte (valeurs brutes conservees) ; en-tetes nettoyes.
    Ajoute `_line` : numero de ligne physique de debut d'enregistrement (1 = premiere)."""
    raw = Path(path).read_bytes()
    try:
        text = raw.decode(read["encoding"])
    except (UnicodeDecodeError, LookupError) as exc:
        raise UserSourceError(f"Encodage {read['encoding']} invalide pour {Path(path).name} : {exc}") from exc
    reader = csv.reader(io.StringIO(text), delimiter=read["separator"])
    rows, header, index = [], None, -1
    while True:
        line = reader.line_num + 1
        try:
            record = next(reader)
        except StopIteration:
            break
        except csv.Error as exc:
            raise UserSourceError(f"CSV illisible ligne {line} : {exc}") from exc
        if not any(field.strip() for field in record):
            continue
        index += 1
        if index < read.get("header_row", 0):
            continue
        if header is None:
            header = [h.strip().lstrip("﻿") for h in record]
            if len(set(header)) != len(header):
                raise UserSourceError(f"En-tetes en double : {sorted({h for h in header if header.count(h) > 1})}")
            continue
        if len(record) != len(header):
            raise UserSourceError(f"Ligne {line} : {len(record)} champ(s) au lieu de {len(header)}")
        rows.append([*record, line])
    if header is None:
        raise UserSourceError("Aucune ligne d'en-tête détectée")
    return pd.DataFrame(rows, columns=[*header, "_line"], dtype=object)


def parse_number(text: object, decimal: str = ".") -> float | None:
    """Nombre selon la decimale declaree ; None si vide ; ValueError si non numerique."""
    if text is None:
        return None
    value = str(text).strip()
    if value == "":
        return None
    grouped = THOUSANDS.match(value)
    if grouped and (grouped.group(3) or "")[:1] in ("", decimal):  # mise en forme, chiffres inchanges
        value = re.sub(r"[   ]", "", value)
    pattern = COMMA_NUMBER if decimal == "," else DOT_NUMBER
    if not pattern.match(value):
        raise ValueError(f"valeur non numérique {value!r}")
    return float(value.replace(",", ".")) if decimal == "," else float(value)


# --------------------------------------------------------------------------- disposition
def _share(values: list[str], test) -> float:
    filled = [v.strip() for v in values if isinstance(v, str) and v.strip()]
    return sum(1 for v in filled if test(v)) / len(filled) if filled else 0.0


def _numeric(value: str, decimal: str) -> bool:
    try:
        return parse_number(value, decimal) is not None
    except ValueError:
        return False


def detect_structure(df: pd.DataFrame, decimal: str = ".", resolver: CountryResolver | None = None) -> dict[str, Any]:
    """Colonnes candidates et disposition, avec preuves (parts de valeurs reconnues)."""
    resolver = resolver or CountryResolver()
    columns = [c for c in df.columns if c != "_line"]
    year_columns = [c for c in columns if YEAR_NAME.match(c)]
    other = [c for c in columns if c not in year_columns]
    candidates: dict[str, list[dict[str, Any]]] = {"country": [], "year": [], "indicator": [], "value": []}
    numeric_columns = []
    for column in other:
        values = [str(v) for v in df[column].tolist()][:2000]
        distinct = list(dict.fromkeys(v.strip() for v in values if v.strip()))
        # Un agregat (WLD...) est un code valide : il compte pour reconnaitre la colonne,
        # mais reste exclu des donnees (liste des pays non reconnus).
        iso_share = _share(distinct, lambda v: resolver.resolve(v, "iso3")[0] is not None or is_aggregate(v))
        name_share = _share(distinct, lambda v: resolver.resolve(v, "name")[0] is not None)
        year_share = _share(values, lambda v: bool(YEAR_NAME.match(v)))
        num_share = _share(values, lambda v: _numeric(v, decimal))
        if iso_share >= 0.8:
            candidates["country"].append({"column": column, "kind": "iso3", "share": round(iso_share, 3)})
        elif name_share >= 0.5:
            candidates["country"].append({"column": column, "kind": "name", "share": round(name_share, 3)})
        elif year_share >= 0.95:
            candidates["year"].append({"column": column, "share": round(year_share, 3)})
        elif num_share >= 0.5:
            numeric_columns.append(column)
            candidates["value"].append({"column": column, "share": round(num_share, 3)})
        elif distinct and len(distinct) <= max(1, len(values) // 2):
            candidates["indicator"].append({"column": column, "distinct": len(distinct)})
    candidates["country"].sort(key=lambda c: -c["share"])

    if len(year_columns) >= 2:
        layout = "wide_by_year"
        evidence = f"{len(year_columns)} colonnes nommées comme des années ({year_columns[0]}..{year_columns[-1]})"
    elif candidates["year"] and candidates["indicator"] and len(numeric_columns) == 1:
        layout = "long"
        evidence = "une colonne année, une colonne indicateur et une seule colonne numérique"
    elif candidates["year"] and numeric_columns:
        layout = "wide_by_indicator"
        evidence = f"une colonne année et {len(numeric_columns)} colonne(s) numérique(s) (une par indicateur)"
    else:
        layout = None
        evidence = "aucune disposition reconnue (colonne année ou colonnes années introuvables)"
    return {"layout": layout, "evidence": evidence, "candidates": candidates,
            "year_columns": year_columns, "numeric_columns": numeric_columns, "columns": columns}


def detect(path: str | Path, resolver: CountryResolver | None = None) -> dict[str, Any]:
    """Parametres de lecture + structure d'un CSV utilisateur."""
    read = detect_read_params(path)
    df = read_user_csv(path, read)
    structure = detect_structure(df, read["decimal"], resolver)
    return {"read": read, **structure, "rows": int(len(df))}


__all__ = ["detect", "detect_read_params", "detect_structure", "parse_number", "read_user_csv"]
