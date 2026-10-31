"""Renderer-agnostic dashboard contract consumed by the React front end.

The dashboard never computes a value: cards, series, rankings and comparisons
are copied from the deterministic analysis dataset. Validation rejects non
finite numbers and inconsistent availability, so a missing observation can
never be rendered as zero.
"""
from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

from biflow.config import resolve
from biflow.utils.io import save_json

SCHEMA_VERSION = "1.0"
REQUIRED_KEYS = (
    "cards", "series", "rankings", "comparisons", "table", "insights", "notices",
)


def _indexes(dataset: dict[str, Any]):
    kpis = {item["kpi_id"]: item for item in dataset["scope"]["kpis"]}
    countries = {item["iso3"]: item for item in dataset["scope"]["countries"]}
    return kpis, countries


def build_dashboard_data(
    dataset: dict[str, Any],
    *,
    run_id: str,
    analyst_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    kpis, countries = _indexes(dataset)
    cards: list[dict[str, Any]] = []
    table: list[dict[str, Any]] = []
    for observation in dataset["observations"]:
        kpi = kpis[observation["kpi_id"]]
        country = countries[observation["iso3"]]
        card = {
            "kpi_id": observation["kpi_id"],
            "kpi_name": kpi["name"],
            "iso3": observation["iso3"],
            "country_name": country["name"],
            "region": country["region"],
            "income_group": country["income_group"],
            "year": observation["year"],
            "value": observation["value"],
            "unit": observation["unit"],
            "availability_status": observation["availability_status"],
            "reason": observation["reason"],
            "definition_status": observation["definition_status"],
            "requires_review": observation["requires_review"],
            "review_reasons": list(observation["review_reasons"]),
            "evidence_id": observation["evidence_id"],
        }
        cards.append(card)
        table.append({
            **card,
            "selection": observation["selection"],
            "source": observation["source"],
            "indicator_code": observation["indicator_code"],
        })

    insights = []
    if analyst_report:
        insights = [
            {
                "id": finding.get("id"),
                "code": finding.get("code"),
                "statement": finding.get("statement"),
                "severity": finding.get("severity"),
                "evidence_ids": list(finding.get("evidence_ids") or []),
            }
            for finding in analyst_report.get("findings") or []
        ]

    data = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dataset["generated_at"],
        "run_id": run_id,
        "catalog": dataset["catalog"],
        "scope": dataset["scope"],
        "provenance": dataset["provenance"],
        "cards": cards,
        "table": table,
        "series": dataset["series"],
        "rankings": dataset["rankings"],
        "comparisons": dataset["comparisons"],
        "insights": insights,
        "notices": dataset["notices"],
        "summary": analyst_report.get("summary") if analyst_report else None,
        "limitations": list(analyst_report.get("limitations") or []) if analyst_report else [],
        "publication_status": dataset["publication_status"],
    }
    return validate_dashboard_data(data)


def validate_dashboard_data(data: Any) -> dict[str, Any]:
    """Fail fast on a contract violation; never repair or coerce values."""
    if not isinstance(data, dict):
        raise ValueError("dashboard data must be an object")
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported dashboard schema_version")
    for key in REQUIRED_KEYS:
        if not isinstance(data.get(key), list):
            raise ValueError(f"dashboard field must be a list: {key}")
    evidence: list[str] = []
    for card in data["cards"]:
        if not isinstance(card, dict):
            raise ValueError("dashboard card must be an object")
        if card.get("availability_status") == "available" and not isinstance(
            card.get("value"), (int, float)
        ):
            raise ValueError("available card without a numeric value")
        value = card.get("value")
        if value is not None and not math.isfinite(value):
            raise ValueError("dashboard value must be finite or null")
        if card.get("availability_status") != "available" and value is not None:
            raise ValueError("unavailable card must keep a null value")
        evidence.append(card["evidence_id"])
    if len(evidence) != len(set(evidence)):
        raise ValueError("duplicate evidence_id in dashboard cards")
    return data


def export_dashboard_json(data: dict[str, Any], path: str | Path) -> Path:
    """Atomic export so the React app never reads a half-written file."""
    out = resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    temporary = out.with_name(out.name + ".tmp")
    save_json(data, temporary)
    for attempt in range(4):
        try:
            temporary.replace(out)
            return out
        except PermissionError:
            if attempt == 3:
                # Windows readers (Vite, browser) can hold the target without
                # delete sharing: overwrite in place rather than fail the run.
                out.write_bytes(temporary.read_bytes())
                temporary.unlink(missing_ok=True)
                return out
            time.sleep(0.05 * (attempt + 1))
    return out


__all__ = [
    "SCHEMA_VERSION",
    "build_dashboard_data",
    "export_dashboard_json",
    "validate_dashboard_data",
]
