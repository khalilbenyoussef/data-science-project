"""« Vos indicateurs face aux données officielles » : valeur utilisateur à côté du KPI
officiel déclaré comparable (même pays), en lecture seule.

Règles :
- le KPI comparable est déclaré par l'utilisateur à l'étape « Indicateurs », avec la
  case « même définition » cochée ; seule une unité identique (après conversion) est
  acceptée, et l'unité est revérifiée ici (catalogue modifié depuis -> aucune valeur) ;
- valeur utilisateur : année sélectionnée, sinon dernière année antérieure (année affichée) ;
- valeur officielle : ligne kpi_values approuvée (statuts de publication autorisés) de
  l'année sélectionnée, sinon de la dernière vague antérieure (année affichée) ;
- années différentes -> note « années différentes : comparaison indicative » ;
- la comparaison reste indicative : la définition est déclarée par l'utilisateur.
Aucune valeur n'est modifiée ; rien n'est écrit.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import duckdb

from biflow.tools.kpi import DEFAULT_CATALOG, USER_STATUS, load_catalog
from biflow.tools.user_sources.data import USER_CHIP, UserData, display

STATUSES = ("approved", "approved_with_review_note")
INDICATIVE = "Comparaison indicative : définition déclarée par l'utilisateur"
YEARS_DIFFER = "années différentes : comparaison indicative"
UNIT_MISMATCH = "comparaison impossible : unités différentes"


def _denominator(kpi: Mapping[str, Any]) -> str | None:
    den = kpi.get("denominator")
    if isinstance(den, Mapping):
        parts = [str(den[k]) for k in ("population", "basis") if den.get(k)]
        return " · ".join(parts) or None
    return str(den) if den else None


def official_kpis(catalog_path: str | Path = DEFAULT_CATALOG) -> dict[str, dict[str, Any]]:
    """KPI officiels du catalogue (jamais les KPI déclarés par l'utilisateur)."""
    out = {}
    for kpi_id, kpi in load_catalog(catalog_path)["kpis"].items():
        if (kpi.get("verification") or {}).get("status") == USER_STATUS:
            continue
        out[kpi_id] = {"id": kpi_id, "name_fr": kpi.get("name_fr") or kpi.get("name") or kpi_id,
                       "unit": kpi.get("unit"), "definition": kpi.get("definition"),
                       "denominator": _denominator(kpi)}
    return out


def official_value(warehouse: str | Path, kpi_id: str, iso3: str, year: int,
                   statuses: Sequence[str] = STATUSES) -> dict[str, Any] | None:
    """Dernière valeur approuvée de kpi_values (année <= year) pour le pays."""
    path = Path(warehouse)
    if not path.is_file():
        return None
    try:
        with duckdb.connect(str(path), read_only=True) as con:
            row = con.execute(
                "SELECT year, value, unit, publication_status FROM kpi_values WHERE kpi_id = ? AND iso3 = ? "
                "AND year <= ? AND value IS NOT NULL AND publication_status IN ("
                + ", ".join("?" for _ in statuses) + ") ORDER BY year DESC LIMIT 1",
                [kpi_id, iso3, int(year), *statuses]).fetchone()
    except duckdb.Error:
        return None
    if row is None:
        return None
    return {"year": int(row[0]), "value": float(row[1]), "unit": row[2], "display": display(row[1], row[2]),
            "publication_status": row[3]}


def comparisons(user_data: UserData, warehouse: str | Path, iso3: str, year: int,
                kpis: Mapping[str, Mapping[str, Any]], statuses: Sequence[str] = STATUSES) -> dict[str, Any]:
    rows = []
    for item in user_data.indicators():
        kpi_id = item.get("comparable_kpi")
        if not kpi_id:
            continue
        kpi = kpis.get(kpi_id)
        row: dict[str, Any] = {
            "indicator_code": item["code"], "label": item["label"], "unit": item["unit"], "kpi_id": kpi_id,
            "kpi": kpi["name_fr"] if kpi else kpi_id, "definition": (kpi or {}).get("definition"),
            "denominator": (kpi or {}).get("denominator"), "official_unit": (kpi or {}).get("unit"),
            "user": None, "official": None, "status": "ok", "same_year": False, "notes": [],
        }
        if kpi is None:
            row["status"] = "unknown_kpi"
            row["notes"].append("KPI officiel absent du catalogue : aucune comparaison")
        elif kpi["unit"] != item["unit"]:
            row["status"] = "unit_mismatch"
            row["notes"].append(UNIT_MISMATCH)
        else:
            user = user_data.latest(item["code"], iso3, year)
            official = official_value(warehouse, kpi_id, iso3, year, statuses)
            if user:
                row["user"] = {key: user[key] for key in ("value", "display", "year", "unit")} | {
                    "chip": USER_CHIP}
            if official:
                row["official"] = official
            if not user:
                row["status"] = "no_user_value"
                row["notes"].append(f"aucune valeur utilisateur jusqu'en {year}")
            elif not official:
                row["status"] = "no_official_value"
                row["notes"].append(f"aucune valeur officielle approuvée jusqu'en {year}")
            else:
                row["same_year"] = user["year"] == official["year"]
                if not row["same_year"]:
                    row["notes"].append(YEARS_DIFFER)
        rows.append(row)
    return {"iso3": iso3, "year": int(year), "chip": USER_CHIP, "note": INDICATIVE, "rows": rows}


__all__ = ["INDICATIVE", "STATUSES", "UNIT_MISMATCH", "YEARS_DIFFER", "comparisons", "official_kpis",
           "official_value"]
