"""Finova dashboard contract: typed, fail-closed, renderer-agnostic.

Every displayed number is copied from a deterministic source: the KPI catalog
(via the analysis dataset), a read-only warehouse query, or a dated static
reference. Nothing is interpolated, zero-filled or approved for publication.
A missing observation is ``null`` with an explicit status; a series that was
never loaded is a ``placeholder`` rendered as "To load".

The React app only formats what this module emits. ``build_finova_spec`` is the
single entry point used by the agent, the API and the tests.
"""
from __future__ import annotations

import math
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Literal, Mapping, Sequence

import yaml
from pydantic import (
    BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr,
    field_validator, model_validator,
)

from biflow.config import resolve
from biflow.tools.dictionary import label_for
from biflow.tools.kpi import BARRIER_KPIS, SUBGROUP_KPIS, load_catalog
from biflow.tools.warehouse_reader import (
    DEFINITION_UNVERIFIED, FIN24AP_MISLABELED, LABEL_MISMATCH, NOT_IN_CATALOG, WarehouseReader,
)
from biflow.utils.io import sha256_file

SCHEMA_VERSION = "2.0"
REFERENCE_PATH = "config/reference/finova_reference.yaml"
PEERS = ("TUN", "DZA", "EGY", "JOR", "MAR")
PRIMARY_COUNTRY = "TUN"
COUNTRY_LABELS = {
    "TUN": "Tunisie", "DZA": "Algérie", "EGY": "Égypte",
    "JOR": "Jordanie", "MAR": "Maroc",
}
PAGE_IDS = ("overview", "inclusion", "access", "exclusion", "poverty", "pipeline")
PROVIDERS = ("semantic", "warehouse", "reference", "placeholder", "derived")
STATUSES = ("available", "unavailable", "placeholder")

BARRIER_CODES = ("fin11a", "fin11b", "fin11c", "fin11d", "fin11e", "fin11f")
# Groupes compares (dimension, titre, cle gauche, cle droite, libelles) ; le KPI de
# chaque groupe vient du catalogue (un KPI par valeur de sous-groupe).
DIMENSION_SPECS = (
    ("gender", "Genre", "women", "men", "Femmes", "Hommes"),
    ("income", "Revenu", "poorest 40%", "richest 60%", "40 % les plus pauvres",
     "60 % les plus riches"),
    ("age_cat", "Âge", "ages 15-24", "age 25+", "15-24 ans", "25 ans et +"),
    ("education", "Éducation", "prim edu or less", "secondary edu or more",
     "Primaire ou moins", "Secondaire ou plus"),
    ("laborforce", "Marché du travail", "out of laborforce", "in laborforce",
     "Hors population active", "Population active"),
    ("urbanicity", "Milieu", "rural", "urban", "Rural", "Urbain"),
)
SUBGROUP_KPI = {group: kpi_id for kpi_id, group in SUBGROUP_KPIS.items()}
# Ecart droite − gauche deja au catalogue : lu tel quel au lieu d'etre soustrait ici
GAP_KPIS = {"gender": "gender_gap", "income": "income_gap", "age_cat": "age_gap"}
# Series FAS lues via le catalogue : identifiant du widget -> KPI
ACCESS_KPIS = {
    "atm_per_100k": "atm_density", "depositors_per_1k": "depositors_per_1k",
    "borrowers_per_1k": "borrowers_per_1k", "loans_pct_gdp": "loans_pct_gdp",
    "deposits_pct_gdp": "deposits_pct_gdp",
}
# KPI du catalogue lus par le contrat : le dataset doit les contenir
SPEC_KPIS = (
    "account_ownership", "branch_density", "digital_payment_rate",
    "saving_rate", "borrowing_rate", "formal_saving_rate", "formal_borrowing_rate",
    "emergency_funds", *ACCESS_KPIS.values(), *GAP_KPIS.values(), *SUBGROUP_KPIS,
    *BARRIER_KPIS,
)
BARRIER_KPI = {code: kpi_id for kpi_id, code in BARRIER_KPIS.items()}


# --------------------------------------------------------------------------- models
class FinModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Chip(FinModel):
    provider: Literal["semantic", "warehouse", "reference", "placeholder", "derived"]
    label: str
    requires_review: bool
    review_reasons: tuple[str, ...] = ()
    note: str | None = None


class Point(FinModel):
    year: int
    value: float | None
    status: Literal["available", "unavailable"]
    reason: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "Point":
        if self.status == "available" and self.value is None:
            raise ValueError("available point without a value")
        if self.status != "available" and self.value is not None:
            raise ValueError("unavailable point must keep a null value")
        return self


class Delta(FinModel):
    value: float
    unit: Literal["percentage_points", "percent", "absolute"]
    from_year: int
    to_year: int
    label: str


class WhyInfo(FinModel):
    definition: str | None = None
    source: str | None = None
    source_url: str | None = None
    filter: str | None = None
    year_used: int | None = None
    definition_status: str | None = None
    review_reasons: tuple[str, ...] = ()
    caveat: str | None = None


class Metric(FinModel):
    id: str
    label: str
    value: float | None
    display: str
    unit: str | None
    year: int | None
    status: Literal["available", "unavailable", "placeholder"]
    provider: Literal["semantic", "warehouse", "reference", "placeholder", "derived"]
    iso3: str | None
    chip: Chip
    delta: Delta | None = None
    evidence_ids: tuple[str, ...] = ()
    why: WhyInfo
    caveat: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "Metric":
        if self.status == "available":
            if self.value is None or not math.isfinite(self.value):
                raise ValueError(f"available metric without a finite value: {self.id}")
        elif self.value is not None:
            raise ValueError(f"non-available metric must keep a null value: {self.id}")
        if self.status == "placeholder" and self.display != "To load":
            raise ValueError(f"placeholder metric must display 'To load': {self.id}")
        if self.status == "unavailable" and self.display != "Indisponible":
            raise ValueError(f"unavailable metric must display 'Indisponible': {self.id}")
        if self.chip.provider != self.provider:
            raise ValueError(f"chip/metric provider mismatch: {self.id}")
        if self.delta is not None:
            if self.delta.unit == "percentage_points" and self.unit != "percent":
                raise ValueError(f"percentage-point delta on a non-percent metric: {self.id}")
            if self.delta.to_year != self.year:
                raise ValueError(f"delta target year must equal the metric year: {self.id}")
        if self.unit == "percent" and self.delta is not None and self.delta.unit not in (
            "percentage_points", "percent",
        ):
            raise ValueError(f"percent metric delta must use points: {self.id}")
        return self


class ChartSeries(FinModel):
    id: str
    label: str
    unit: str | None
    points: tuple[Point, ...]
    provider: Literal["semantic", "warehouse", "reference", "derived"]
    chip: Chip
    evidence_ids: tuple[str, ...] = ()
    color: str | None = None


class ReferenceLine(FinModel):
    label: str
    value: float
    year: int | None
    unit: str | None
    source: str
    source_url: str | None = None
    provider: Literal["reference"] = "reference"
    chip: Chip


class Bar(FinModel):
    id: str | None = None
    label: str
    iso3: str | None
    value: float | None
    display: str
    status: Literal["available", "unavailable", "placeholder"]
    year: int | None
    highlight: bool = False
    provider: Literal["semantic", "warehouse", "reference", "placeholder", "derived"]
    chip: Chip
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> "Bar":
        if self.status == "available" and self.value is None:
            raise ValueError(f"available bar without a value: {self.label}")
        if self.status != "available" and self.value is not None:
            raise ValueError(f"non-available bar must keep a null value: {self.label}")
        if self.status == "placeholder" and self.display != "To load":
            raise ValueError(f"placeholder bar must display 'To load': {self.label}")
        return self


class Step(FinModel):
    id: str
    label: str
    value: float | None
    display: str
    status: Literal["available", "unavailable", "placeholder"]
    year: int | None
    drop_from_previous_pp: float | None = None
    provider: Literal["semantic", "warehouse", "placeholder"]
    chip: Chip
    evidence_ids: tuple[str, ...] = ()


class DumbbellSide(FinModel):
    label: str
    value: float | None
    display: str
    status: Literal["available", "unavailable"]


class DumbbellRow(FinModel):
    id: str
    label: str
    left: DumbbellSide
    right: DumbbellSide
    gap_pp: float | None
    status: Literal["available", "partial", "unavailable"]
    year: int
    provider: Literal["warehouse", "semantic"] = "warehouse"
    chip: Chip
    evidence_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> "DumbbellRow":
        if self.status == "available" and self.gap_pp is None:
            raise ValueError(f"available dumbbell row without a gap: {self.id}")
        if self.status == "unavailable" and self.gap_pp is not None:
            raise ValueError(f"unavailable dumbbell row must keep a null gap: {self.id}")
        return self


class DumbbellGroup(FinModel):
    id: str
    title: str
    dimension: str
    rows: tuple[DumbbellRow, ...]


class GapPoint(FinModel):
    id: str
    label: str
    from_year: int
    to_year: int
    gap_from_pp: float | None
    gap_to_pp: float | None
    change_pp: float | None
    status: Literal["available", "unavailable"]
    evidence_ids: tuple[str, ...] = ()


class HeatmapCell(FinModel):
    column: str
    row: str
    value: float | None
    status: Literal["available", "unavailable", "placeholder"]
    display: str
    note: str | None = None


class Chart(FinModel):
    id: str
    kind: Literal["line", "bar", "funnel", "dumbbell", "gap", "heatmap"]
    title: str
    subtitle: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    unit: str | None = None
    series: tuple[ChartSeries, ...] = ()
    bars: tuple[Bar, ...] = ()
    steps: tuple[Step, ...] = ()
    groups: tuple[DumbbellGroup, ...] = ()
    gap_points: tuple[GapPoint, ...] = ()
    columns: tuple[str, ...] = ()
    rows: tuple[str, ...] = ()
    cells: tuple[HeatmapCell, ...] = ()
    reference_lines: tuple[ReferenceLine, ...] = ()
    notes: tuple[str, ...] = ()
    formula: str | None = None
    chip: Chip | None = None

    @model_validator(mode="after")
    def _kind(self) -> "Chart":
        required = {
            "line": bool(self.series), "bar": bool(self.bars),
            "funnel": len(self.steps) >= 2, "dumbbell": bool(self.groups),
            "gap": bool(self.gap_points),
            "heatmap": bool(self.columns) and bool(self.rows) and bool(self.cells),
        }
        if not required[self.kind]:
            raise ValueError(f"chart {self.id} lacks data for kind {self.kind}")
        if self.kind == "heatmap":
            pairs = {(cell.column, cell.row) for cell in self.cells}
            if len(pairs) != len(self.cells):
                raise ValueError(f"duplicate heatmap cell in {self.id}")
        return self


class Fact(FinModel):
    id: str
    code: str
    label: str
    value: float | None
    unit: str | None
    year: int | None
    iso3: str | None
    provider: Literal["semantic", "warehouse", "reference", "derived"]
    display: str
    evidence_ids: tuple[str, ...] = ()


