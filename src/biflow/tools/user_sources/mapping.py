"""Proposition et validation du mapping d'une source utilisateur.

Regles d'abord (synonymes de noms de colonnes FR/EN/translitteration arabe,
preuves de la detection), LLM optionnel uniquement pour les roles restes
indetermines et toujours re-valide. L'unite n'est jamais devinee : sans unite
declaree, la proposition contient une question pour l'utilisateur.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Callable, Literal, Mapping

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.countries import CountryResolver, normalize_name
from biflow.tools.user_sources.detect import YEAR_NAME, parse_number
from biflow.utils.countries import is_aggregate

OFFICIAL_SOURCES = {"findex", "fas", "gdp"}
TRANSFORMS = {"none": None, "percent_to_fraction": ("percent", "fraction"),
              "fraction_to_percent": ("fraction", "percent")}
SYNONYMS = {
    "country": {"pays", "country", "codewb", "iso3", "iso", "code pays", "country code", "country name",
                "nom pays", "nom du pays", "economy", "economie", "balad", "bilad", "dawla", "dawlah",
                "بلد", "البلد", "دولة", "الدولة"},
    "year": {"annee", "an", "year", "yr", "date", "period", "periode", "sana", "sanah", "am", "aam",
             "سنة", "السنة", "العام"},
    "indicator": {"indicateur", "indicator", "indicator name", "indicator code", "serie", "series", "variable",
                  "mesure", "measure", "muashir", "mouachir", "mu ashir", "مؤشر", "المؤشر"},
    "value": {"valeur", "value", "val", "obs value", "montant", "amount", "qima", "qimah", "قيمة", "القيمة"},
}


# --------------------------------------------------------------------------- schema
class ReadSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    encoding: str
    separator: Literal[";", ",", "\t", "|"]
    decimal: Literal[".", ","]
    header_row: int = Field(ge=0)


class CountryColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str
    kind: Literal["iso3", "name"]


class DimensionColumn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    column: str
    name: str = Field(min_length=1)


class Columns(BaseModel):
    model_config = ConfigDict(extra="forbid")
    country: CountryColumn
    year: str | None = None
    indicator: str | None = None
    value: str | None = None
    year_columns: list[str] = []
    indicator_columns: dict[str, str] = {}
    dimension: DimensionColumn | None = None


class IndicatorSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1)
    unit: str = Field(min_length=1)          # unite des valeurs telles qu'ecrites dans le fichier
    transform: Literal["none", "percent_to_fraction", "fraction_to_percent"] = "none"

    @model_validator(mode="after")
    def transform_matches_unit(self):
        expected = TRANSFORMS[self.transform]
        if expected and self.unit != expected[0]:
            raise ValueError(f"transform {self.transform} exige unit: {expected[0]} (declare : {self.unit})")
        return self

    @property
    def stored_unit(self) -> str:
        expected = TRANSFORMS[self.transform]
        return expected[1] if expected else self.unit


class SourceMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    name: str
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    file: str
    read: ReadSpec
    layout: Literal["long", "wide_by_year", "wide_by_indicator"]
    columns: Columns
    indicators: dict[str, IndicatorSpec] = Field(min_length=1)
    indicator_values: dict[str, str] = {}    # long / wide_by_year : libelle brut -> code
    country_names: dict[str, str] = {}       # alias confirmes par l'utilisateur
    confirmed_at: str | None = None

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,40}", value):
            raise ValueError("nom de source : minuscules, chiffres et _ (2 a 41 caracteres)")
        if value in OFFICIAL_SOURCES:
            raise ValueError(f"'{value}' est une source officielle")
        return value

    @field_validator("indicators")
    @classmethod
    def valid_codes(cls, value: dict) -> dict:
        bad = [code for code in value if not re.fullmatch(r"[a-z][a-z0-9_]{0,60}", code)]
        if bad:
            raise ValueError(f"codes indicateur invalides : {bad}")
        return value

    @model_validator(mode="after")
    def layout_requirements(self):
        c = self.columns
        if self.layout == "long" and not (c.year and c.value and (c.indicator or len(self.indicators) == 1)):
            raise ValueError("disposition long : colonnes year et value requises (et indicator si plusieurs indicateurs)")
        if self.layout == "wide_by_year" and not c.year_columns:
            raise ValueError("disposition wide_by_year : year_columns requis")
        if self.layout == "wide_by_indicator" and not (c.year and c.indicator_columns):
            raise ValueError("disposition wide_by_indicator : year et indicator_columns requis")
        targets = set(self.indicator_values.values()) | set(c.indicator_columns.values())
        unknown = sorted(targets - set(self.indicators))
        if unknown:
            raise ValueError(f"indicateurs references sans definition (unite) : {unknown}")
        return self


# --------------------------------------------------------------------------- outils
def fingerprint(columns) -> str:
    """Empreinte de structure : SHA-256 des noms de colonnes normalises et tries."""
    names = sorted(normalize_name(str(c)) for c in columns if c != "_line")
    return hashlib.sha256(json.dumps(names, ensure_ascii=False).encode("utf-8")).hexdigest()


def slug(text: str) -> str:
    code = normalize_name(text).replace(" ", "_")
    code = re.sub(r"[^a-z0-9_]", "", code)
    return code if re.match(r"[a-z]", code or "") else f"i_{code}" if code else "indicator"


def _role_by_name(columns, role) -> list[str]:
    return [c for c in columns if normalize_name(c) in SYNONYMS[role]]


def _validate_role(df: pd.DataFrame, role: str, column: str, decimal: str, resolver: CountryResolver) -> str | None:
    """None si la colonne peut jouer ce role, sinon la raison."""
    if column not in df.columns or column == "_line":
        return f"colonne {column!r} absente"
    values = [str(v).strip() for v in df[column].tolist() if str(v).strip()]
    if not values:
        return f"colonne {column!r} vide"
    if role == "country":
        ok = sum(resolver.resolve(v)[0] is not None or is_aggregate(v) for v in set(values)) / len(set(values))
        return None if ok >= 0.5 else f"{column!r} : seulement {ok:.0%} de pays reconnus"
    if role == "year":
        ok = sum(bool(YEAR_NAME.match(v)) for v in values) / len(values)
        return None if ok >= 0.95 else f"{column!r} : {ok:.0%} d'annees a 4 chiffres"
    if role == "value":
        def numeric(v):
            try:
                return parse_number(v, decimal) is not None
            except ValueError:
                return False
        ok = sum(numeric(v) for v in values) / len(values)
        return None if ok >= 0.5 else f"{column!r} : {ok:.0%} de valeurs numeriques"
    return None


# --------------------------------------------------------------------------- proposition
def propose_mapping(name: str, file: str, df: pd.DataFrame, detection: Mapping[str, Any],
                    resolver: CountryResolver | None = None,
                    llm_suggest: Callable[[dict[str, Any]], Mapping[str, str] | None] | None = None,
                    forced_roles: Mapping[str, str] | None = None) -> dict[str, Any]:
    """{mapping (dict, peut etre incomplet), questions, origins} ; rien n'est confirme ici."""
    resolver = resolver or CountryResolver()
    cand = detection["candidates"]
    decimal = detection["read"]["decimal"]
    columns = detection["columns"]
    layout = detection["layout"]
    origins: dict[str, str] = {}
    roles: dict[str, str | None] = {}
    for role, column in (forced_roles or {}).items():  # choix explicite de l'utilisateur, re-valide
        problem = _validate_role(df, role, column, decimal, resolver)
        if problem:
            raise UserSourceError(f"Role {role} -> {problem}")
        roles[role] = column
        origins[role] = "choix de l'utilisateur"
    for role in ("country", "year", "indicator", "value"):
        if role in roles:
            continue
        by_name = [c for c in _role_by_name(columns, role) if c not in roles.values()]
        evidence = [c["column"] for c in cand.get(role, []) if c["column"] not in roles.values()]
        chosen = next((c for c in by_name if c in evidence or role == "indicator"), None)
        if chosen:
            origins[role] = "regle : synonyme de nom de colonne"
        elif len(evidence) == 1 or (evidence and role == "country"):
            chosen = evidence[0]
            origins[role] = "regle : valeurs reconnues"
        roles[role] = chosen

    needed = {"long": ("country", "year", "indicator", "value"), "wide_by_year": ("country",),
              "wide_by_indicator": ("country", "year")}.get(layout, ("country", "year"))
    missing = [r for r in needed if not roles.get(r)]
    if missing and llm_suggest is not None:
        suggestion = llm_suggest({"columns": columns, "layout": layout, "missing_roles": missing,
                                  "sample": df.drop(columns="_line").head(5).to_dict(orient="records")}) or {}
        for role in missing:
            column = suggestion.get(role)
            if not isinstance(column, str):
                continue
            if column in roles.values():
                origins[role] = f"suggestion LLM rejetee : colonne {column!r} deja utilisee"
            else:
                problem = _validate_role(df, role, column, decimal, resolver)
                if problem is None:
                    roles[role] = column
                    origins[role] = "LLM (valide par regles)"
                else:
                    origins[role] = f"suggestion LLM rejetee : {problem}"

    questions: list[str] = []
    if layout is None:
        raise UserSourceError("Structure non reconnue : il faut une colonne pays et une colonne annee "
                              "(ou des colonnes nommees comme des annees). " + detection["evidence"])
    if not roles.get("country"):
        raise UserSourceError("Aucune colonne pays detectable (codes ISO3 ou noms de pays).")
    if layout != "wide_by_year" and not roles.get("year"):
        raise UserSourceError("Aucune colonne annee detectable (annees a 4 chiffres).")

    kind = next((c["kind"] for c in cand["country"] if c["column"] == roles["country"]), "name")
    mapping: dict[str, Any] = {
        "schema_version": 1, "name": name, "fingerprint": fingerprint(columns), "file": file,
        "read": dict(detection["read"]), "layout": layout,
        "columns": {"country": {"column": roles["country"], "kind": kind}},
        "indicators": {}, "indicator_values": {}, "country_names": {},
    }
    if layout == "long":
        mapping["columns"].update(year=roles["year"], value=roles["value"], indicator=roles["indicator"])
        labels = sorted(set(str(v).strip() for v in df[roles["indicator"]] if str(v).strip())) \
            if roles.get("indicator") else [name]
        if not roles.get("value"):
            questions.append("Quelle colonne contient les valeurs ?")
    elif layout == "wide_by_year":
        mapping["columns"].update(year_columns=list(detection["year_columns"]), indicator=roles.get("indicator"))
        labels = sorted(set(str(v).strip() for v in df[roles["indicator"]] if str(v).strip())) \
            if roles.get("indicator") else [name]
    else:
        mapping["columns"]["year"] = roles["year"]
        numeric = [c for c in detection["numeric_columns"] if c not in (roles["country"], roles["year"])]
        mapping["columns"]["indicator_columns"] = {c: slug(c) for c in numeric}
        labels = numeric
    for label in labels:
        code = slug(label)
        while code in mapping["indicators"] and mapping["indicators"][code]["label"] != label:
            code += "_2"
        mapping["indicators"][code] = {"label": label, "unit": None, "transform": "none"}
        if layout != "wide_by_indicator" and (roles.get("indicator") or layout == "long"):
            mapping["indicator_values"][label] = code
        questions.append(f"Unite de l'indicateur '{label}' ({code}) ? (ex. percent, fraction, count, usd) "
                         "- jamais devinee")
    resolved, unresolved = resolver.resolve_all(df[roles["country"]].tolist(), kind)
    for value, reason in unresolved.items():
        questions.append(f"Pays non reconnu : {value!r} ({reason}) - indiquer le code ISO3 ou laisser exclu")
    return {"mapping": mapping, "questions": questions, "origins": origins,
            "unresolved_countries": unresolved}


