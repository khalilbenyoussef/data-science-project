"""Service de la page « Mes données » : detection, mapping depuis les roles choisis,
dry-run et confirmation, au-dessus des outils existants (une seule implementation
du mapping, partagee avec add-source, l'ETL et l'Auditor).

Les fichiers deposes restent dans une zone d'attente (jamais data/uploads) jusqu'a
la confirmation ; ils ne sont jamais executes ni ouverts par un tableur.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import duckdb

from biflow.config import resolve
from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.canonical import canonical, source_label
from biflow.tools.user_sources.cli import rebind
from biflow.tools.user_sources.countries import CountryResolver
from biflow.tools.user_sources.detect import check_file, detect_read_params, detect_structure, read_user_csv
from biflow.tools.user_sources.mapping import (
    OFFICIAL_SOURCES, _validate_role, fingerprint, propose_mapping, slug, validate_mapping,
)
from biflow.tools.user_sources.registry import list_mappings, load_mapping, mapping_path, register, unregister
from biflow.tools.user_sources.data import USER_CHIP
from biflow.utils.countries import is_country, normalize_iso3

NAME = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
UPLOAD_ID = re.compile(r"^[0-9a-f]{32}$")
ROLES = ("country", "year", "indicator", "value", "year_column", "indicator_column", "ignore")
UNITS = ("percent", "fraction", "per_100k_adults", "per_1k_adults", "count")
CURRENCY = re.compile(r"^currency:[A-Za-z]{2,10}$")
MISSING_UNIT = "A_DECLARER"
DEFAULT_PENDING_DIR = "outputs/uploads_pending"


class SourceConflict(UserSourceError):
    """Nom deja pris ou operation impossible dans l'etat actuel (HTTP 409)."""


class SourceNotFound(UserSourceError):
    """Depot ou source inconnu (HTTP 404)."""


def check_name(name: Any) -> str:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise UserSourceError("Nom de source invalide : lettres minuscules, chiffres et _ uniquement "
                              "(2 à 41 caractères, commence par une lettre).")
    if name in OFFICIAL_SOURCES:
        raise UserSourceError(f"« {name} » est une source officielle : choisissez un autre nom.")
    return name


def _aliases(cfg: Mapping[str, Any]) -> dict[str, str]:
    return dict(((cfg.get("countries") or {}).get("name_to_iso3")) or {})


def max_file_mb(cfg: Mapping[str, Any]) -> float:
    return float((cfg.get("uploads") or {}).get("max_file_mb", 200))


