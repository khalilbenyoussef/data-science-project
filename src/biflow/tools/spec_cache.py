"""Generated Finova scopes and their disk cache, shared by the API and Route 2.

A scope (country, year) not covered by the published contract is built from the
warehouse with the same deterministic builders (no LLM). The cache file name
carries the warehouse modification time: a rebuild invalidates every entry.
``pregenerate`` fills that same cache right after a Route 2 publication.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from biflow.agents.analyst import build_insights, build_xai
from biflow.tools.analysis import DEFAULT_KPIS, AnalysisRequest, AnalysisService
from biflow.tools.dashboard_spec import (
    DashboardSpec, PEERS, build_finova_spec, load_pipeline_info, load_reference,
)
from biflow.tools.kpi import DEFAULT_CATALOG
from biflow.tools.warehouse_reader import WarehouseReader

SpecBuilder = Callable[[str, int], dict[str, Any]]
DEFAULT_GENERATED_DIR = "outputs/dashboard/generated"


def attach_analysis(payload: Mapping[str, Any], insights: Mapping[str, Any],
                    xai: Mapping[str, Any] | None) -> dict[str, Any]:
    data = dict(payload)
    data["pages"] = [dict(page) for page in payload.get("pages") or []]
    for page in data["pages"]:
        page["insights"] = [dict(item) for item in insights.get(page.get("id"), [])]
        if page.get("id") == "exclusion":
            if xai is not None:
                page["xai"] = dict(xai)
            else:
                page.pop("xai", None)
    return DashboardSpec.model_validate(data).model_dump(mode="json")


def warehouse_stamp(warehouse: Path) -> float:
    try:
        return warehouse.stat().st_mtime
    except OSError:
        return 0.0


def generated_path(root: Path, iso3: str, year: int, stamp: float) -> Path:
    return root / f"{iso3}_{year}_{int(stamp)}.json"


def store_generated(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, path)
    except (OSError, ValueError):
        logging.getLogger(__name__).warning(
            "cache disque non écrit : %s", path, exc_info=True,
        )


class WarehouseSpecBuilder:
    """Deterministic on-demand spec for a scope not covered by the public file."""

    def __init__(
        self, cfg: Mapping[str, Any], *, warehouse: Path, lineage: Path,
        quality: Path, reference: Path, reports: Path, history_dir: Path,
        catalog_path: str | Path = DEFAULT_CATALOG,
    ) -> None:
        self.cfg = cfg
        self.warehouse = warehouse
        self.lineage = lineage
        self.quality = quality
        self.reference = reference
        self.reports = reports
        self.history_dir = history_dir
        self.catalog_path = catalog_path
        self._lock = threading.Lock()
        self._service: AnalysisService | None = None
        self._service_stamp = 0.0
        self._pipeline: tuple[float, dict[str, Any]] | None = None
        self._reference_catalog: tuple[float, Any] | None = None

    def _pipeline_for(self, reader: WarehouseReader, stamp: float) -> dict[str, Any]:
        if self._pipeline is None or self._pipeline[0] != stamp:
            history_files = sorted(
                [path for path in self.history_dir.glob("*.json")
                 if path.is_file()],
                key=lambda path: path.stat().st_mtime, reverse=True,
            )[:20]
            self._pipeline = (stamp, load_pipeline_info(
                self.cfg, reader=reader, lineage_path=self.lineage,
                quality_report_path=self.quality, reports_dir=self.reports,
                history_files=history_files,
            ))
        return self._pipeline[1]

    def _reference_for(self, stamp: float) -> Any:
        if self._reference_catalog is None or self._reference_catalog[0] != stamp:
            self._reference_catalog = (stamp, load_reference(self.reference))
        return self._reference_catalog[1]

    def __call__(self, iso3: str, year: int) -> dict[str, Any]:
        if not self.warehouse.is_file():
            raise FileNotFoundError(f"warehouse introuvable : {self.warehouse}")
        with self._lock:
            stamp = self.warehouse.stat().st_mtime
            if self._service is None or self._service_stamp != stamp:
                self._service = AnalysisService(
                    self.warehouse, self.catalog_path, lineage_path=self.lineage,
                    quality_report_path=self.quality,
                )
                self._service_stamp = stamp
                self._pipeline = None
                self._reference_catalog = None
            request = AnalysisRequest(
                iso3=(iso3, *(code for code in PEERS if code != iso3)),
                kpi_ids=DEFAULT_KPIS, mode="year", year=year,
                series_iso3=(iso3,), include_trends=False,
                include_rankings=False, include_comparisons=False,
            )
            dataset = self._service.build(request)
            reader = WarehouseReader(self.warehouse)
            pipeline = self._pipeline_for(reader, stamp)
            reference = self._reference_for(stamp)
            spec = build_finova_spec(
                dataset, run_id=f"api_{iso3}_{year}", iso3=iso3, year=year,
                reader=reader, reference=reference, pipeline=pipeline,
            )
        facts = [fact.model_dump(mode="json") for fact in spec.facts]
        insights, _ = build_insights(facts, spec.country.name)
        xai, _ = build_xai(facts, spec.country.name)
        return attach_analysis(
            spec.model_dump(mode="json"), insights, xai,
        )


def pregenerate(builder: SpecBuilder, root: Path, warehouse: Path,
                scopes: Iterable[tuple[str, int]]) -> list[dict[str, Any]]:
    """Ecrit dans le cache disque chaque scope absent ; un echec n'arrete pas les
    autres. Renvoie {iso3, year, status, seconds, path} par scope."""
    stamp = warehouse_stamp(warehouse)
    results = []
    for iso3, year in scopes:
        path = generated_path(root, iso3, year, stamp)
        started = time.perf_counter()
        if path.is_file():
            status = "cached"
        else:
            try:
                store_generated(path, builder(iso3, year))
                status = "generated" if path.is_file() else "failed: cache non écrit"
            except Exception as exc:  # noqa: BLE001 - one scope never blocks the others
                status = f"failed: {type(exc).__name__}: {exc}"
        results.append({"iso3": iso3, "year": year, "status": status, "path": str(path),
                        "seconds": round(time.perf_counter() - started, 3)})
    return results


__all__ = [
    "DEFAULT_GENERATED_DIR", "SpecBuilder", "WarehouseSpecBuilder", "attach_analysis",
    "generated_path", "pregenerate", "store_generated", "warehouse_stamp",
]
