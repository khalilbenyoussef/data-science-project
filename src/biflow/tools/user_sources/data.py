"""Lecture seule des valeurs des sources utilisateur (fact, source = user:<nom>).

Utilise par Ask Finova (outil get_user_indicator), le bloc « Vos indicateurs face
aux données officielles », l'annexe PDF et la regle de recommandation
user_vs_official. Les valeurs ne sont jamais verifiees par BIFlow : chaque valeur
renvoyee porte le libelle USER_CHIP. Aucune ecriture, aucune table officielle lue.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

import duckdb

from biflow.tools.audit_text import fr_number
from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.canonical import indicator_code
from biflow.tools.user_sources.countries import normalize_name
from biflow.tools.user_sources.registry import list_mappings

USER_CHIP = "Données utilisateur · non vérifiée par BIFlow"
USER_MARKER = "D'après vos données (non vérifiées par BIFlow)"
STOP_WORDS = {"pour", "adultes", "exemple", "fictif", "dans", "avec", "des", "les", "taux", "part", "nombre"}
UNIT_TEXT = {"percent": "%", "fraction": "(fraction)", "per_100k_adults": "pour 100 000 adultes",
             "per_1k_adults": "pour 1 000 adultes", "count": "", "percentage_points": "pts"}


def unit_text(unit: str | None) -> str:
    if not unit:
        return ""
    if unit.startswith("currency:"):
        return unit.split(":", 1)[1]
    return UNIT_TEXT.get(unit, unit)


def display(value: float, unit: str | None) -> str:
    """Valeur telle que stockee (arrondie a 2 decimales pour l'affichage), suivie de l'unite."""
    text = f"{round(float(value), 2):.2f}".rstrip("0").rstrip(".")
    number = fr_number(float(value), len(text.split(".")[1]) if "." in text else 0)
    suffix = unit_text(unit)
    return f"{number} {suffix}".strip()


class UserData:
    """Indicateurs et valeurs des sources utilisateur integrees dans l'entrepot."""

    def __init__(self, cfg: Mapping[str, Any] | None, warehouse: str | Path) -> None:
        self.cfg = cfg
        self.warehouse = Path(warehouse)

    def indicators(self) -> list[dict[str, Any]]:
        """Indicateurs declares (libelle, unite stockee, KPI officiel comparable eventuel)."""
        try:
            mappings = list_mappings(self.cfg)
        except UserSourceError:
            return []
        out = []
        for name, mapping in mappings.items():
            for code, spec in mapping.indicators.items():
                out.append({"code": indicator_code(name, code), "source": name, "label": spec.label,
                            "unit": spec.stored_unit,
                            "comparable_kpi": getattr(spec, "comparable_kpi", None)})
        return out

    def _query(self, sql: str, params: list[Any]) -> list[tuple]:
        if not self.warehouse.is_file():
            return []
        try:
            with duckdb.connect(str(self.warehouse), read_only=True) as con:
                return con.execute(sql, params).fetchall()
        except duckdb.Error:
            return []

    def values(self, *, codes: list[str] | None = None, iso3: str | None = None,
               year_max: int | None = None) -> list[dict[str, Any]]:
        """Observations (dimension « all ») des sources utilisateur, triees par indicateur et annee."""
        known = {item["code"]: item for item in self.indicators()}
        wanted = [c for c in (codes or list(known)) if c in known]
        if not wanted:
            return []
        sql = ("SELECT indicator_code, iso3, year, value, unit FROM fact WHERE source LIKE 'user:%' "
               "AND dimension = 'all' AND value IS NOT NULL AND indicator_code IN ("
               + ", ".join("?" for _ in wanted) + ")")
        params: list[Any] = list(wanted)
        if iso3:
            sql += " AND iso3 = ?"
            params.append(iso3.upper())
        if year_max is not None:
            sql += " AND year <= ?"
            params.append(int(year_max))
        rows = self._query(sql + " ORDER BY indicator_code, iso3, year", params)
        out = []
        for code, country, year, value, unit in rows:
            item = known[code]
            out.append({"indicator_code": code, "label": item["label"], "iso3": country, "year": int(year),
                        "value": float(value), "unit": unit, "display": display(value, unit),
                        "source": f"user:{item['source']}", "user_data": True, "chip": USER_CHIP})
        return out

    def latest(self, code: str, iso3: str, year: int) -> dict[str, Any] | None:
        """Valeur de l'annee demandee, sinon la derniere annee anterieure (annee indiquee)."""
        rows = self.values(codes=[code], iso3=iso3, year_max=year)
        if not rows:
            return None
        row = rows[-1]
        return {**row, "year_requested": int(year), "same_year": row["year"] == int(year)}

    def match(self, text: str) -> list[dict[str, Any]]:
        """Indicateurs utilisateur cites dans une question : code ou libelle (sans la
        parenthese), ou au moins 70 % des mots significatifs du libelle (2 au minimum)."""
        norm = f" {normalize_name(text)} "
        words = set(norm.split())
        found = []
        for item in self.indicators():
            short = normalize_name(item["code"].split(".", 1)[1].replace("_", " "))
            label = normalize_name(re.sub(r"\([^)]*\)", " ", item["label"]))
            significant = {w for w in label.split() if len(w) >= 4 and w not in STOP_WORDS}
            if ((label and f" {label} " in norm) or (short and f" {short} " in norm)
                    or (len(significant) >= 2 and len(significant & words) >= 0.7 * len(significant))):
                found.append(item)
        return found


__all__ = ["USER_CHIP", "USER_MARKER", "UserData", "display", "unit_text"]