# --------------------------------------------------------------------- attente
class PendingUploads:
    """Fichiers deposes en attente de confirmation : <id>.csv + <id>.json."""

    def __init__(self, root: str | Path) -> None:
        self.root = resolve(root)

    def save(self, filename: str, content: bytes) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        upload_id = uuid.uuid4().hex
        (self.root / f"{upload_id}.csv").write_bytes(content)
        (self.root / f"{upload_id}.json").write_text(json.dumps({
            "filename": Path(filename or "fichier.csv").name, "size_bytes": len(content),
            "created_at": datetime.now().isoformat(timespec="seconds")}, ensure_ascii=False), encoding="utf-8")
        return upload_id

    def path(self, upload_id: Any) -> Path:
        if not isinstance(upload_id, str) or not UPLOAD_ID.fullmatch(upload_id):
            raise SourceNotFound("Identifiant de dépôt invalide.")
        path = self.root / f"{upload_id}.csv"
        if not path.is_file():
            raise SourceNotFound("Fichier déposé introuvable ou expiré : déposez-le à nouveau.")
        return path

    def meta(self, upload_id: str) -> dict[str, Any]:
        try:
            return json.loads((self.root / f"{upload_id}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def discard(self, upload_id: str) -> None:
        for suffix in (".csv", ".json"):
            (self.root / f"{upload_id}{suffix}").unlink(missing_ok=True)


# -------------------------------------------------------------------- lecture
def _read(path: Path, cfg: Mapping[str, Any]):
    check_file(path, max_file_mb(cfg))
    resolver = CountryResolver(_aliases(cfg))
    read = detect_read_params(path)
    df = read_user_csv(path, read)
    detection = {**detect_structure(df, read["decimal"], resolver), "read": read}
    return df, detection, resolver


def _roles_from_mapping(mapping: Mapping[str, Any], columns: list[str]) -> dict[str, str]:
    cols = mapping.get("columns") or {}
    roles = {column: "ignore" for column in columns}
    for column in cols.get("year_columns") or []:
        roles[column] = "year_column"
    for column in cols.get("indicator_columns") or {}:
        roles[column] = "indicator_column"
    for role in ("year", "indicator", "value"):
        if cols.get(role):
            roles[cols[role]] = role
    country = (cols.get("country") or {}).get("column")
    if country:
        roles[country] = "country"
    return {column: role for column, role in roles.items() if column in columns}


def _evidence(column: str, role: str, detection: Mapping[str, Any]) -> str:
    cand = detection["candidates"]
    if role == "country":
        found = next((c for c in cand["country"] if c["column"] == column), None)
        if found:
            kind = "codes ISO3" if found["kind"] == "iso3" else "noms de pays"
            return f"{kind} ({round(100 * found['share'])} % reconnus)"
        return "choisie par nom de colonne"
    if role == "year":
        found = next((c for c in cand["year"] if c["column"] == column), None)
        return f"années à 4 chiffres ({round(100 * found['share'])} %)" if found else "nom de colonne"
    if role == "value":
        found = next((c for c in cand["value"] if c["column"] == column), None)
        return f"valeurs numériques ({round(100 * found['share'])} %)" if found else "nom de colonne"
    if role == "year_column":
        return "nom de colonne = année"
    if role == "indicator_column":
        return "colonne numérique : un indicateur"
    if role == "indicator":
        found = next((c for c in cand["indicator"] if c["column"] == column), None)
        return f"{found['distinct']} libellé(s) distinct(s)" if found else "nom de colonne"
    return ""


def country_kind(df, column: str, resolver: CountryResolver) -> dict[str, Any]:
    values = list(dict.fromkeys(str(v).strip() for v in df[column].tolist() if str(v).strip()))
    if not values:
        return {"kind": "name", "share": 0.0}
    iso = sum(resolver.resolve(v, "iso3")[0] is not None for v in values) / len(values)
    name = sum(resolver.resolve(v, "name")[0] is not None for v in values) / len(values)
    return {"kind": "iso3" if iso >= name and iso > 0 else "name", "share": round(max(iso, name), 3)}


def detect_upload(path: Path, cfg: Mapping[str, Any], filename: str = "") -> dict[str, Any]:
    """Structure detectee, roles proposes (avec preuve) et configuration reutilisable."""
    df, detection, resolver = _read(path, cfg)
    columns = [c for c in df.columns if c != "_line"]
    print_fp = fingerprint(df.columns)
    problem = None
    try:
        proposal = propose_mapping("nouvelle_source", str(path), df, detection, resolver)
        roles = _roles_from_mapping(proposal["mapping"], columns)
        origins = proposal["origins"]
    except UserSourceError as exc:
        roles, origins, problem = {column: "ignore" for column in columns}, {}, str(exc)
    country = next((c for c, r in roles.items() if r == "country"), None)
    reusable = [{"name": m.name, "confirmed_at": m.confirmed_at,
                 "indicators": {code: spec.label for code, spec in m.indicators.items()}}
                for m in list_mappings(cfg).values() if m.fingerprint == print_fp]
    return {
        "filename": filename, "rows": int(len(df)), "read": detection["read"],
        "layout": detection["layout"], "layout_evidence": detection["evidence"], "problem": problem,
        "columns": [{
            "name": column, "role": roles.get(column, "ignore"),
            "evidence": _evidence(column, roles.get(column, "ignore"), detection),
            "origin": next((o for r, o in origins.items()
                            if r in ("country", "year", "indicator", "value") and roles.get(column) == r), None),
            "samples": list(dict.fromkeys(str(v) for v in df[column].tolist() if str(v).strip()))[:3],
        } for column in columns],
        "country": ({"column": country, **country_kind(df, country, resolver)} if country else None),
        "fingerprint": print_fp, "reusable": reusable,
    }


# -------------------------------------------------------------------- mapping
def _unit(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if value in UNITS or (isinstance(value, str) and CURRENCY.fullmatch(value)):
        return value
    raise UserSourceError(f"Unité non autorisée : « {value} » (%, fraction, par 100 000 adultes, "
                          "par 1 000 adultes, nombre ou monnaie).")


def build_mapping(name: str, path: Path, df, detection: Mapping[str, Any], payload: Mapping[str, Any],
                  resolver: CountryResolver, cfg: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """(mapping dict, champs manquants). Unite jamais devinee : sans unite, le champ
    est signale et la confirmation reste bloquee."""
    read = detection["read"]
    print_fp = fingerprint(df.columns)
    if payload.get("reuse"):
        saved = check_name(payload["reuse"]) if payload["reuse"] not in OFFICIAL_SOURCES else payload["reuse"]
        target = mapping_path(saved, cfg)
        if not target.is_file():
            raise SourceNotFound(f"Configuration enregistrée « {saved} » introuvable.")
        existing = load_mapping(target)
        if existing.fingerprint != print_fp:
            raise UserSourceError("La configuration enregistrée décrit d'autres colonnes : elle ne peut pas "
                                  "être réutilisée pour ce fichier.")
        data = rebind(existing.model_dump(mode="json"), df.columns)
        data.update(name=name, file=str(path), read=dict(read), fingerprint=print_fp, confirmed_at=None)
        return data, []

    columns = [c for c in df.columns if c != "_line"]
    roles = dict(payload.get("roles") or {})
    unknown = sorted(set(roles) - set(columns))
    if unknown:
        raise UserSourceError(f"Colonnes inconnues dans les rôles : {unknown}")
    bad = sorted({r for r in roles.values() if r not in ROLES})
    if bad:
        raise UserSourceError(f"Rôles inconnus : {bad}")
    by_role = {role: [c for c in columns if roles.get(c) == role] for role in ROLES}
    if len(by_role["country"]) != 1:
        raise UserSourceError("Choisissez exactement une colonne « Pays ».")
    for role, label in (("year", "Année"), ("indicator", "Indicateur"), ("value", "Valeur")):
        if len(by_role[role]) > 1:
            raise UserSourceError(f"Une seule colonne « {label} » est possible.")
    year_cols, ind_cols = by_role["year_column"], by_role["indicator_column"]
    if year_cols and ind_cols:
        raise UserSourceError("« Colonne d'année » et « Colonne d'indicateur » ne peuvent pas être combinées.")
    decimal = read["decimal"]
    country = by_role["country"][0]
    year = (by_role["year"] or [None])[0]
    indicator = (by_role["indicator"] or [None])[0]
    value = (by_role["value"] or [None])[0]
    if year_cols:
        layout = "wide_by_year"
    elif ind_cols:
        layout = "wide_by_indicator"
        if not year:
            raise UserSourceError("Indicateurs en colonnes : une colonne « Année » est requise.")
    else:
        layout = "long"
        if not (year and value):
            raise UserSourceError("Format long : choisissez une colonne « Année » et une colonne « Valeur », "
                                  "ou marquez les colonnes d'années.")
    for role, column in (("country", country), ("year", year), ("value", value)):
        if column:
            problem = _validate_role(df, role, column, decimal, resolver)
            if problem:
                raise UserSourceError(f"Rôle {role} : {problem}")
    for column in year_cols:
        if not re.fullmatch(r"(19|20)\d{2}", column.strip()):
            raise UserSourceError(f"« {column} » n'est pas une année : elle ne peut pas être une colonne d'année.")

    kind = payload.get("country_kind") or country_kind(df, country, resolver)["kind"]
    if kind not in ("iso3", "name"):
        raise UserSourceError("Type de pays inconnu (iso3 ou name).")
    if ind_cols:
        labels = list(ind_cols)
    elif indicator:
        labels = list(dict.fromkeys(str(v).strip() for v in df[indicator] if str(v).strip()))
    else:
        labels = [name]
    chosen = payload.get("indicators") or {}
    indicators, indicator_values, indicator_columns, missing = {}, {}, {}, []
    for label in labels:
        code = slug(label)
        while code in indicators:
            code += "_2"
        spec = chosen.get(code) or {}
        unit = _unit(spec.get("unit"))
        transform = spec.get("transform") or "none"
        if transform not in ("none", "percent_to_fraction"):
            raise UserSourceError("Conversion autorisée : pourcentage -> fraction uniquement, sur demande.")
        if transform == "percent_to_fraction" and unit != "percent":
            raise UserSourceError(f"La conversion pourcentage -> fraction exige l'unité % ({code}).")
        new_label = str(spec.get("label") or label).strip() or label
        if unit is None:
            missing.append({"indicator": code, "label": new_label, "field": "unit"})
        indicators[code] = {"label": new_label, "unit": unit or MISSING_UNIT, "transform": transform}
        if ind_cols:
            indicator_columns[label] = code
        elif indicator:
            indicator_values[label] = code

    country_names = {}
    for raw, code in (payload.get("country_names") or {}).items():
        if code in (None, ""):
            continue  # ignore : la ligne reste exclue
        iso = normalize_iso3(str(code))
        if not iso or not is_country(iso):
            raise UserSourceError(f"Code ISO3 invalide pour « {raw} » : {code}")
        country_names[str(raw)] = iso
    data = {
        "schema_version": 1, "name": name, "fingerprint": print_fp, "file": str(path), "read": dict(read),
        "layout": layout,
        "columns": {"country": {"column": country, "kind": kind}, "year": year, "indicator": indicator,
                    "value": value, "year_columns": year_cols, "indicator_columns": indicator_columns,
                    "dimension": None},
        "indicators": indicators, "indicator_values": indicator_values, "country_names": country_names,
        "confirmed_at": None,
    }
    return data, missing


def evaluate(upload_path: Path, name: str, payload: Mapping[str, Any], cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Dry-run : mapping -> observations canoniques et controles, rien n'est ecrit."""
    check_name(name)
    df, detection, resolver = _read(upload_path, cfg)
    data, missing = build_mapping(name, upload_path, df, detection, payload, resolver, cfg)
    mapping = validate_mapping(data, df)
    frame, report = canonical(mapping, df, CountryResolver({**_aliases(cfg), **mapping.country_names}))
    from biflow.agents.quality import check_user_source

    check = check_user_source(name, frame, report, dict(cfg.get("quality") or {}))
    columns = [c for c in df.columns if c != "_line"]
    blocking = []
    if missing:
        blocking.append("Unité manquante pour : " + ", ".join(m["label"] for m in missing))
    if report["mapped"] == 0:
        blocking.append("Aucune observation exploitable : vérifiez les rôles des colonnes.")
    if report["duplicates"]["conflicting_keys"]:
        blocking.append(f"{report['duplicates']['conflicting_keys']} doublon(s) pays/année/indicateur avec "
                        "des valeurs différentes : corrigez le fichier.")
    return {
        "name": name, "layout": mapping.layout, "roles": _roles_from_mapping(data, columns),
        "indicators": [{"code": code, "label": spec["label"],
                        "unit": None if spec["unit"] == MISSING_UNIT else spec["unit"],
                        "transform": spec["transform"]} for code, spec in data["indicators"].items()],
        "country_names": data["country_names"],
        "missing_fields": missing, "blocking": blocking,
        "rows_mapped_pct": report["mapped_pct"], "observations": report["observations"],
        "mapped": report["mapped"], "empty_cells": report["empty_cells"],
        "year_range": report["year_range"], "countries": report["countries"],
        "unmapped_countries": report["unmapped_countries"], "non_numeric": report["non_numeric"],
        "invalid_years": report["invalid_years"], "duplicates": report["duplicates"],
        "preview": [{key: row[key] for key in ("iso3", "year", "indicator_code", "indicator_label", "value",
                                               "unit", "raw_value", "raw_column", "line")}
                    for row in report["preview"]],
        "quality": {"gate": check["gate"], "score": check["score"],
                    "issues": [{"code": i["code"], "severity": i["severity"], "message": i.get("message")}
                               for i in check["issues"]]},
        "_mapping": data,
    }


def confirm(upload_path: Path, name: str, payload: Mapping[str, Any], cfg: Mapping[str, Any]) -> dict[str, Any]:
    """Enregistre le mapping et copie le fichier dans data/uploads/ (registre existant)."""
    result = evaluate(upload_path, name, payload, cfg)
    if result["blocking"]:
        raise UserSourceError(" ".join(result["blocking"]))
    exists = mapping_path(name, cfg).is_file()
    if exists and not payload.get("replace"):
        raise SourceConflict(f"Une source nommée « {name} » existe déjà : utilisez « Remplacer le fichier » "
                             "ou choisissez un autre nom.")
    df, _, _ = _read(upload_path, cfg)
    mapping = validate_mapping(result["_mapping"], df)
    paths = register(mapping, upload_path, cfg)
    return {"name": name, "paths": paths, "replaced": exists, "dry_run": result}


def remove(name: str, cfg: Mapping[str, Any]) -> None:
    check_name(name)
    if not unregister(name, cfg):
        raise SourceNotFound(f"Aucune source utilisateur nommée « {name} ».")


# ---------------------------------------------------------------- consultation
def _quality(cfg: Mapping[str, Any]) -> dict[str, Any]:
    path = resolve((cfg.get("paths") or {}).get("quality", "data/quality")) / "quality_report.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _facts(warehouse: Path, name: str) -> dict[str, Any]:
    if not warehouse.is_file():
        return {}
    try:
        with duckdb.connect(str(warehouse), read_only=True) as con:
            row = con.execute("SELECT count(*), min(year), max(year), count(DISTINCT iso3), "
                              "count(DISTINCT indicator_code) FROM fact WHERE source = ?",
                              [source_label(name)]).fetchone()
            countries = [r[0] for r in con.execute(
                "SELECT DISTINCT iso3 FROM fact WHERE source = ? ORDER BY 1", [source_label(name)]).fetchall()]
    except duckdb.Error:
        return {}
    return {"rows": int(row[0]), "year_min": row[1], "year_max": row[2], "countries": countries,
            "indicator_count": int(row[4])}


def list_sources(cfg: Mapping[str, Any], warehouse: Path, last_jobs: Mapping[str, Any] | None = None,
                 ) -> list[dict[str, Any]]:
    quality = _quality(cfg)
    checks = quality.get("user_sources") or {}
    excluded = {item.get("source"): item for item in quality.get("excluded_sources") or []}
    out = []
    for name, mapping in list_mappings(cfg).items():
        facts = _facts(warehouse, name)
        check = checks.get(name) or {}
        if name in excluded:
            status, reason = "excluded", excluded[name].get("reason") or "contrôle qualité en échec"
        elif facts.get("rows"):
            status, reason = "included", None
        else:
            status, reason = "pending", "pas encore intégrée : recalcul en attente"
        out.append({
            "name": name, "file": Path(mapping.file).name, "confirmed_at": mapping.confirmed_at,
            "indicators": [{"code": code, "label": spec.label, "unit": spec.stored_unit}
                           for code, spec in mapping.indicators.items()],
            "rows": facts.get("rows", 0), "years": [facts.get("year_min"), facts.get("year_max")]
            if facts.get("rows") else None, "countries": facts.get("countries", []),
            "quality_score": check.get("score"), "status": status, "reason": reason,
            "last_job": (last_jobs or {}).get(name),
        })
    return out


def source_data(cfg: Mapping[str, Any], warehouse: Path, name: str, *, indicator: str | None = None,
                iso3: str | None = None, year: int | None = None) -> dict[str, Any]:
    """Valeurs publiees d'une source (fact, source = user:<name>), lecture seule."""
    check_name(name)
    if not mapping_path(name, cfg).is_file():
        raise SourceNotFound(f"Aucune source utilisateur nommée « {name} ».")
    mapping = load_mapping(mapping_path(name, cfg))
    sql = ("SELECT iso3, year, indicator_code, value, unit FROM fact WHERE source = ?")
    params: list[Any] = [source_label(name)]
    if indicator:
        sql += " AND indicator_code = ?"
        params.append(indicator if "." in indicator else f"{name}.{indicator}")
    if iso3:
        sql += " AND iso3 = ?"
        params.append(str(iso3).upper())
    if year is not None:
        sql += " AND year = ?"
        params.append(int(year))
    rows = []
    if warehouse.is_file():
        try:
            with duckdb.connect(str(warehouse), read_only=True) as con:
                rows = con.execute(sql + " ORDER BY indicator_code, iso3, year", params).fetchall()
        except duckdb.Error:
            rows = []
    labels = {f"{name}.{code}": spec.label for code, spec in mapping.indicators.items()}
    return {
        "name": name, "provider": "user", "chip": USER_CHIP,
        "indicators": [{"code": f"{name}.{code}", "label": spec.label, "unit": spec.stored_unit}
                       for code, spec in mapping.indicators.items()],
        "values": [{"iso3": r[0], "year": int(r[1]), "indicator_code": r[2],
                    "indicator_label": labels.get(r[2], r[2]), "value": float(r[3]) if r[3] is not None else None,
                    "unit": r[4]} for r in rows],
    }


def discard_old_pending(root: Path, max_age_hours: float = 24) -> None:
    """Nettoyage des depots jamais confirmes (zone d'attente)."""
    if not root.is_dir():
        return
    limit = datetime.now().timestamp() - max_age_hours * 3600
    for path in root.iterdir():
        if path.is_file() and path.stat().st_mtime < limit:
            path.unlink(missing_ok=True)


__all__ = [
    "PendingUploads", "SourceConflict", "SourceNotFound", "build_mapping", "check_name", "confirm",
    "detect_upload", "discard_old_pending", "evaluate", "list_sources", "remove", "source_data",
]