# Messages pydantic -> francais (les messages metier des validateurs sont deja en francais)
PYDANTIC_FR = {
    "missing": "champ obligatoire absent",
    "extra_forbidden": "champ inconnu (non autorise)",
    "literal_error": "valeur non autorisee",
    "string_too_short": "valeur vide",
    "string_type": "texte attendu",
    "int_type": "entier attendu",
    "int_parsing": "entier attendu",
    "dict_type": "dictionnaire attendu",
    "list_type": "liste attendue",
    "model_type": "objet attendu",
    "string_pattern_mismatch": "format invalide",
    "too_short": "au moins un element requis",
    "greater_than_equal": "valeur trop petite",
}


def _french(error: Mapping[str, Any]) -> str:
    if error["type"] == "value_error":
        return str(error["msg"]).removeprefix("Value error, ")
    return PYDANTIC_FR.get(error["type"], error["msg"])


def validate_mapping(data: Mapping[str, Any], df: pd.DataFrame | None = None) -> SourceMapping:
    """Validation deterministe complete ; UserSourceError avec messages en francais."""
    try:
        mapping = SourceMapping.model_validate(data)
    except ValidationError as exc:
        details = "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'mapping'} : {_french(e)}"
                            for e in exc.errors())
        raise UserSourceError(f"Mapping invalide : {details}") from exc
    if df is not None:
        c = mapping.columns
        referenced = [c.country.column, c.year, c.indicator, c.value, *c.year_columns, *c.indicator_columns,
                      c.dimension.column if c.dimension else None]
        absent = [col for col in referenced if col and col not in df.columns]
        if absent:
            raise UserSourceError(f"Colonnes du mapping absentes du fichier : {absent}")
        if c.indicator and mapping.layout != "wide_by_indicator":
            labels = {str(v).strip() for v in df[c.indicator] if str(v).strip()}
            unmapped = sorted(labels - set(mapping.indicator_values))
            if unmapped:
                raise UserSourceError(f"Indicateurs du fichier sans correspondance dans le mapping : {unmapped}")
    return mapping


def llm_role_suggester(ask_json: Callable[..., Any]) -> Callable[[dict[str, Any]], Mapping[str, str] | None]:
    """Suggestion LLM limitee aux roles de colonnes (jamais d'unite ni de valeur)."""
    def suggest(context: dict[str, Any]) -> Mapping[str, str] | None:
        answer = ask_json(
            "Voici les colonnes et un extrait d'un CSV. Pour chaque role manquant parmi "
            f"{context['missing_roles']}, donne le nom EXACT d'une colonne existante ou null. "
            'Reponds en JSON : {"country": ..., "year": ..., "indicator": ..., "value": ...}. '
            "Ne propose jamais d'unite.\n"
            f"Colonnes : {context['columns']}\nExtrait : {json.dumps(context['sample'], ensure_ascii=False)[:2000]}",
            system="Tu identifies seulement le role des colonnes d'un fichier de donnees.", fallback=None)
        if not isinstance(answer, dict):
            return None
        return {role: col for role, col in answer.items() if role in SYNONYMS and isinstance(col, str)}
    return suggest


__all__ = ["SourceMapping", "IndicatorSpec", "fingerprint", "llm_role_suggester", "propose_mapping",
           "slug", "validate_mapping"]
