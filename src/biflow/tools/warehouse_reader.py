"""Read-only access to the DuckDB warehouse for series outside the KPI catalog.

Only whitelisted indicator/dimension pairs can be queried; callers never supply
SQL. Every value keeps its observation year, a missing observation stays null
and is never replaced by zero. These series are *not* in the KPI catalog yet, so
each one is flagged ``requires_review`` with an explicit reason.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import duckdb

from biflow.tools.dictionary import FINDEX_LABELS
from biflow.config import resolve

NOT_IN_CATALOG = "not_in_kpi_catalog"
DEFINITION_UNVERIFIED = "warehouse_definition_unverified"
LABEL_MISMATCH = "dictionary_label_mismatch"
# fin24aP etait libelle « Paiement numerique » ; le glossaire Findex 2025 l'a corrige
FIN24AP_MISLABELED = "paiement" in FINDEX_LABELS.get("fin24aP", "").lower()


@dataclass(frozen=True)
class SeriesSpec:
    series_id: str
    label: str
    unit: str
    indicator: str
    dimension: str
    dimension_value: str
    note: str | None = None
    extra_review: tuple[str, ...] = ()


# Only these explicit (indicator, dimension, dimension_value) triples are read.
SERIES: dict[str, SeriesSpec] = {
    "atm_per_100k": SeriesSpec(
        "atm_per_100k", "Distributeurs automatiques pour 100 000 adultes",
        "per_100k_adults", "atm_density", "bank_type", "commercial_banks",
    ),
    "branch_per_100k": SeriesSpec(
        "branch_per_100k", "Agences bancaires pour 100 000 adultes",
        "per_100k_adults", "branch_density", "bank_type", "commercial_banks",
    ),
    "depositors_per_1k": SeriesSpec(
        "depositors_per_1k", "Deposants (banques commerciales) pour 1 000 adultes",
        "per_1k_adults", "depositors_per_1k", "bank_type", "commercial_banks",
    ),
    "borrowers_per_1k": SeriesSpec(
        "borrowers_per_1k", "Emprunteurs (banques commerciales) pour 1 000 adultes",
        "per_1k_adults", "borrowers_per_1k", "bank_type", "commercial_banks",
    ),
    "deposit_accounts_per_1k": SeriesSpec(
        "deposit_accounts_per_1k", "Comptes de depot pour 1 000 adultes",
        "per_1k_adults", "deposit_accounts_per_1k", "bank_type", "commercial_banks",
    ),
    "loan_accounts_per_1k": SeriesSpec(
        "loan_accounts_per_1k", "Comptes de pret pour 1 000 adultes",
        "per_1k_adults", "loan_accounts_per_1k", "bank_type", "commercial_banks",
    ),
    "deposits_pct_gdp": SeriesSpec(
        "deposits_pct_gdp", "Encours des depots des banques commerciales (% du PIB)",
        "percent_of_gdp", "deposits_pct_gdp", "bank_type", "commercial_banks",
    ),
    "loans_pct_gdp": SeriesSpec(
        "loans_pct_gdp", "Encours des prets des banques commerciales (% du PIB)",
        "percent_of_gdp", "loans_pct_gdp", "bank_type", "commercial_banks",
    ),
    "formal_saving": SeriesSpec(
        "formal_saving", "Epargne formelle (compte d'epargne)",
        "percent", "fin17a", "all", "all",
        note="Sous-ensemble « epargne formelle » de Findex, hors catalogue KPI.",
    ),
    "formal_borrowing": SeriesSpec(
        "formal_borrowing", "Emprunt formel aupres d'une institution financiere",
        "percent", "fin22a", "all", "all",
        note="Emprunt formel Findex, hors catalogue KPI.",
    ),
    "emergency_money": SeriesSpec(
        "emergency_money", "Capacite a obtenir une somme d'urgence",
        "percent", "fin24aP", "all", "all",
        # Signalement conserve seulement si le dictionnaire garde l'ancien libelle
        note=(
            "fin24aP est etiquete differemment dans tools/dictionary.py : la "
            "definition Findex 2025 est « could obtain emergency money »."
        ) if FIN24AP_MISLABELED else None,
        extra_review=(LABEL_MISMATCH,) if FIN24AP_MISLABELED else (),
    ),
    "urban_account": SeriesSpec(
        "urban_account", "Detention d'un compte - milieu urbain",
        "percent", "account_t_d", "urbanicity", "urban",
    ),
    "rural_account": SeriesSpec(
        "rural_account", "Detention d'un compte - milieu rural",
        "percent", "account_t_d", "urbanicity", "rural",
    ),
}

# Indicator/dimension pairs exposed for group comparisons (dumbbell charts).
SUBGROUP_DIMENSIONS: dict[str, tuple[str, ...]] = {
    "account_t_d": ("gender", "income", "age_cat", "education", "laborforce", "urbanicity"),
    "fiaccount_t_d": ("gender", "income", "urbanicity"),
    "g20_any": ("gender", "income", "age_cat", "education", "laborforce", "urbanicity"),
    "save_any_t_d": ("gender", "income", "education", "urbanicity"),
    "fin17a": ("gender", "income", "education", "urbanicity"),
    "fin22a": ("gender", "income", "education", "urbanicity"),
    "borrow_any_t_d": ("gender", "income", "education", "urbanicity"),
    "fin24aP": ("gender", "income", "urbanicity"),
}

UNIT_FACTOR = {
    "fraction": 100.0,
    "percent": 1.0,
    "per_100k_adults": 1.0,
    "per_1k_adults": 1.0,
    "percent_of_gdp": 1.0,
}


class WarehouseReadError(RuntimeError):
    """The warehouse cannot be read or does not expose the expected tables."""


class UnknownSeriesError(ValueError):
    """A series outside the whitelist was requested."""


def _point(year: int, value: Any, *, factor: float = 1.0) -> dict[str, Any]:
    """Convert a stored fact to a dashboard point; never coerce a gap to zero."""
    if value is None:
        return {"year": int(year), "value": None, "status": "unavailable",
                "reason": "missing_observation"}
    number = float(value) * factor
    if not math.isfinite(number):
        return {"year": int(year), "value": None, "status": "unavailable",
                "reason": "non_finite_value"}
    return {"year": int(year), "value": number, "status": "available", "reason": None}


class WarehouseReader:
    """Whitelisted, parameterised, read-only queries over ``fact``.

    The database is opened with ``read_only=True``; every query binds the country
    code as a parameter. Call ``close()`` (or use the reader as a context
    manager) to release the file handle on Windows.
    """

    def __init__(self, warehouse_path: str | Path) -> None:
        self.path = resolve(warehouse_path)
        if not self.path.is_file():
            raise WarehouseReadError(f"warehouse introuvable : {self.path}")
        try:
            with self._connect() as con:
                tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        except duckdb.Error as exc:  # pragma: no cover - depends on the file
            raise WarehouseReadError(f"warehouse illisible : {exc}") from exc
        missing = {"fact", "country_dim"} - tables
        if missing:
            raise WarehouseReadError(
                "tables manquantes : " + ", ".join(sorted(missing))
            )

    # ------------------------------------------------------------- connection
    def _connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.path), read_only=True)

    def __enter__(self) -> "WarehouseReader":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:  # kept for API symmetry; connections are short-lived
        return None

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def spec(series_id: str) -> SeriesSpec:
        try:
            return SERIES[series_id]
        except KeyError as exc:
            raise UnknownSeriesError(f"serie non autorisee : {series_id}") from exc

    def _rows(self, sql: str, params: Sequence[Any]) -> list[tuple]:
        with self._connect() as con:
            return con.execute(sql, list(params)).fetchall()

    def units(self, series_id: str) -> str:
        spec = self.spec(series_id)
        rows = self._rows(
            "SELECT DISTINCT unit FROM fact WHERE indicator_code = ? AND dimension = ? "
            "AND dimension_value = ?",
            [spec.indicator, spec.dimension, spec.dimension_value],
        )
        units = {row[0] for row in rows if row[0]}
        return units.pop() if len(units) == 1 else spec.unit

    def has_indicator(self, indicator_code: str) -> bool:
        rows = self._rows(
            "SELECT 1 FROM fact WHERE indicator_code = ? LIMIT 1", [indicator_code]
        )
        return bool(rows)

    def years(self, series_id: str, iso3: str) -> list[int]:
        spec = self.spec(series_id)
        rows = self._rows(
            "SELECT year FROM fact WHERE iso3 = ? AND indicator_code = ? "
            "AND dimension = ? AND dimension_value = ? AND value IS NOT NULL "
            "ORDER BY year",
            [iso3.upper(), spec.indicator, spec.dimension, spec.dimension_value],
        )
        return [int(row[0]) for row in rows]

    # ------------------------------------------------------------------ reads
    def series(self, series_id: str, iso3: str) -> list[dict[str, Any]]:
        spec = self.spec(series_id)
        rows = self._rows(
            "SELECT year, value, unit FROM fact WHERE iso3 = ? AND indicator_code = ? "
            "AND dimension = ? AND dimension_value = ? ORDER BY year",
            [iso3.upper(), spec.indicator, spec.dimension, spec.dimension_value],
        )
        return [
            _point(year, value, factor=UNIT_FACTOR.get(unit or spec.unit, 1.0))
            for year, value, unit in rows
        ]

    def value(self, series_id: str, iso3: str, year: int) -> dict[str, Any]:
        spec = self.spec(series_id)
        rows = self._rows(
            "SELECT year, value, unit FROM fact WHERE iso3 = ? AND indicator_code = ? "
            "AND dimension = ? AND dimension_value = ? AND year = ?",
            [iso3.upper(), spec.indicator, spec.dimension, spec.dimension_value, int(year)],
        )
        if not rows:
            return {"year": int(year), "value": None, "status": "unavailable",
                    "reason": "missing_observation"}
        point = _point(rows[0][0], rows[0][1],
                       factor=UNIT_FACTOR.get(rows[0][2] or spec.unit, 1.0))
        point["year"] = int(year)
        return point

    def latest(self, series_id: str, iso3: str) -> dict[str, Any]:
        spec = self.spec(series_id)
        rows = self._rows(
            "SELECT year, value, unit FROM fact WHERE iso3 = ? AND indicator_code = ? "
            "AND dimension = ? AND dimension_value = ? AND value IS NOT NULL "
            "ORDER BY year DESC LIMIT 1",
            [iso3.upper(), spec.indicator, spec.dimension, spec.dimension_value],
        )
        if not rows:
            return {"year": None, "value": None, "status": "unavailable",
                    "reason": "no_observed_year", "requested_year": None}
        point = _point(rows[0][0], rows[0][1],
                       factor=UNIT_FACTOR.get(rows[0][2] or spec.unit, 1.0))
        return point

    def latest_upto(
        self, series_id: str, iso3: str, max_year: int
    ) -> dict[str, Any]:
        """Latest observed year at or before ``max_year`` (never a later wave)."""
        spec = self.spec(series_id)
        rows = self._rows(
            "SELECT year, value, unit FROM fact WHERE iso3 = ? AND indicator_code = ? "
            "AND dimension = ? AND dimension_value = ? AND value IS NOT NULL "
            "AND year <= ? ORDER BY year DESC LIMIT 1",
            [iso3.upper(), spec.indicator, spec.dimension, spec.dimension_value,
             int(max_year)],
        )
        if not rows:
            return {"year": None, "value": None, "status": "unavailable",
                    "reason": "no_observed_year", "requested_year": int(max_year)}
        point = _point(rows[0][0], rows[0][1],
                       factor=UNIT_FACTOR.get(rows[0][2] or spec.unit, 1.0))
        point["requested_year"] = int(max_year)
        return point

    def latest_for_countries(
        self, series_id: str, iso3: Iterable[str]
    ) -> dict[str, dict[str, Any]]:
        return {code: self.latest(series_id, code) for code in iso3}

    def summary(self) -> dict[str, Any]:
        """Row counts by table and source, read directly from the warehouse."""
        tables = self._rows("SELECT COUNT(*) FROM fact", [])
        by_source = self._rows(
            "SELECT source, COUNT(*) FROM fact GROUP BY source ORDER BY source", []
        )
        countries = self._rows(
            "SELECT COUNT(DISTINCT iso3) FROM fact", []
        )
        return {
            "fact_rows": int(tables[0][0]) if tables else 0,
            "countries": int(countries[0][0]) if countries else 0,
            "by_source": {str(source): int(rows) for source, rows in by_source},
        }

    def country_year_value(
        self, column: str, iso3: str, year: int
    ) -> dict[str, Any]:
        """Whitelisted macro column from ``country_year``; null when not observed."""
        allowed = {
            "gdp_pc": "usd_current_per_capita",
            "gdp_usd": "usd_current",
            "gdp_growth_pct": "percent",
            "atm_per_100k": "per_100k_adults",
            "brch_per_100k": "per_100k_adults",
            "depositors_per_1k": "per_1k_adults",
            "borrowers_per_1k": "per_1k_adults",
            "gender_gap_pp": "percentage_points",
        }
        if column not in allowed:
            raise UnknownSeriesError(f"colonne non autorisee : {column}")
        rows = self._rows(
            f"SELECT {column} FROM country_year WHERE iso3 = ? AND year = ?",
            [iso3.upper(), int(year)],
        )
        if not rows:
            return {"year": int(year), "value": None, "status": "unavailable",
                    "reason": "missing_observation", "unit": allowed[column]}
        point = _point(year, rows[0][0])
        point["unit"] = allowed[column]
        return point

    def subgroups(
        self, iso3: str, indicator_code: str, dimension: str, year: int
    ) -> list[dict[str, Any]]:
        """Observed group values for one dimension; the ``all`` total is excluded."""
        allowed = SUBGROUP_DIMENSIONS.get(indicator_code)
        if allowed is None:
            raise UnknownSeriesError(f"indicateur non autorise : {indicator_code}")
        if dimension not in allowed:
            raise UnknownSeriesError(
                f"dimension non autorisee pour {indicator_code} : {dimension}"
            )
        rows = self._rows(
            "SELECT dimension_value, value, unit FROM fact WHERE iso3 = ? "
            "AND indicator_code = ? AND dimension = ? AND year = ? "
            "AND dimension_value NOT IN ('all', 'total') ORDER BY dimension_value",
            [iso3.upper(), indicator_code, dimension, int(year)],
        )
        return [
            {"group": group, **_point(year, value,
                                      factor=UNIT_FACTOR.get(unit or "fraction", 1.0))}
            for group, value, unit in rows
        ]

    def peer_average(self, kpi_id: str, year: int) -> dict[str, Any] | None:
        """Ligne PEERS de kpi_values (moyenne simple calculee par l'etape semantic_kpi,
        jamais recalculee ici) ; None si la table ou la ligne est absente."""
        try:
            rows = self._rows(
                "SELECT value, unit, availability_status, peers_included, missing_peers, "
                "publication_status FROM kpi_values WHERE kpi_id = ? AND iso3 = 'PEERS' AND year = ?",
                [kpi_id, int(year)],
            )
        except duckdb.Error:  # warehouse sans kpi_values (etape semantic_kpi non executee)
            return None
        if len(rows) != 1:
            return None
        value, unit, status, included, missing, publication = rows[0]
        available = status == "available" and value is not None and math.isfinite(float(value))
        return {"value": float(value) if available else None, "unit": unit,
                "status": "available" if available else "unavailable",
                "peers_included": list(included or []), "missing_peers": list(missing or []),
                "publication_status": publication}

    def first_available_year(self, kpi_id: str, iso3: str) -> int | None:
        """Premiere annee de kpi_values ou le KPI est disponible pour le pays ;
        None si aucune vague ne l'observe (ou table kpi_values absente)."""
        try:
            rows = self._rows(
                "SELECT min(year) FROM kpi_values WHERE kpi_id = ? AND iso3 = ? "
                "AND availability_status = 'available' AND value IS NOT NULL",
                [kpi_id, iso3],
            )
        except duckdb.Error:
            return None
        return int(rows[0][0]) if rows and rows[0][0] is not None else None

    def country_meta(self, iso3: str) -> dict[str, Any] | None:
        rows = self._rows(
            "SELECT iso3, country, region, income_group FROM country_dim WHERE iso3 = ?",
            [iso3.upper()],
        )
        if not rows:
            return None
        code, name, region, income = rows[0]
        return {"iso3": code, "name": name or code, "region": region,
                "income_group": income}

    def indicators(self) -> Mapping[str, list[str]]:
        rows = self._rows(
            "SELECT DISTINCT indicator_code, dimension FROM fact ORDER BY 1, 2", []
        )
        found: dict[str, list[str]] = {}
        for indicator, dimension in rows:
            found.setdefault(indicator, []).append(dimension)
        return found

    def require_series(self, series_id: str, iso3: str) -> str:
        """Return ``available`` or the explicit missing reason for a series."""
        return self.latest(series_id, iso3)["status"]


__all__ = [
    "DEFINITION_UNVERIFIED",
    "LABEL_MISMATCH",
    "NOT_IN_CATALOG",
    "SERIES",
    "SUBGROUP_DIMENSIONS",
    "SeriesSpec",
    "UnknownSeriesError",
    "WarehouseReadError",
    "WarehouseReader",
]