class Insight(FinModel):
    id: str
    code: str
    statement: str
    severity: Literal["info", "review", "warning"]
    kind: Literal["auto", "xai_evidence", "xai_interpretation", "hypothesis"]
    evidence_ids: tuple[str, ...]

    @field_validator("statement")
    @classmethod
    def _statement(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("insight statement cannot be empty")
        return value


class XaiCard(FinModel):
    title: str
    evidence: tuple[Insight, ...]
    interpretation: tuple[Insight, ...]
    recommendation: Insight
    caveat: str


class ChangeItem(FinModel):
    metric_id: str
    label: str
    previous_value: float | None
    current_value: float | None
    delta: float | None
    unit: str | None
    status: Literal["changed", "stable", "new", "removed", "unavailable"]


class SnapshotDiff(FinModel):
    available: bool
    previous_run_id: str | None = None
    previous_generated_at: str | None = None
    items: tuple[ChangeItem, ...] = ()


class InfoItem(FinModel):
    id: str
    label: str
    value: str | None = None
    unit: str | None = None
    status: str | None = None
    provider: Literal["semantic", "warehouse", "reference", "placeholder", "derived"] | None = None
    chip: Chip | None = None
    year: int | None = None
    note: str | None = None
    source: str | None = None
    source_url: str | None = None


class InfoBlock(FinModel):
    id: str
    kind: Literal[
        "metric_strip", "reference_cards", "pipeline", "sources", "quality",
        "simulator", "ask", "list",
    ]
    title: str
    subtitle: str | None = None
    items: tuple[InfoItem, ...] = ()
    payload: dict[str, Any] = {}


class Notice(FinModel):
    code: str
    severity: Literal["info", "review", "warning"]
    message: str
    kpi_id: str | None = None


class Page(FinModel):
    id: Literal["overview", "inclusion", "access", "exclusion", "poverty", "pipeline"]
    title: str
    subtitle: str
    available: bool = True
    unavailable_reason: str | None = None
    metrics: tuple[Metric, ...] = ()
    charts: tuple[Chart, ...] = ()
    insights: tuple[Insight, ...] = ()
    changes: SnapshotDiff | None = None
    xai: XaiCard | None = None
    blocks: tuple[InfoBlock, ...] = ()
    notices: tuple[Notice, ...] = ()


class CountryRef(FinModel):
    iso3: str
    name: str
    region: str | None = None
    income_group: str | None = None


class DashboardSpec(FinModel):
    schema_version: Literal["2.0"] = SCHEMA_VERSION
    generated_at: str
    run_id: str
    country: CountryRef
    year: int
    years: tuple[int, ...]
    countries_available: tuple[CountryRef, ...]
    pages: tuple[Page, ...]
    facts: tuple[Fact, ...]
    notices: tuple[Notice, ...]
    provenance: dict[str, Any]
    reference: dict[str, Any]
    publication_status: Literal["not_evaluated", "approved", "approved_with_review_note", "blocked"] = "not_evaluated"

    @model_validator(mode="after")
    def _cross_checks(self) -> "DashboardSpec":
        if tuple(page.id for page in self.pages) != PAGE_IDS:
            raise ValueError("dashboard must expose the six pages in order")
        page_ids = [page.id for page in self.pages]
        if len(set(page_ids)) != len(page_ids):
            raise ValueError("duplicate page id")
        metric_ids: list[str] = []
        chart_ids: list[str] = []
        for page in self.pages:
            if not page.available and page.unavailable_reason is None:
                raise ValueError(f"unavailable page needs a reason: {page.id}")
            metric_ids.extend(metric.id for metric in page.metrics)
            chart_ids.extend(chart.id for chart in page.charts)
            evidence = [eid for metric in page.metrics for eid in metric.evidence_ids]
            if len(evidence) != len(set(evidence)):
                raise ValueError(f"duplicate evidence_id in page {page.id}")
        if len(set(metric_ids)) != len(metric_ids):
            raise ValueError("duplicate metric id")
        if len(set(chart_ids)) != len(chart_ids):
            raise ValueError("duplicate chart id")
        fact_ids = [fact.id for fact in self.facts]
        if len(set(fact_ids)) != len(fact_ids):
            raise ValueError("duplicate fact id")
        known = set(fact_ids)
        for page in self.pages:
            for insight in page.insights:
                if not set(insight.evidence_ids) <= known:
                    raise ValueError(f"unknown fact id in insight {insight.id}")
            if page.xai is not None:
                for insight in (*page.xai.evidence, *page.xai.interpretation,
                                page.xai.recommendation):
                    if not set(insight.evidence_ids) <= known:
                        raise ValueError(f"unknown fact id in XAI {insight.id}")
        return self

    def metric(self, metric_id: str) -> Metric:
        for page in self.pages:
            for metric in page.metrics:
                if metric.id == metric_id:
                    return metric
        raise KeyError(metric_id)

    def page(self, page_id: str) -> Page:
        for page in self.pages:
            if page.id == page_id:
                return page
        raise KeyError(page_id)


# ------------------------------------------------------------------------ formatting
_UNIT_LABELS = {
    "percent": "%",
    "percentage_points": "pt",
    "per_100k_adults": "/ 100k adultes",
    "per_1k_adults": "/ 1 000 adultes",
    "percent_of_gdp": "% du PIB",
    "institutions": "institutions",
    "count": "",
}


def format_value(value: float | None, unit: str | None) -> str:
    if value is None:
        return "Indisponible"
    if unit == "percent":
        return f"{value:.1f} %"
    if unit == "percentage_points":
        return f"{value:+.1f} pt"
    if unit == "per_100k_adults":
        return f"{value:.2f} / 100k adultes"
    if unit == "per_1k_adults":
        return f"{value:.1f} / 1 000 adultes"
    if unit == "percent_of_gdp":
        return f"{value:.1f} % du PIB"
    if unit == "TND_per_month":
        return f"{value:,.2f} TND/mois".replace(",", " ")
    if unit == "TND_per_USD":
        return f"{value:.3f} TND/USD"
    if unit == "usd_current_per_capita":
        return f"{value:,.0f} USD/hab".replace(",", " ")
    if unit == "index_2017_100":
        return f"{value:.1f}"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _slug(text: str) -> str:
    out = []
    for char in text.lower():
        if char.isalnum():
            out.append(char)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "item"


# ------------------------------------------------------------------------ reference
class ReferenceEntry(FinModel):
    id: str
    label: str
    metric: str
    value: float | None
    unit: str | None
    year: int | None
    source: str
    source_url: str | None = None
    static: StrictBool
    verification: str
    caveat: str | None = None

    @model_validator(mode="after")
    def _static(self) -> "ReferenceEntry":
        if not self.static:
            raise ValueError(f"reference entry must be static: {self.id}")
        return self


class ReferenceCatalog(FinModel):
    schema_version: StrictInt
    catalog_id: str
    snapshot_date: str
    entries: tuple[ReferenceEntry, ...]

    @model_validator(mode="after")
    def _ids(self) -> "ReferenceCatalog":
        if self.schema_version != 1 or self.catalog_id != "finova_static_reference":
            raise ValueError("unsupported reference catalog")
        ids = [entry.id for entry in self.entries]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate reference id")
        return self

    def by_id(self, entry_id: str) -> ReferenceEntry:
        for entry in self.entries:
            if entry.id == entry_id:
                return entry
        raise KeyError(entry_id)


def load_reference(path: str | Path = REFERENCE_PATH) -> ReferenceCatalog:
    raw = yaml.safe_load(resolve(path).read_bytes())
    return ReferenceCatalog.model_validate(raw)


# ------------------------------------------------------------------------ builders
def _chip(
    provider: str, label: str, *, review: bool, reasons: Sequence[str] = (),
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "provider": provider, "label": label, "requires_review": review,
        "review_reasons": tuple(dict.fromkeys(reasons)), "note": note,
    }


def _semantic_chip(verification: str, observation: Mapping[str, Any],
                   catalog_version: str | None = None) -> dict[str, Any]:
    return _chip(
        "semantic", f"KPI catalog · {verification}",
        review=bool(observation.get("requires_review")),
        reasons=tuple(observation.get("review_reasons") or ()),
        note=f"Définition catalogue v{catalog_version or '?'} appliquée au warehouse.",
    )


def _provisional_suffix(data: "_Data", kpi_id: str, label: str, suffix: str) -> str:
    """Mention « provisoire » seulement si le catalogue le dit."""
    meta = data.kpi_meta.get(kpi_id) or {}
    return label + suffix if meta.get("verification_status") == "provisional" else label


def _warehouse_chip(series_note: str | None, extra: Sequence[str] = ()) -> dict[str, Any]:
    return _chip(
        "warehouse", "Warehouse · hors catalogue KPI", review=True,
        reasons=(NOT_IN_CATALOG, DEFINITION_UNVERIFIED, *extra),
        note=series_note or "Série lue en lecture seule, pas encore validée par le catalogue.",
    )


def _reference_chip(entry: ReferenceEntry) -> dict[str, Any]:
    review = entry.verification not in ("official_source", "aggregate_snapshot")
    return _chip(
        "reference", f"Référence statique · {entry.verification}", review=review,
        reasons=(entry.verification,) if review else (),
        note=f"Instantane {entry.source}.",
    )


def _placeholder_chip(reason: str, note: str | None = None) -> dict[str, Any]:
    return _chip("placeholder", "Donnée non chargée", review=True, reasons=(reason,), note=note)


def _point(raw: Mapping[str, Any]) -> dict[str, Any]:
    value = raw.get("value")
    status = "available" if raw.get("status", raw.get("availability_status")) == "available" and value is not None else "unavailable"
    return {
        "year": int(raw["year"]),
        "value": float(value) if status == "available" else None,
        "status": status,
        "reason": raw.get("reason"),
    }


def _delta(
    points: Sequence[Mapping[str, Any]], target_year: int | None, unit: str | None
) -> dict[str, Any] | None:
    if target_year is None:
        return None
    ordered = sorted(points, key=lambda item: item["year"])
    current = next((p for p in ordered if p["year"] == target_year
                    and p["value"] is not None), None)
    if current is None:
        return None
    previous = [p for p in ordered
                if p["year"] < target_year and p["value"] is not None]
    if not previous:
        return None
    base = previous[-1]
    value = float(current["value"]) - float(base["value"])
    if unit == "percent":
        return {
            "value": value, "unit": "percentage_points",
            "from_year": int(base["year"]), "to_year": int(target_year),
            "label": f"{value:+.1f} pt vs {base['year']}",
        }
    return {
        "value": value, "unit": "absolute",
        "from_year": int(base["year"]), "to_year": int(target_year),
        "label": f"{value:+.2f} vs {base['year']}",
    }


class _Data:
    """Small adapter over the analysis dataset, warehouse and references."""

    def __init__(
        self, dataset: Mapping[str, Any], reader: WarehouseReader | None,
        reference: ReferenceCatalog, catalog: Mapping[str, Any],
        iso3: str, year: int,
    ) -> None:
        self.dataset = dataset
        self.reader = reader
        self.reference = reference
        self.catalog = catalog
        self.iso3 = iso3
        self.year = year
        self.observations = {
            (row["iso3"], row["kpi_id"]): row for row in dataset["observations"]
        }
        self.series = {
            (row["iso3"], row["kpi_id"]): row for row in dataset["series"]
        }
        self.kpi_meta = {item["kpi_id"]: item for item in dataset["scope"]["kpis"]}
        self.countries = {item["iso3"]: item for item in dataset["scope"]["countries"]}

    # ------------------------------------------------------------------ semantic
    def observation(self, kpi_id: str, iso3: str | None = None) -> Mapping[str, Any]:
        return self.observations[(iso3 or self.iso3, kpi_id)]

    def kpi_points(self, kpi_id: str, iso3: str | None = None) -> list[dict[str, Any]]:
        raw = self.series.get((iso3 or self.iso3, kpi_id))
        return [_point(point) for point in (raw or {}).get("points", [])]

    def semantic_metric(
        self, kpi_id: str, *, iso3: str | None = None, label: str | None = None,
        previous: bool = True, metric_id: str | None = None, upto: bool = False,
    ) -> dict[str, Any]:
        """Metrique d'un KPI du catalogue. ``metric_id`` garde l'identifiant du widget ;
        ``upto`` reprend la regle de lecture annuelle : derniere annee observee au plus
        tard a l'annee choisie (jamais une annee posterieure), affichee telle quelle."""
        code = iso3 or self.iso3
        observation = self.observation(kpi_id, code)
        if upto and observation["availability_status"] != "available":
            observation = self._latest_upto(kpi_id, code, observation)
        meta = self.kpi_meta[kpi_id]
        definition = (self.catalog.get("kpis") or {}).get(kpi_id, {})
        source_meta = definition.get("source")
        source_meta = source_meta if isinstance(source_meta, dict) else {}
        unit = observation["unit"]
        available = observation["availability_status"] == "available" and observation["value"] is not None
        metric = {
            "id": metric_id or kpi_id,
            "label": label or meta["name"],
            "value": float(observation["value"]) if available else None,
            "display": format_value(observation["value"] if available else None, unit),
            "unit": unit,
            "year": observation["year"],
            "status": "available" if available else "unavailable",
            "provider": "semantic",
            "iso3": code,
            "chip": _semantic_chip(meta["verification_status"], observation, self.catalog.get("catalog_version")),
            "delta": _delta(self.kpi_points(kpi_id, code), observation["year"], unit) if previous else None,
            "evidence_ids": (observation["evidence_id"],),
            "why": {
                "definition": definition.get("definition"),
                "source": f"KPI catalog · {source_meta.get('dataset', 'findex')} · {observation.get('indicator_code')}",
                "source_url": source_meta.get("url"),
                "filter": f"iso3={code} · {observation.get('subgroup', 'total_population')}",
                "year_used": observation["year"],
                "definition_status": observation["definition_status"],
                "review_reasons": tuple(observation.get("review_reasons") or ()),
                "caveat": None if available else f"Raison : {observation.get('reason')}",
            },
            "caveat": None if available else (
                f"Observation non disponible ({observation.get('reason')}) : aucune "
                "valeur n'est affichée."
            ),
        }
        if not available:
            metric["delta"] = None
        elif upto and observation["year"] != self.year:
            metric["caveat"] = (
                f"Dernière année observée {observation['year']} (série arrêtée) : elle est "
                f"affichée telle quelle, sans substitution par {self.year}."
            )
        return metric

    def review_of(self, *kpi_ids: str) -> dict[str, Any]:
        """Motifs de revue reunis des observations (annee choisie) de plusieurs KPI."""
        rows = [self.observations.get((self.iso3, kpi_id)) or {} for kpi_id in kpi_ids]
        reasons = tuple(dict.fromkeys(r for row in rows for r in row.get("review_reasons") or ()))
        return {"requires_review": any(row.get("requires_review") for row in rows),
                "review_reasons": reasons}

    def kpi_point(self, kpi_id: str, year: int, iso3: str | None = None) -> dict[str, Any]:
        """Valeur d'un KPI pour une annee : observation de l'annee choisie, sinon point
        de la serie. {value | None, evidence_id | None} ; jamais de substitution d'annee."""
        code = iso3 or self.iso3
        observation = self.observations.get((code, kpi_id)) or {}
        if observation.get("year") == year:
            row = observation
        else:
            row = next((p for p in (self.series.get((code, kpi_id)) or {}).get("points") or []
                        if int(p["year"]) == year), None) or {}
        available = row.get("availability_status") == "available" and row.get("value") is not None
        return {"value": float(row["value"]) if available else None,
                "evidence_id": row.get("evidence_id") if available else None}

    def _latest_upto(self, kpi_id: str, code: str,
                     observation: Mapping[str, Any]) -> Mapping[str, Any]:
        """Dernier point disponible de la serie du KPI au plus tard a l'annee choisie."""
        points = (self.series.get((code, kpi_id)) or {}).get("points") or []
        candidates = [p for p in points if p.get("availability_status") == "available"
                      and p.get("value") is not None and int(p["year"]) <= self.year]
        if not candidates:
            return observation
        point = max(candidates, key=lambda p: int(p["year"]))
        return {
            **observation, "year": int(point["year"]), "value": point["value"],
            "availability_status": "available", "reason": None,
            "evidence_id": point["evidence_id"],
            "requires_review": bool(point.get("requires_review")),
            "review_reasons": tuple(observation.get("review_reasons") or ())
            if point.get("requires_review") else (),
        }

    # ----------------------------------------------------------------- warehouse
    def warehouse_metric(
        self, series_id: str, *, iso3: str | None = None, label: str | None = None,
        exact: bool = False, previous: bool = True, unit: str | None = None,
    ) -> dict[str, Any]:
        code = iso3 or self.iso3
        spec = WarehouseReader.spec(series_id)
        effective_unit = unit or spec.unit
        if self.reader is None:
            point = {"year": None, "value": None, "status": "unavailable",
                     "reason": "warehouse_unavailable"}
        elif exact:
            point = self.reader.value(series_id, code, self.year)
        else:
            point = self.reader.latest_upto(series_id, code, self.year)
        value = point["value"] if point["status"] == "available" else None
        year = point.get("year")
        points = self.reader.series(series_id, code) if self.reader is not None else []
        delta = _delta(points, year, effective_unit) if previous and year else None
        caveat = None
        if value is None:
            caveat = "Aucune observation disponible : la valeur reste vide."
        elif not exact and year != self.year:
            caveat = (
                f"Dernière année observée {year} (série arrêtée) : elle est affichée "
                f"telle quelle, sans substitution par {self.year}."
            )
        return {
            "id": series_id,
            "label": label or spec.label,
            "value": float(value) if value is not None else None,
            "display": format_value(value, effective_unit),
            "unit": effective_unit,
            "year": year,
            "status": "available" if value is not None else "unavailable",
            "provider": "warehouse",
            "iso3": code,
            "chip": _warehouse_chip(spec.note, spec.extra_review),
            "delta": delta,
            "evidence_ids": (
                (f"WH-{series_id}-{code}-{year}",) if year is not None else ()
            ),
            "why": {
                "definition": spec.label,
                "source": "Warehouse DuckDB · IMF FAS / World Bank Findex (lecture seule)",
                "filter": f"iso3={code} · {spec.indicator} · {spec.dimension}={spec.dimension_value}",
                "year_used": year,
                "definition_status": "hors_catalogue",
                "review_reasons": (NOT_IN_CATALOG, DEFINITION_UNVERIFIED, *spec.extra_review),
                "caveat": spec.note,
            },
            "caveat": caveat,
        }

    # ---------------------------------------------------------------- reference
    def reference_metric(
        self, entry_id: str, *, label: str | None = None, unit: str | None = None,
    ) -> dict[str, Any]:
        entry = self.reference.by_id(entry_id)
        effective_unit = unit or entry.unit
        value = entry.value
        return {
            "id": entry.id,
            "label": label or entry.label,
            "value": float(value) if value is not None else None,
            "display": format_value(value, effective_unit) if value is not None else "To load",
            "unit": effective_unit,
            "year": entry.year,
            "status": "available" if value is not None else "placeholder",
            "provider": "reference" if value is not None else "placeholder",
            "iso3": None,
            "chip": _reference_chip(entry) if value is not None else _placeholder_chip(
                "reference_value_missing", entry.caveat),
            "delta": None,
            "evidence_ids": (f"REF-{entry.id}",) if value is not None else (),
            "why": {
                "definition": entry.source,
                "source": entry.source,
                "source_url": entry.source_url,
                "filter": "référence statique (aucun filtre pays)",
                "year_used": entry.year,
                "definition_status": entry.verification,
                "review_reasons": ((entry.verification,) if _reference_chip(entry)["requires_review"] else ()),
                "caveat": entry.caveat,
            },
            "caveat": entry.caveat,
        }

    def placeholder_metric(self, metric_id: str, label: str, *, note: str) -> dict[str, Any]:
        return {
            "id": metric_id,
            "label": label,
            "value": None,
            "display": "To load",
            "unit": None,
            "year": None,
            "status": "placeholder",
            "provider": "placeholder",
            "iso3": self.iso3,
            "chip": _placeholder_chip("source_not_collected", note),
            "delta": None,
            "evidence_ids": (),
            "why": {
                "definition": label,
                "source": "Source non collectée dans le warehouse",
                "filter": None,
                "year_used": None,
                "definition_status": "non_charge",
                "review_reasons": ("source_not_collected",),
                "caveat": note,
            },
            "caveat": note,
        }

    # ------------------------------------------------------------------- misc
    def peer_bars(self, kpi_id: str) -> list[dict[str, Any]]:
        bars = []
        for code in PEERS:
            observation = self.observations.get((code, kpi_id))
            if observation is None:
                continue
            meta = self.kpi_meta[kpi_id]
            available = observation["availability_status"] == "available" and observation["value"] is not None
            bars.append({
                "id": f"account_peer_{code}",
                "label": COUNTRY_LABELS.get(code, self.countries.get(code, {}).get("name", code)),
                "iso3": code,
                "value": float(observation["value"]) if available else None,
                "display": format_value(observation["value"] if available else None,
                                        observation["unit"]),
                "status": "available" if available else "unavailable",
                "year": observation["year"],
                "highlight": code == self.iso3,
                "provider": "semantic",
                "chip": _semantic_chip(meta["verification_status"], observation,
                                       self.catalog.get("catalog_version")),
                "evidence_ids": (observation["evidence_id"],),
            })
        return bars

    def subgroup(self, indicator: str, dimension: str, year: int) -> dict[str, dict[str, Any]]:
        if self.reader is None:
            return {}
        return {
            item["group"]: item
            for item in self.reader.subgroups(self.iso3, indicator, dimension, year)
        }

    def macro(self, column: str, unit: str) -> dict[str, Any]:
        point = (
            self.reader.country_year_value(column, self.iso3, self.year)
            if self.reader is not None
            else {"year": self.year, "value": None, "status": "unavailable"}
        )
        value = point.get("value")
        return {
            "id": f"macro-{column}",
            "label": {
                "gdp_pc": "PIB par habitant",
                "gdp_usd": "PIB courant",
                "gdp_growth_pct": "Croissance du PIB",
            }.get(column, column),
            "value": format_value(value, unit) if value is not None else "To load",
            "unit": unit,
            "status": "available" if value is not None else "unavailable",
            "provider": "warehouse",
            "chip": _warehouse_chip("Indicateur macro WDI du warehouse."),
            "year": point.get("year"),
            "note": "Contexte macro, pas un KPI d'inclusion.",
        }


# --------------------------------------------------------------------- fact helpers
def _fact(metric: Mapping[str, Any], *, code: str | None = None,
          fact_id: str | None = None, label: str | None = None,
          value: float | None = None, unit: str | None = None,
          year: int | None = None, iso3: str | None = None,
          display: str | None = None,
          evidence_ids: Sequence[str] | None = None) -> dict[str, Any]:
    iso = iso3 if iso3 is not None else metric.get("iso3")
    fact_year = year if year is not None else metric.get("year")
    fact_code = code or metric.get("id") or "fact"
    return {
        "id": fact_id or f"F-{fact_code}-{iso or 'REF'}-{fact_year or 'NA'}",
        "code": fact_code,
        "label": label or metric["label"],
        "value": value if value is not None else metric.get("value"),
        "unit": unit or metric.get("unit"),
        "year": fact_year,
        "iso3": iso,
        "provider": metric["provider"],
        "display": display or metric.get("display", "Indisponible"),
        "evidence_ids": tuple(evidence_ids if evidence_ids is not None
                              else metric.get("evidence_ids") or ()),
    }


def _unique_facts(facts: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for fact in facts:
        if not fact.get("id"):
            raise ValueError("fact without id")
        if fact["id"] in seen:
            continue
        seen.add(fact["id"])
        out.append(dict(fact))
    return out


# ------------------------------------------------------------------------- builder
def _reference_catalog_meta(reference: ReferenceCatalog) -> dict[str, Any]:
    return {
        "catalog_id": reference.catalog_id,
        "snapshot_date": reference.snapshot_date,
        "entries": len(reference.entries),
    }


def _chart_buildable(chart: Mapping[str, Any]) -> bool:
    """Mirror the Chart validator: an empty chart must be omitted, never emitted."""
    kind = chart.get("kind")
    if kind == "line":
        return bool(chart.get("series"))
    if kind == "bar":
        return bool(chart.get("bars"))
    if kind == "funnel":
        return len(chart.get("steps") or ()) >= 2
    if kind == "dumbbell":
        return bool(chart.get("groups"))
    if kind == "gap":
        return bool(chart.get("gap_points"))
    if kind == "heatmap":
        return (
            bool(chart.get("columns"))
            and bool(chart.get("rows"))
            and bool(chart.get("cells"))
        )
    return True


def _build_blocks(
    data: _Data, dataset: Mapping[str, Any], *, history: Mapping[str, Any] | None,
    pipeline: Mapping[str, Any] | None,
) -> dict[str, Any]:
    iso3, year = data.iso3, data.year
    country = data.countries.get(iso3) or {"iso3": iso3, "name": iso3,
                                           "region": None, "income_group": None}
    pages: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ overview
    overview_metrics = [
        data.semantic_metric("account_ownership"),
        data.semantic_metric("digital_payment_rate"),
        data.semantic_metric("saving_rate", label=_provisional_suffix(
            data, "saving_rate", "Épargne (toute forme", ", définition provisoire") + ")"),
        data.semantic_metric(  # KPI emergency_funds ; libelle du dictionnaire (glossaire 2025)
            "emergency_funds", metric_id="emergency_money", upto=True, label=label_for("fin24aP")),
    ]
    account_metric = overview_metrics[0]
    account_points = data.kpi_points("account_ownership")
    account_chart = {
        "id": "account_ownership_history",
        "kind": "line",
        "title": "Détention d'un compte par vague Findex",
        "subtitle": "Chaque point est une observation observée; aucune interpolation.",
        "x_label": "Année Findex",
        "y_label": "Part des adultes (%)",
        "unit": "percent",
        "series": [{
            "id": "account_ownership",
            "label": f"{country['name']} — détention d'un compte",
            "unit": "percent",
            "points": account_points,
            "provider": "semantic",
            "chip": account_metric["chip"],
            "evidence_ids": tuple(p["evidence_id"] for p in
                                  data.series[(iso3, "account_ownership")]["points"]),
        }],
        "reference_lines": [],
        "notes": [
            "Les repères statiques sont des agrégats Findex 2025 (vague 2024), "
            "pas des observations du pays.",
        ],
        "formula": None,
    }
    for entry_id, color in (("benchmark_mena", None), ("benchmark_lmic", None),
                            ("benchmark_world", None)):
        entry = data.reference.by_id(entry_id)
        account_chart["reference_lines"].append({
            "label": entry.label,
            "value": entry.value,
            "year": entry.year,
            "unit": entry.unit,
            "source": entry.source,
            "source_url": entry.source_url,
            "chip": _reference_chip(entry),
        })

    peers = data.peer_bars("account_ownership")
    observed = [bar for bar in peers if bar["value"] is not None]
    peer_notes = ["Comparaison des détentions de compte à l'année sélectionnée."]
    morocco = next((bar for bar in peers if bar["iso3"] == "MAR"), None)
    subject = next((bar for bar in peers if bar["iso3"] == iso3 and bar["iso3"] != "MAR"), None)
    if morocco and subject and morocco["value"] is not None and subject["value"] is not None:
        gap = morocco["value"] - subject["value"]
        peer_notes.append(
            f"Écart calculé Maroc − {subject['label']} : {gap:+.1f} pt "
            "(différence de deux observations, même année)."
        )
    peer_chart = {
        "id": "account_ownership_peers",
        "kind": "bar",
        "title": "Pairs régionaux — détention d'un compte",
        "subtitle": "DZA, EGY, JOR, MAR, TUN; le pays sélectionné est mis en évidence.",
        "x_label": "Pays",
        "y_label": "Part des adultes (%)",
        "unit": "percent",
        "bars": peers,
        "notes": peer_notes,
    }
    macro_items = [
        data.macro("gdp_pc", "usd_current_per_capita"),
    ]
    if iso3 == "TUN":
        for entry_id in ("fx_tnd_usd_2024", "smig_2025"):
            entry = data.reference.by_id(entry_id)
            macro_items.append({
                "id": entry.id,
                "label": entry.label,
                "value": format_value(entry.value, entry.unit),
                "unit": entry.unit,
                "status": "available",
                "provider": "reference",
                "chip": _reference_chip(entry),
                "year": entry.year,
                "note": entry.caveat,
                "source": entry.source,
                "source_url": entry.source_url,
            })
    macro_block = {
        "id": "macro_context",
        "kind": "metric_strip",
        "title": "Contexte macro",
        "subtitle": "Ordres de grandeur : contexte, pas des KPI d'inclusion.",
        "items": [{
            "id": item["id"], "label": item["label"], "value": item["value"],
            "unit": item.get("unit"), "status": item["status"],
            "provider": item["provider"], "chip": item.get("chip"),
            "year": item.get("year"), "note": item.get("note"),
            "source": item.get("source"), "source_url": item.get("source_url"),
        } for item in macro_items],
        "payload": {},
    }
    pages.append({
        "id": "overview", "title": "Vue d'ensemble",
        "subtitle": "Accès et usage des services financiers — données réelles, sources visibles.",
        "metrics": overview_metrics,
        "charts": [account_chart, peer_chart],
        "insights": [],
        "changes": dict(history) if history is not None else None,
        "blocks": [macro_block],
        "notices": [],
    })

    # ------------------------------------------------------- inclusion/inequalities
    funnel_steps = []
    # (identifiant du widget, KPI du catalogue, libelle) : l'identifiant reste stable
    # pour l'interface, la valeur vient du KPI semantique.
    funnel_inputs = (
        ("account_ownership", "account_ownership", None),
        ("digital_payment_rate", "digital_payment_rate", None),
        ("formal_saving", "formal_saving_rate", "Épargne formelle (fin17a)"),
        ("formal_borrowing", "formal_borrowing_rate", "Emprunt formel (fin22a)"),
    )
    previous_value: float | None = None
    for widget_id, kpi_id, label in funnel_inputs:
        metric = data.semantic_metric(kpi_id, label=label, previous=False)
        value = metric["value"]
        drop = None
        if value is not None and previous_value is not None:
            drop = value - previous_value
        funnel_steps.append({
            "id": widget_id,
            "label": metric["label"],
            "value": value,
            "display": metric["display"],
            "status": metric["status"] if metric["status"] != "placeholder" else "placeholder",
            "year": metric["year"],
            "drop_from_previous_pp": drop,
            "provider": metric["provider"],
            "chip": metric["chip"],
            "evidence_ids": metric["evidence_ids"],
        })
        previous_value = value if value is not None else previous_value
    funnel = {
        "id": "inclusion_funnel",
        "kind": "funnel",
        "title": "Du compte à l'usage formel",
        "subtitle": f"Chaque marche est une question Findex distincte, année {year}.",
        "x_label": None,
        "y_label": "Part des adultes (%)",
        "unit": "percent",
        "steps": funnel_steps,
        "notes": [
            "Ce n'est pas un entonnoir de cohorte : les questions Findex sont "
            "posées séparément, la baisse n'est pas un taux de conversion individuel.",
            "Aucune année n'est substituée : une marche non observée reste vide.",
        ],
    }

    formal_bars = []
    # (widget, KPI, libelle, mis en avant) : seules les mesures « toute forme » sont mises en avant
    for widget_id, kpi_id, label, highlight in (
        ("saving_rate", "saving_rate",
         _provisional_suffix(data, "saving_rate", "Épargne — toute forme", " (provisoire)"), True),
        ("formal_saving", "formal_saving_rate", "Épargne formelle (fin17a)", False),
        ("borrowing_rate", "borrowing_rate",
         _provisional_suffix(data, "borrowing_rate", "Emprunt — toute forme", " (provisoire)"), True),
        ("formal_borrowing", "formal_borrowing_rate", "Emprunt formel (fin22a)", False),
    ):
        metric = data.semantic_metric(kpi_id, label=label, previous=False)
        formal_bars.append({
            "id": widget_id,
            "label": metric["label"], "iso3": iso3, "value": metric["value"],
            "display": metric["display"], "status": metric["status"],
            "year": metric["year"], "highlight": highlight,
            "provider": metric["provider"], "chip": metric["chip"],
            "evidence_ids": metric["evidence_ids"],
        })
    formal_chart = {
        "id": "formal_vs_any",
        "kind": "bar",
        "title": "Formel vs tout moyen confondu",
        "subtitle": "Les écarts sont calculés à partir des deux observations affichées.",
        "x_label": "Mesure",
        "y_label": "Part des adultes (%)",
        "unit": "percent",
        "bars": formal_bars,
        "notes": [],
    }
    if (formal_bars[0]["value"] is not None and formal_bars[1]["value"] is not None):
        formal_chart["notes"].append(
            f"Écart épargne tout − formel : {formal_bars[0]['value'] - formal_bars[1]['value']:+.1f} pt."
        )
    if (formal_bars[2]["value"] is not None and formal_bars[3]["value"] is not None):
        formal_chart["notes"].append(
            f"Écart emprunt tout − formel : {formal_bars[2]['value'] - formal_bars[3]['value']:+.1f} pt."
        )

    def group_gap(dimension: str, left_key: str, right_key: str, gap_year: int):
        """(gauche, droite, ecart, preuves) : sous-groupes et ecart lus au catalogue ;
        l'ecart n'est soustrait ici que s'il n'existe pas de KPI d'ecart."""
        left = data.kpi_point(SUBGROUP_KPI[(dimension, left_key)], gap_year)
        right = data.kpi_point(SUBGROUP_KPI[(dimension, right_key)], gap_year)
        evidence = [p["evidence_id"] for p in (left, right) if p["evidence_id"]]
        if dimension in GAP_KPIS:
            stored = data.kpi_point(GAP_KPIS[dimension], gap_year)
            gap = stored["value"] if left["value"] is not None and right["value"] is not None else None
            if gap is not None:
                evidence.append(stored["evidence_id"])
        else:
            gap = (right["value"] - left["value"]
                   if left["value"] is not None and right["value"] is not None else None)
        return left["value"], right["value"], gap, tuple(evidence)

    dumbbell_groups = []
    for dimension, title, left_key, right_key, left_label, right_label in DIMENSION_SPECS:
        rows = []
        left_value, right_value, gap, evidence = group_gap(dimension, left_key, right_key, year)
        status = ("available" if gap is not None else
                  "partial" if left_value is not None or right_value is not None
                  else "unavailable")
        rows.append({
            "id": f"dumbbell-{dimension}",
            "label": title,
            "left": {"label": left_label, "value": left_value,
                     "display": format_value(left_value, "percent"),
                     "status": "available" if left_value is not None else "unavailable"},
            "right": {"label": right_label, "value": right_value,
                      "display": format_value(right_value, "percent"),
                      "status": "available" if right_value is not None else "unavailable"},
            "gap_pp": gap,
            "status": status,
            "year": year,
            "provider": "semantic",
            "chip": _semantic_chip(
                data.kpi_meta[SUBGROUP_KPI[(dimension, left_key)]]["verification_status"],
                data.review_of(*(SUBGROUP_KPI[(dimension, key)] for key in (left_key, right_key))),
                data.catalog.get("catalog_version")),
            "evidence_ids": evidence,
        })
        if rows[0]["gap_pp"] is None and not any(value is not None for value in
                                                 (left_value, right_value)):
            continue
        dumbbell_groups.append({
            "id": f"account_by_{dimension}", "title": title,
            "dimension": dimension, "rows": rows,
        })
    dumbbell = {
        "id": "account_ownership_groups",
        "kind": "dumbbell",
        "title": "Détention d'un compte par groupe",
        "subtitle": f"Écart en points de pourcentage, année observée {year}.",
        "x_label": "Part des adultes (%)",
        "y_label": None,
        "unit": "percent",
        "groups": dumbbell_groups,
        "notes": [
            "L'écart est calculé à partir des deux sous-groupes affichés.",
            "Les sous-groupes ne sont pas des populations appariées.",
        ],
        "formula": "gap_pp = valeur(groupe avantagé) − valeur(groupe désavantagé)",
    }

    gap_points = []
    for dimension, title, left_key, right_key in (
        ("gender", "Genre", "women", "men"),
        ("income", "Revenu", "poorest 40%", "richest 60%"),
        ("education", "Éducation", "prim edu or less", "secondary edu or more"),
        ("laborforce", "Marché du travail", "out of laborforce", "in laborforce"),
    ):
        gaps: dict[int, float | None] = {}
        evidence: list[str] = []
        for gap_year in (2021, 2024):
            _, _, gaps[gap_year], cited = group_gap(dimension, left_key, right_key, gap_year)
            if gaps[gap_year] is not None:
                evidence.extend(cited)
        change = (gaps[2024] - gaps[2021]
                  if gaps.get(2024) is not None and gaps.get(2021) is not None else None)
        gap_points.append({
            "id": f"gap-{dimension}",
            "label": title,
            "from_year": 2021,
            "to_year": 2024,
            "gap_from_pp": gaps.get(2021),
            "gap_to_pp": gaps.get(2024),
            "change_pp": change,
            "status": "available" if change is not None else "unavailable",
            "evidence_ids": tuple(evidence),
        })
    gap_chart = {
        "id": "gap_change",
        "kind": "gap",
        "title": "Évolution des écarts 2021 → 2024",
        "subtitle": "Variation de l'écart entre deux groupes, en points de pourcentage.",
        "x_label": "Écart (points de pourcentage)",
        "y_label": None,
        "unit": "percentage_points",
        "gap_points": gap_points,
        "notes": [
            "Un écart négatif signifie que le groupe avantagé est en dessous; "
            "la variation est calculée en points, jamais en %.",
        ],
        "formula": "change_pp = gap(2024) − gap(2021)",
    }
    pages.append({
        "id": "inclusion", "title": "Inclusion & inégalités",
        "subtitle": "Usage formel, groupes sociaux et évolution des écarts.",
        "metrics": [],
        "charts": [funnel, formal_chart, dumbbell, gap_chart],
        "insights": [],
        "blocks": [],
        "notices": [],
    })

    # ------------------------------------------------------------ access/credit
    def access_metric(widget_id: str, label: str | None = None) -> dict[str, Any]:
        # meme libelle et meme regle d'annee qu'avant, valeur lue au catalogue KPI
        return data.semantic_metric(
            ACCESS_KPIS[widget_id], metric_id=widget_id, upto=True,
            label=label or WarehouseReader.spec(widget_id).label)

    access_metrics = [
        access_metric("atm_per_100k", "Distributeurs automatiques"),
        data.semantic_metric("branch_density", label="Agences bancaires"),
        access_metric("depositors_per_1k"),
        access_metric("borrowers_per_1k"),
        access_metric("loans_pct_gdp"),
        access_metric("deposits_pct_gdp"),
    ]
    network_series = []
    atm_series = data.kpi_points("atm_density")
    branch_points = data.kpi_points("branch_density")
    window = [p for p in atm_series if p["year"] >= 2015]
    branch_window = [p for p in branch_points if p["year"] >= 2015]
    if window:
        network_series.append({
            "id": "atm_per_100k", "label": "Distributeurs automatiques",
            "unit": "per_100k_adults", "points": window, "provider": "semantic",
            "chip": access_metrics[0]["chip"],
            "evidence_ids": tuple(p["evidence_id"] for p in
                                  data.series[(iso3, "atm_density")]["points"]
                                  if p["year"] >= 2015),
        })
    if branch_window:
        network_series.append({
            "id": "branch_density", "label": "Agences bancaires",
            "unit": "per_100k_adults", "points": branch_window, "provider": "semantic",
            "chip": access_metrics[1]["chip"], "color": "#4ADE80",
            "evidence_ids": tuple(p["evidence_id"] for p in
                                  data.series[(iso3, "branch_density")]["points"]
                                  if p["year"] >= 2015),
        })
    network_chart = {
        "id": "physical_network",
        "kind": "line",
        "title": f"Réseau physique en {COUNTRY_LABELS.get(iso3, iso3)} (2015-2024)",
        "subtitle": "ATMs et agences pour 100 000 adultes.",
        "x_label": "Année",
        "y_label": "Pour 100 000 adultes",
        "unit": "per_100k_adults",
        "series": network_series,
        "notes": ["Deux échelles comparables (même unité). Aucune donnée annuelle inventée."],
    }
    peer_atm_bars = []
    for code in PEERS:
        if (code, "atm_density") not in data.observations:
            continue
        meta = data.countries.get(code, {})
        point = data.semantic_metric("atm_density", iso3=code, upto=True, previous=False)
        value = point["value"]
        peer_atm_bars.append({
            "id": f"atm_peer_{code}",
            "label": COUNTRY_LABELS.get(code, meta.get("name", code)), "iso3": code, "value": value,
            "display": format_value(value, "per_100k_adults"),
            "status": "available" if value is not None else "unavailable",
            "year": point["year"], "highlight": code == iso3,
            "provider": "semantic", "chip": point["chip"],
            "evidence_ids": point["evidence_ids"] if value is not None else (),
        })
    peer_atm_chart = {
        "id": "atm_peers", "kind": "bar",
        "title": "ATMs pour 100 000 adultes — pairs",
        "subtitle": "Dernière année disponible au plus tard à l'année sélectionnée.",
        "x_label": "Pays", "y_label": "ATMs / 100k adultes",
        "unit": "per_100k_adults", "bars": peer_atm_bars, "notes": [],
    }

    index_series = []
    base_year = 2017
    digital_points = data.kpi_points("digital_payment_rate")
    for series_id, label, points, provider, chip, color in (
        ("atm_per_100k", "ATMs (offre)", atm_series, "semantic",
         access_metrics[0]["chip"], "#FFC93C"),
        ("digital_payment_rate", "Paiements numériques (demande)", digital_points,
         "semantic", overview_metrics[1]["chip"], "#8DB0FF"),
    ):
        base = next((p for p in points if p["year"] == base_year and p["value"]), None)
        if base is None:
            continue
        indexed = [
            {"year": p["year"], "value": (p["value"] / base["value"] * 100.0)
             if p["value"] is not None else None,
             "status": p["status"], "reason": p.get("reason")}
            for p in points if p["year"] >= base_year
        ]
        index_series.append({
            "id": f"index_{series_id}", "label": label, "unit": "index_2017_100",
            "points": indexed, "provider": provider, "chip": chip, "color": color,
            "evidence_ids": tuple(p.get("evidence_id") for p in points
                                  if p["year"] >= base_year and p.get("evidence_id")),
        })
    index_chart = {
        "id": "supply_demand_index",
        "kind": "line",
        "title": "Offre vs demande, base 2017 = 100",
        "subtitle": "Indice calculé en code à partir des séries affichées.",
        "x_label": "Année", "y_label": "Indice (2017 = 100)",
        "unit": "index_2017_100", "series": index_series,
        "notes": [
            "Indice = valeur / valeur 2017 × 100; une année sans observation reste vide.",
            "L'offre (ATMs) et la demande (paiements numériques) ont des définitions distinctes.",
        ],
        "formula": "index_t = 100 × valeur_t / valeur_2017",
    }
    pages.append({
        "id": "access", "title": "Accès & crédit",
        "subtitle": "Réseau physique, dépôts, crédits et écart offre/demande.",
        "metrics": access_metrics,
        "charts": [network_chart, peer_atm_chart, index_chart],
        "insights": [],
        "blocks": [],
        "notices": [],
    })

    # ------------------------------------------------------------- why exclusion
    # Barrieres fin11a-f : KPI du catalogue pour le pays, moyenne PEERS de kpi_values
    barrier_rows = list(BARRIER_CODES)
    country_column = COUNTRY_LABELS.get(iso3, country.get("name", iso3))
    barrier_cells, peer_rows = [], {}
    for code in barrier_rows:
        observation = data.observations.get((iso3, BARRIER_KPI[code])) or {}
        available = observation.get("availability_status") == "available" and observation.get("value") is not None
        value = float(observation["value"]) if available else None
        barrier_cells.append({
            "column": country_column, "row": code, "value": value,
            "status": "available" if available else "unavailable",
            "display": format_value(value, "percent"),
            "note": label_for(code) if available else (
                f"Aucune observation {year} ({observation.get('reason') or 'missing_observation'}).")})
        peer_rows[code] = data.reader.peer_average(BARRIER_KPI[code], year) if data.reader else None
    configured = sorted({c for row in peer_rows.values() if row
                         for c in (*row["peers_included"], *row["missing_peers"])})
    peer_column = f"Moyenne des pairs ({', '.join(configured)})" if configured else "Moyenne des pairs"
    missing = sorted({c for row in peer_rows.values() if row and row["status"] == "available"
                      for c in row["missing_peers"]})
    for code in barrier_rows:
        row = peer_rows[code]
        value = row["value"] if row and row["status"] == "available" else None
        if row is None:
            note = "Moyenne des pairs indisponible : kpi_values absent du warehouse."
        elif value is None:
            note = f"Aucun pair observé en {year}."
        elif row["missing_peers"]:
            note = (f"Couverture partielle : moyenne de {', '.join(row['peers_included'])} ; "
                    f"{', '.join(row['missing_peers'])} sans observation {year}.")
        else:
            note = f"Moyenne simple de {', '.join(row['peers_included'])}."
        barrier_cells.append({"column": peer_column, "row": code, "value": value,
                              "status": "available" if value is not None else "unavailable",
                              "display": format_value(value, "percent"), "note": note})
    barrier_notes = [
        "Plusieurs raisons peuvent être citées : les parts ne s'additionnent pas à 100 %.",
        "Part de tous les adultes (15 ans et plus) ; comptes bancaires uniquement (hors mobile money).",
    ]
    if missing:
        barrier_notes.append(
            f"Moyenne des pairs partielle : {', '.join(missing)} sans observation en {year}.")
    barrier_notes.append("Aucune barre n'est dessinée à partir d'une valeur inventée.")
    barrier_chart = {
        "id": "barriers_heatmap", "kind": "heatmap",
        "title": "Barrières à l'ouverture d'un compte",
        "subtitle": f"Raisons déclarées de ne pas avoir de compte bancaire, année {year} (Findex).",
        "x_label": None, "y_label": None, "unit": "percent",
        "columns": (country_column, peer_column),
        "rows": tuple(barrier_rows),
        "cells": barrier_cells,
        "notes": barrier_notes,
    }
    urban = data.semantic_metric("account_ownership_urban", metric_id="urban_account",
                                 label="Compte — milieu urbain", previous=False)
    rural = data.semantic_metric("account_ownership_rural", metric_id="rural_account",
                                 label="Compte — milieu rural", previous=False)
    urban_rural_chart = {
        "id": "urban_rural", "kind": "bar",
        "title": "Détention d'un compte : urbain vs rural",
        "subtitle": f"Année observée {year} (Findex, dimension urbanicity).",
        "x_label": "Milieu", "y_label": "Part des adultes (%)", "unit": "percent",
        "bars": [
            {"id": "urban_account", "label": "Urbain", "iso3": iso3, "value": urban["value"],
             "display": urban["display"], "status": urban["status"],
             "year": urban["year"], "highlight": False, "provider": urban["provider"],
             "chip": urban["chip"], "evidence_ids": urban["evidence_ids"]},
            {"id": "rural_account", "label": "Rural", "iso3": iso3, "value": rural["value"],
             "display": rural["display"], "status": rural["status"],
             "year": rural["year"], "highlight": True, "provider": rural["provider"],
             "chip": rural["chip"], "evidence_ids": rural["evidence_ids"]},
        ],
        "notes": [],
    }
    if urban["value"] is not None and rural["value"] is not None:
        urban_rural_chart["notes"].append(
            f"Écart urbain − rural : {urban['value'] - rural['value']:+.1f} pt."
        )
    context_items = []
    context_entries = (
        ("poverty_rate_urban_2021", "poverty_rate_rural_2021")
        if iso3 == "TUN" else ()
    )
    for entry_id in (*context_entries, "context_undp", "context_oif"):
        entry = data.reference.by_id(entry_id)
        context_items.append({
            "id": entry.id, "label": entry.label,
            "value": format_value(entry.value, entry.unit) if entry.value is not None else None,
            "unit": entry.unit, "status": "available" if entry.value is not None else "unavailable",
            "provider": "reference", "chip": _reference_chip(entry), "year": entry.year,
            "note": entry.caveat, "source": entry.source, "source_url": entry.source_url,
        })
    context_block = {
        "id": "exclusion_context", "kind": "reference_cards",
        "title": "Contexte vérifié",
        "subtitle": (
            "La pauvreté est un contexte INS 2021, pas une mesure d'exclusion bancaire."
            if iso3 == "TUN"
            else "Cadres analytiques internationaux, pas une mesure d'exclusion bancaire."
        ),
        "items": context_items, "payload": {},
    }
    ask_block = {
        "id": "ask_finova", "kind": "ask",
        "title": "Ask Finova",
        "subtitle": "Réponses déterministes, chiffres vérifiés dans les faits.",
        "items": [],
        "payload": {
            "suggestions": [
                "Pourquoi l'écart femmes-hommes est-il élevé ?",
                "Combien d'adultes ont un compte en Tunisie ?",
                "Les ATMs ont-ils augmenté depuis 2017 ?",
                "Que dit la pauvreté rurale ?",
            ],
            "endpoint": "/api/ask",
            "rules": [
                "Chaque chiffre de la réponse existe dans les faits du spec.",
                "Aucune recommandation n'est présentée comme une causalité.",
            ],
        },
    }
    pages.append({
        "id": "exclusion", "title": "Pourquoi l'exclusion ?",
        "subtitle": "Barrières, milieu de vie et lecture XAI (association, pas causalité).",
        "metrics": [urban, rural],
        "charts": [barrier_chart, urban_rural_chart],
        "insights": [],
        "blocks": [context_block, ask_block],
        "notices": [],
    })

    # --------------------------------------------------------------- poverty/SMIG
    poverty_available = iso3 == "TUN"
    poverty_page: dict[str, Any] = {
        "id": "poverty", "title": "Pauvreté & SMIG",
        "subtitle": "Contexte tunisien uniquement : SMIG, pauvreté INS 2021 et simulateur de frais.",
        "available": poverty_available,
        "unavailable_reason": None if poverty_available else (
            "Les références SMIG et pauvreté INS sont propres à la Tunisie : "
            "aucune valeur n'est affichée pour un autre pays."
        ),
        "metrics": [], "charts": [], "insights": [], "blocks": [], "notices": [],
    }
    if poverty_available:
        smig_entries = [data.reference.by_id(f"smig_{y}") for y in (2025, 2026, 2027, 2028)]
        smig_points = [
            {"year": entry.year, "value": entry.value, "status": "available",
             "reason": None}
            for entry in smig_entries
        ]
        smig_chart = {
            "id": "smig_trajectory", "kind": "line",
            "title": "SMIG 2025-2028 (40 h/semaine)",
            "subtitle": "Barème statique, revalorisations programmées — à confirmer au JORT.",
            "x_label": "Année", "y_label": "TND par mois", "unit": "TND_per_month",
            "series": [{
                "id": "smig", "label": "SMIG mensuel brut",
                "unit": "TND_per_month", "points": smig_points,
                "provider": "reference", "chip": _reference_chip(smig_entries[0]),
                "evidence_ids": tuple(f"REF-{entry.id}" for entry in smig_entries),
            }],
            "notes": ["Aucune projection n'est calculée au-delà du barème publié."],
        }
        poverty_metrics = [
            data.reference_metric("smig_2025", label="SMIG 2025"),
            data.reference_metric("smig_2028", label="SMIG 2028 (programmé)"),
            data.reference_metric("poverty_rate_2021"),
            data.reference_metric("poverty_rate_extreme_2021"),
        ]
        poverty_context = {
            "id": "poverty_context", "kind": "metric_strip",
            "title": "Contexte INS 2021",
            "subtitle": "Enquête nationale budget/consommation, seuil national.",
            "items": [{
                "id": entry_id,
                "label": data.reference.by_id(entry_id).label,
                "value": format_value(data.reference.by_id(entry_id).value, "percent"),
                "unit": "percent",
                "status": "available",
                "provider": "reference",
                "chip": _reference_chip(data.reference.by_id(entry_id)),
                "year": data.reference.by_id(entry_id).year,
                "note": data.reference.by_id(entry_id).caveat,
                "source": data.reference.by_id(entry_id).source,
                "source_url": data.reference.by_id(entry_id).source_url,
            } for entry_id in ("poverty_rate_2021", "poverty_rate_urban_2021",
                               "poverty_rate_rural_2021")],
            "payload": {},
        }
        simulator = {
            "id": "fee_simulator", "kind": "simulator",
            "title": "Simulateur de frais de compte",
            "subtitle": "Arithmétique côté client : un frais mensuel rapporté au SMIG.",
            "items": [],
            "payload": {
                "default_fee_tnd": 5.0,
                "smig_reference": {
                    "value": data.reference.by_id("smig_2025").value,
                    "year": 2025,
                    "source": data.reference.by_id("smig_2025").source,
                },
                "formula": "part_smig = frais_mensuel / SMIG_mensuel × 100",
                "rules": [
                    "Le frais saisi est une hypothèse illustrative, pas une donnée.",
                    "Le SMIG affiché est la référence statique 2025.",
                ],
            },
        }
        gdp = data.macro("gdp_pc", "usd_current_per_capita")
        fx_entry = data.reference.by_id("fx_tnd_usd_2024")
        income_items = [{
            "id": gdp["id"], "label": gdp["label"], "value": gdp["value"],
            "unit": gdp["unit"], "status": gdp["status"], "provider": "warehouse",
            "chip": gdp["chip"], "year": gdp["year"], "note": gdp["note"],
        }, {
            "id": fx_entry.id, "label": fx_entry.label,
            "value": format_value(fx_entry.value, fx_entry.unit),
            "unit": fx_entry.unit, "status": "available", "provider": "reference",
            "chip": _reference_chip(fx_entry), "year": fx_entry.year,
            "note": fx_entry.caveat, "source": fx_entry.source,
            "source_url": fx_entry.source_url,
        }]
        if (data.reader is not None and data.year == 2024 and fx_entry.value):
            point = data.reader.country_year_value("gdp_pc", iso3, 2024)
            if point["value"] is not None:
                magnitude = point["value"] * fx_entry.value / 12.0
                income_items.append({
                    "id": "derived_monthly_magnitude",
                    "label": "Ordre de grandeur mensuel (dérivé)",
                    "value": f"{magnitude:,.0f} TND/mois".replace(",", " "),
                    "unit": "TND_per_month", "status": "available",
                    "provider": "derived", "chip": _chip(
                        "derived", "Calcul BIFlow · dérivé", review=True,
                        reasons=("derived_value",),
                        note="PIB/hab × FX / 12 : ordre de grandeur, pas un revenu mesuré.",
                    ),
                    "year": 2024,
                    "note": "Dérivé = PIB par habitant × FX / 12; ne remplace pas une mesure de revenu.",
                })
        income_block = {
            "id": "income_context", "kind": "metric_strip",
            "title": "Contexte de revenu",
            "subtitle": "Grandeurs publiées, aucune promesse sur le revenu des ménages.",
            "items": income_items,
            "payload": {},
        }
        poverty_page.update({
            "metrics": poverty_metrics,
            "charts": [smig_chart],
            "blocks": [poverty_context, simulator, income_block],
        })

    pages.append(poverty_page)

    # ------------------------------------------------------------- data pipeline
    pipeline_payload = dict(pipeline or {})
    pipeline_blocks = []
    if pipeline_payload:
        route_items = []
        for group in ("route1", "route2"):
            for index, step in enumerate(pipeline_payload.get(group) or []):
                route_items.append({
                    "id": f"{group}-{step.get('id', index)}",
                    "label": step.get("label", step.get("id", "step")),
                    "value": step.get("status"),
                    "status": step.get("status"),
                    "provider": None,
                    "note": step.get("detail"),
                })
        pipeline_blocks.append({
            "id": "pipeline_diagram", "kind": "pipeline",
            "title": "Route 1 puis Route 2",
            "subtitle": "Quality PASS → ETL ; FAIL → arrêt et rapport d'erreur.",
            "items": route_items,
            "payload": pipeline_payload,
        })
    pages.append({
        "id": "pipeline", "title": "Données & pipeline",
        "subtitle": "Sources, qualité, dernier run et comptages réels du warehouse.",
        "metrics": [], "charts": [], "insights": [],
        "blocks": pipeline_blocks, "notices": [],
    })

    # -------------------------------------- années sans enquête / graphiques vides
    survey_present = any(
        row.get("availability_status") == "available"
        for row in dataset.get("observations") or []
        if row.get("iso3") == iso3 and row.get("source") == "findex"
    )
    survey_reason = (
        f"Aucune enquête Findex pour {year} : l'enquête est menée par vagues "
        "(2011, 2014, 2017, 2021, 2024). Les indicateurs bancaires annuels restent "
        "disponibles sur la page Accès et crédit."
    )
    for page in pages:
        page["charts"] = [
            chart for chart in page.get("charts", []) if _chart_buildable(chart)
        ]
        if page["id"] in ("inclusion", "exclusion") and not survey_present:
            page.update({
                "available": False,
                "unavailable_reason": survey_reason,
                "metrics": [], "charts": [], "insights": [], "xai": None,
            })
        elif page["id"] == "overview" and not survey_present:
            page.setdefault("notices", []).append({
                "code": "survey_absent", "severity": "info", "kpi_id": None,
                "message": survey_reason,
            })

    # -------------------------------------------------------------------- notices
    notices: list[dict[str, Any]] = []
    for notice in dataset.get("notices") or []:
        notices.append({
            "code": notice.get("code", "dataset_notice"),
            "severity": notice.get("severity", "info"),
            "message": notice.get("message", ""),
            "kpi_id": notice.get("kpi_id"),
        })
    # Notices dependant du backend : affichees seulement si elles restent vraies
    if FIN24AP_MISLABELED:
        notices.append(
            {"code": "fin24aP_definition", "severity": "warning", "kpi_id": "emergency_money",
             "message": (
                 "fin24aP : le dictionnaire l'appelle « Paiement numerique » alors que la "
                 "définition Findex 2025 attendue est « could obtain emergency money ». "
                 "La valeur brute est affichée avec un badge de revue, sans validation."
             )})
    catalog_codes = {(k.get("warehouse") or {}).get("indicator_code")
                     for k in (data.catalog.get("kpis") or {}).values()}
    outside = [name for name, codes in (
        ("ATM", ("atm_density",)), ("dépôts/crédits", ("deposits_pct_gdp", "loans_pct_gdp")),
        ("fin17a", ("fin17a",)), ("fin22a", ("fin22a",)), ("fin24aP", ("fin24aP",)),
    ) if not set(codes) & catalog_codes]
    if outside:
        listed = ", ".join(outside[:-1]) + f" et {outside[-1]}" if len(outside) > 1 else outside[0]
        notices.append(
            {"code": "warehouse_not_in_catalog", "severity": "review", "kpi_id": None,
             "message": (
                 f"Les séries {listed} viennent du "
                 "warehouse et ne sont pas encore dans le catalogue KPI : revue requise."
             )})
    if dataset.get("publication_status", "not_evaluated") == "not_evaluated":
        notices.append(
            {"code": "publication_not_evaluated", "severity": "review", "kpi_id": None,
             "message": "Aucune donnée n'est approuvée pour publication : statut not_evaluated."})
    for series_id in ("loans_pct_gdp", "deposits_pct_gdp"):
        if (iso3, series_id) in data.observations:
            point = data.semantic_metric(series_id, upto=True, previous=False)
            if point["status"] == "available":
                notices.append({
                    "code": f"{series_id}_now_available", "severity": "info",
                    "kpi_id": series_id,
                    "message": (
                        f"{series_id} est désormais disponible dans le warehouse "
                        f"reconstruit ({point['year']}). Le plan prévoyait « To load » : "
                        "la valeur réelle est affichée à la place, avec sa provenance."
                    ),
                })
    if iso3 != "TUN":
        notices.append({
            "code": "tunisia_only_reference", "severity": "info", "kpi_id": None,
            "message": "SMIG, pauvreté INS et simulateur sont propres à la Tunisie.",
        })

    # --------------------------------------------------------------- provenance
    provenance = {
        "dataset_generated_at": dataset.get("generated_at"),
        "dataset_provenance": dataset.get("provenance"),
        "catalog": dataset.get("catalog"),
        "publication_status": dataset.get("publication_status"),
        "reference": _reference_catalog_meta(data.reference),
        "warehouse_summary": data.reader.summary() if data.reader is not None else None,
    }
    return {
        "generated_at": dataset.get("generated_at"),
        "country": {
            "iso3": iso3,
            "name": COUNTRY_LABELS.get(iso3, country.get("name", iso3)),
            "region": country.get("region"), "income_group": country.get("income_group"),
        },
        "year": year,
        "pages": pages,
        "notices": notices,
        "provenance": provenance,
    }


def build_spec_blocks(
    dataset: Mapping[str, Any], *, reader: WarehouseReader | None,
    reference: ReferenceCatalog, iso3: str, year: int,
    history: Mapping[str, Any] | None = None,
    pipeline: Mapping[str, Any] | None = None,
    catalog: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    data = _Data(dataset, reader, reference, catalog or load_catalog(), iso3, year)
    return _build_blocks(data, dataset, history=history, pipeline=pipeline)


# -------------------------------------------------------------------- fact export
def _display_number(text: Any) -> float | None:
    if not isinstance(text, str):
        return None
    match = re.search(r"\d[\d \u00a0\u202f]*(?:[.,]\d+)?", text)
    if match is None:
        return None
    try:
        return float(
            match.group(0).replace(" ", "").replace("\u00a0", "")
            .replace("\u202f", "").replace(",", ".")
        )
    except ValueError:
        return None


def _gap_fact(dimension: str, title: str, value: float, year: int, iso3: str,
              evidence: Sequence[str], *, label: str, display: str) -> dict[str, Any]:
    """Ecart entre deux groupes : fait semantique s'il est lu dans un KPI d'ecart du
    catalogue (preuve unique), sinon derive des deux sous-groupes cites."""
    stored = f"EV-{GAP_KPIS[dimension]}-{iso3}-{year}" if dimension in GAP_KPIS else None
    semantic = stored is not None and stored in evidence
    return {
        "id": f"F-gap-{dimension}-{iso3}-{year}",
        "code": f"gap_{dimension}",
        "label": label,
        "value": value, "unit": "percentage_points",
        "year": year, "iso3": iso3,
        "provider": "semantic" if semantic else "derived",
        "display": display,
        "evidence_ids": (stored,) if semantic else tuple(evidence),
    }


def _baseline_evidence(metric: Mapping[str, Any]) -> tuple[str, ...]:
    """Preuve de l'annee de base d'une variation semantique (EV-<kpi>-<iso3>-<annee>)."""
    delta = metric.get("delta")
    evidence = tuple(metric.get("evidence_ids") or ())
    if metric.get("provider") != "semantic" or delta is None or len(evidence) != 1:
        return ()
    return (f"{evidence[0].rsplit('-', 1)[0]}-{delta['from_year']}",)


def baseline_facts(blocks: Mapping[str, Any], dataset: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Observation de l'annee de base de chaque variation semantique, lue telle quelle
    dans la serie du dataset (aucun calcul) : la variation reste verifiable."""
    points = {
        point.get("evidence_id"): (row, point)
        for row in dataset.get("series") or []
        for point in row.get("points") or []
        if point.get("evidence_id")
    }
    facts = []
    for page in blocks["pages"]:
        for metric in page["metrics"]:
            for evidence in _baseline_evidence(metric):
                row, point = points.get(evidence, (None, None))
                if point is None or point.get("availability_status") != "available" or point.get("value") is None:
                    continue
                facts.append({
                    "id": f"F-{row['kpi_id']}-{row['iso3']}-{point['year']}",
                    "code": row["kpi_id"],
                    "label": metric["label"],
                    "value": float(point["value"]), "unit": metric["unit"],
                    "year": int(point["year"]), "iso3": row["iso3"],
                    "provider": "semantic",
                    "display": format_value(float(point["value"]), metric["unit"]),
                    "evidence_ids": (evidence,),
                })
    return facts


def extract_facts(blocks: Mapping[str, Any], *, iso3: str, year: int) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    for page in blocks["pages"]:
        for metric in page["metrics"]:
            if metric["status"] == "placeholder":
                continue
            facts.append(_fact(metric))
            delta = metric.get("delta")
            if delta is not None:
                facts.append({
                    "id": f"F-{metric['id']}-delta-{metric.get('iso3') or iso3}-{delta['to_year']}",
                    "code": f"{metric['id']}_delta",
                    "label": f"Variation — {metric['label']}",
                    "value": delta["value"], "unit": delta["unit"],
                    "year": delta["to_year"], "iso3": metric.get("iso3") or iso3,
                    "provider": "derived", "display": delta["label"],
                    # une variation cite les deux annees comparees
                    "evidence_ids": (*(metric.get("evidence_ids") or ()),
                                     *_baseline_evidence(metric)),
                })
        for chart in page["charts"]:
            if chart["kind"] == "bar":
                for bar in chart["bars"]:
                    if bar["status"] == "placeholder":
                        continue
                    if bar.get("evidence_ids"):
                        code = bar.get("id") or f"{chart['id']}-{_slug(bar['label'])}"
                        facts.append(_fact(
                            bar, code=code, unit=chart.get("unit"),
                            iso3=bar.get("iso3") or iso3,
                        ))
            if chart["kind"] == "funnel":
                for step in chart["steps"]:
                    if step["status"] == "placeholder" or step["value"] is None:
                        continue
                    facts.append(_fact(
                        step, code=step["id"], iso3=iso3,
                        unit=chart.get("unit"),
                    ))
            if chart["kind"] == "dumbbell":
                for group in chart["groups"]:
                    spec = next(s for s in DIMENSION_SPECS if s[0] == group["dimension"])
                    for row in group["rows"]:
                        for side_key, group_key in (("left", spec[2]), ("right", spec[3])):
                            side = row[side_key]
                            if side["value"] is None:
                                continue
                            # preuve propre a chaque cote : le KPI du sous-groupe
                            evidence = f"EV-{SUBGROUP_KPI[(group['dimension'], group_key)]}-{iso3}-{row['year']}"
                            facts.append({
                                "id": f"F-{group['dimension']}-{_slug(side['label'])}-{iso3}-{row['year']}",
                                "code": f"{group['dimension']}_{_slug(side['label'])}",
                                "label": f"Compte — {group['title']} : {side['label']}",
                                "value": side["value"], "unit": "percent",
                                "year": row["year"], "iso3": iso3,
                                "provider": row.get("provider", "warehouse"), "display": side["display"],
                                "evidence_ids": (evidence,) if evidence in row["evidence_ids"]
                                else row["evidence_ids"],
                            })
                        if row["gap_pp"] is not None:
                            facts.append(_gap_fact(group["dimension"], group["title"], row["gap_pp"],
                                                   row["year"], iso3, row["evidence_ids"],
                                                   label=f"Écart de compte — {group['title']}",
                                                   display=f"{row['gap_pp']:+.1f} pt"))
            if chart["kind"] == "gap":
                for point in chart["gap_points"]:
                    for year, value in ((point["from_year"], point["gap_from_pp"]),
                                        (point["to_year"], point["gap_to_pp"])):
                        if value is None:
                            continue
                        dimension = point["id"].removeprefix("gap-")
                        facts.append(_gap_fact(
                            dimension, point["label"], value, year, iso3,
                            tuple(e for e in point["evidence_ids"] if e.endswith(f"-{year}")),
                            label=f"Écart — {point['label']}", display=f"{value:.1f} pt"))
                    if point["change_pp"] is None:
                        continue
                    facts.append({
                        "id": f"F-gapchange-{dimension}-{iso3}",
                        "code": f"gap_change_{dimension}",
                        "label": f"Variation de l'écart — {point['label']}",
                        "value": point["change_pp"], "unit": "percentage_points",
                        "year": point["to_year"], "iso3": iso3,
                        "provider": "derived",
                        "display": f"{point['change_pp']:+.1f} pt",
                        "evidence_ids": point["evidence_ids"],
                    })
            if chart["kind"] == "heatmap" and chart["id"] == "barriers_heatmap":
                # colonne 1 : KPI du pays ; colonne 2 : ligne PEERS de kpi_values
                for cell in chart["cells"]:
                    if cell["status"] != "available" or cell["value"] is None:
                        continue
                    peers = cell["column"] == chart["columns"][1]
                    owner = "PEERS" if peers else iso3
                    kpi_id = BARRIER_KPI[cell["row"]]
                    facts.append({
                        "id": f"F-{kpi_id}-{owner}-{year}", "code": kpi_id,
                        "label": f"{label_for(cell['row'])} — {cell['column']}",
                        "value": cell["value"], "unit": "percent", "year": year,
                        "iso3": owner, "provider": "semantic", "display": cell["display"],
                        "evidence_ids": (f"EV-{kpi_id}-{owner}-{year}",),
                    })
            if chart["kind"] == "line" and chart.get("unit") == "index_2017_100":
                for series in chart["series"]:
                    last = next((point for point in reversed(series["points"])
                                 if point["value"] is not None), None)
                    if last is None:
                        continue
                    facts.append({
                        "id": f"F-index-{series['id']}-{iso3}-{last['year']}",
                        "code": series["id"],
                        "label": f"Indice — {series['label']} (2017 = 100)",
                        "value": last["value"], "unit": "index_2017_100",
                        "year": last["year"], "iso3": iso3,
                        "provider": "derived", "display": f"{last['value']:.1f}",
                        "evidence_ids": series.get("evidence_ids") or (),
                    })
        for block in page.get("blocks") or ():
            if block.get("kind") not in ("metric_strip", "reference_cards"):
                continue
            for item in block.get("items") or ():
                provider = item.get("provider")
                if item.get("status") != "available" or provider not in (
                        "reference", "warehouse", "derived"):
                    continue
                value = _display_number(item.get("value"))
                if value is None:
                    continue
                code = item.get("id") or _slug(str(item.get("label") or "item"))
                item_year = item.get("year")
                item_iso = iso3 if provider == "warehouse" else None
                facts.append({
                    "id": f"F-{code}-{item_iso or 'REF'}-{item_year or 'NA'}",
                    "code": code,
                    "label": item.get("label") or code,
                    "value": value,
                    "unit": item.get("unit"),
                    "year": item_year,
                    "iso3": item_iso,
                    "provider": provider,
                    "display": str(item.get("value")),
                    "evidence_ids": (f"REF-{code}",) if provider == "reference" else (),
                })
    return _unique_facts(facts)


# --------------------------------------------------------------------- assemble
def finalize_spec(
    blocks: Mapping[str, Any], *, facts: Sequence[Mapping[str, Any]],
    run_id: str, years: Sequence[int], countries: Sequence[Mapping[str, Any]],
    insights: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    xai: Mapping[str, Any] | None = None,
    extra_notices: Sequence[Mapping[str, Any]] = (),
) -> DashboardSpec:
    """Attach analyst output then validate the whole contract (fail closed)."""
    facts_json = _unique_facts([{**dict(fact)} for fact in facts])
    insights = insights or {}
    pages = []
    for page in blocks["pages"]:
        page = dict(page)
        page["insights"] = [dict(item) for item in insights.get(page["id"], [])]
        if page["id"] == "exclusion" and xai is not None:
            page["xai"] = dict(xai)
        if page.get("changes") is None:
            page.pop("changes", None)
        pages.append(page)
    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": blocks["generated_at"],
        "run_id": run_id,
        "country": blocks["country"],
        "year": blocks["year"],
        "years": tuple(sorted(set(years))),
        "countries_available": [dict(item) for item in countries],
        "pages": pages,
        "facts": facts_json,
        "notices": [dict(item) for item in (*blocks["notices"], *extra_notices)],
        "provenance": blocks["provenance"],
        "reference": blocks["provenance"]["reference"],
        # statut fixe par l'Auditor (kpi_values) ; not_evaluated sans audit
        "publication_status": blocks["provenance"].get("publication_status") or "not_evaluated",
    }
    return DashboardSpec.model_validate(data)


def validate_spec(data: Any) -> DashboardSpec:
    return DashboardSpec.model_validate(data)


# ------------------------------------------------------------------------ history
SNAPSHOT_METRICS = (
    "account_ownership", "digital_payment_rate", "saving_rate", "emergency_money",
    "atm_per_100k", "branch_density", "depositors_per_1k", "borrowers_per_1k",
    "loans_pct_gdp", "deposits_pct_gdp", "urban_account", "rural_account",
)


def snapshot_from_spec(spec: DashboardSpec | Mapping[str, Any]) -> dict[str, Any]:
    spec = spec if isinstance(spec, DashboardSpec) else DashboardSpec.model_validate(spec)
    metrics = {}
    for page in spec.pages:
        for metric in page.metrics:
            metrics[metric.id] = {
                "label": metric.label, "value": metric.value, "unit": metric.unit,
                "year": metric.year, "status": metric.status,
                "provider": metric.provider,
            }
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": spec.run_id,
        "generated_at": spec.generated_at,
        "iso3": spec.country.iso3,
        "year": spec.year,
        "metrics": {key: metrics[key] for key in metrics if key in SNAPSHOT_METRICS},
    }


def diff_snapshots(
    current: DashboardSpec | Mapping[str, Any],
    previous: Mapping[str, Any] | None,
) -> SnapshotDiff:
    spec = current if isinstance(current, DashboardSpec) else DashboardSpec.model_validate(current)
    snapshot = snapshot_from_spec(spec)
    if not previous or previous.get("iso3") != snapshot["iso3"]:
        return SnapshotDiff(available=False)
    previous_metrics = previous.get("metrics") or {}
    items = []
    for metric_id, metric in snapshot["metrics"].items():
        before = previous_metrics.get(metric_id)
        if before is None:
            items.append({
                "metric_id": metric_id, "label": metric["label"],
                "previous_value": None, "current_value": metric["value"],
                "delta": None, "unit": metric["unit"], "status": "new",
            })
            continue
        current_value = metric["value"]
        previous_value = before.get("value")
        if current_value is None or previous_value is None:
            items.append({
                "metric_id": metric_id, "label": metric["label"],
                "previous_value": previous_value, "current_value": current_value,
                "delta": None, "unit": metric["unit"], "status": "unavailable",
            })
            continue
        delta = float(current_value) - float(previous_value)
        if abs(delta) < 1e-9:
            status = "stable"
        else:
            status = "changed"
        items.append({
            "metric_id": metric_id, "label": metric["label"],
            "previous_value": float(previous_value), "current_value": float(current_value),
            "delta": delta, "unit": metric["unit"], "status": status,
        })
    return SnapshotDiff(
        available=True, previous_run_id=previous.get("run_id"),
        previous_generated_at=previous.get("generated_at"),
        items=tuple(items),
    )


# ------------------------------------------------------------------------ pipeline
def load_pipeline_info(
    cfg: Mapping[str, Any], *, reader: WarehouseReader | None,
    lineage_path: str | Path, quality_report_path: str | Path,
    reports_dir: str | Path, history_files: Sequence[Path] = (),
) -> dict[str, Any]:
    """Assemble the Data & Pipeline payload from real artefacts only."""

    def read_json(path: str | Path) -> dict[str, Any]:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    lineage = read_json(lineage_path)
    quality = read_json(quality_report_path)
    threshold = (cfg.get("quality") or {}).get("score_threshold")
    sources = []
    for name, item in (lineage.get("inputs") or {}).items():
        raw_path = resolve(item.get("path", ""))
        digest = None
        match = None
        if raw_path.is_file():
            digest = sha256_file(raw_path)
            companion = raw_path.with_name(raw_path.name + ".sha256")
            if companion.is_file():
                expected = companion.read_text(encoding="utf-8").split()[0].strip()
                match = expected == digest
        sources.append({
            "name": name,
            "path": item.get("path"),
            "rows": item.get("rows"),
            "sha256": digest,
            "sha256_match": match,
            "collected_at": (
                datetime.fromtimestamp(raw_path.stat().st_mtime).isoformat(
                    timespec="seconds")
                if raw_path.is_file() else None
            ),
            "rejected": item.get("rejected") or {},
        })
    checks = [
        {
            "source": name, "rows": check.get("rows"), "cols": check.get("cols"),
            "score": check.get("score"), "gate": check.get("gate"),
        }
        for name, check in (quality.get("checks") or {}).items()
    ]
    history = []
    for path in history_files:
        snap = read_json(path)
        if snap:
            history.append({
                "run_id": snap.get("run_id"), "generated_at": snap.get("generated_at"),
                "iso3": snap.get("iso3"), "year": snap.get("year"),
                "file": path.name,
            })
    reports = sorted(
        (item.name for item in Path(reports_dir).glob("*") if item.is_dir()),
        reverse=True,
    )[:5]
    summary = reader.summary() if reader is not None else {}
    return {
        "route1": [
            {"id": "collector", "label": "Collector", "status": "done",
             "detail": "Sources Findex/FAS statiques, WDI hashée."},
            {"id": "profiler", "label": "Profiler", "status": "done",
             "detail": "Profilage et métadonnées des sources."},
            {"id": "quality", "label": "Quality gate", "status":
             "passed" if quality.get("passed") else "failed",
             "detail": f"Seuil {threshold} · score {quality.get('overall_score')}"},
            {"id": "etl", "label": "ETL", "status":
             "done" if quality.get("passed") else "skipped",
             "detail": "Warehouse DuckDB (fact, country_year, dimensions)."},
        ],
        "route2": [
            {"id": "semantic_kpi", "label": "Semantic / KPI", "status": "done",
             "detail": "6 KPI du catalogue, calcul déterministe."},
            {"id": "analyst", "label": "Analyst", "status": "done",
             "detail": "Faits déterministes, insight et carte XAI."},
            {"id": "dashboard", "label": "Dashboard", "status": "done",
             "detail": "Contrat de données version 2.0."},
            {"id": "xai", "label": "XAI", "status": "out_of_scope",
             "detail": "Carte XAI déterministe incluse; moteur XAI avancé hors périmètre."},
        ],
        "gate": {
            "passed": bool(quality.get("passed")),
            "score": quality.get("overall_score"),
            "threshold": threshold,
            "critical_issues": quality.get("critical_issues"),
        },
        "sources": sources,
        "quality": {
            "run_id": quality.get("run_id"),
            "score": quality.get("overall_score"),
            "passed": quality.get("passed"),
            "checks": checks,
        },
        "warehouse": {
            "path": str(getattr(reader, "path", None)) if reader is not None else None,
            "fact_rows": summary.get("fact_rows"),
            "countries": summary.get("countries"),
            "by_source": summary.get("by_source"),
            "sha256": lineage.get("outputs", {}).get("warehouse_sha256"),
        },
        "last_run": {
            "run_id": lineage.get("run_id"),
            "created_at": lineage.get("created_at"),
            "period": lineage.get("period"),
        },
        "reports": reports,
        "history": history,
        "transforms": lineage.get("transforms") or [],
        "checks": lineage.get("checks") or {},
    }


# --------------------------------------------------------------------- entrypoint
def build_finova_spec(
    dataset: Mapping[str, Any], *, run_id: str, iso3: str | None = None,
    year: int | None = None, reader: WarehouseReader | None = None,
    reference: ReferenceCatalog | str | Path | None = None,
    history: Mapping[str, Any] | None = None,
    pipeline: Mapping[str, Any] | None = None,
    insights: Mapping[str, Sequence[Mapping[str, Any]]] | None = None,
    xai: Mapping[str, Any] | None = None,
    years: Sequence[int] | None = None,
    catalog: Mapping[str, Any] | None = None,
) -> DashboardSpec:
    reference = reference or load_reference()
    if isinstance(reference, (str, Path)):
        reference = load_reference(reference)
    iso3 = iso3 or (dataset.get("scope", {}).get("countries") or [{}])[0].get(
        "iso3", PRIMARY_COUNTRY)
    spec_year = year or int(dataset["scope"].get("year") or 0)
    if not spec_year:
        observation = next(
            (row for row in dataset.get("observations") or []
             if row.get("iso3") == iso3 and row.get("value") is not None),
            None,
        )
        spec_year = int(observation["year"]) if observation else 0
    if not spec_year:
        raise ValueError("cannot infer the dashboard year from the dataset")
    blocks = build_spec_blocks(
        dataset, reader=reader, reference=reference, iso3=iso3, year=spec_year,
        history=history, pipeline=pipeline, catalog=catalog,
    )
    facts = extract_facts(blocks, iso3=iso3, year=spec_year) + baseline_facts(blocks, dataset)
    known_years = sorted({
        point["year"]
        for row in dataset.get("series") or []
        if row.get("iso3") == iso3
        for point in row.get("points") or []
        if point.get("availability_status") == "available"
    })
    countries = [
        {"iso3": item["iso3"],
         "name": COUNTRY_LABELS.get(item["iso3"], item.get("name", item["iso3"])),
         "region": item.get("region"), "income_group": item.get("income_group")}
        for item in dataset.get("scope", {}).get("countries") or []
    ]
    return finalize_spec(
        blocks, facts=facts, run_id=run_id,
        years=years or known_years or [spec_year], countries=countries,
        insights=insights, xai=xai,
    )


__all__ = [
    "DashboardSpec",
    "Fact",
    "Insight",
    "Metric",
    "PAGE_IDS",
    "PEERS",
    "REFERENCE_PATH",
    "ReferenceCatalog",
    "SCHEMA_VERSION",
    "build_finova_spec",
    "build_spec_blocks",
    "diff_snapshots",
    "extract_facts",
    "finalize_spec",
    "format_value",
    "load_pipeline_info",
    "load_reference",
    "snapshot_from_spec",
    "validate_spec",
]
