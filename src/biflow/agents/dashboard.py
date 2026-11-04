"""Dashboard agents for Route 2.

``DashboardAgent`` exports the legacy dashboard contract. ``DashboardSpecAgent``
exports the Finova contract v2.0: it never renders charts, never computes a KPI
and never approves publication. It reads the analysis dataset, the read-only
warehouse and the static reference, then writes one validated JSON spec to the
reports, the public front-end path and the history folder.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from biflow.agents.base import BaseAgent
from biflow.config import path_of, resolve
from biflow.tools.analysis import AnalysisRequest, AnalysisService, build_with_findex_wave
from biflow.tools.dashboard_contract import build_dashboard_data, export_dashboard_json
from biflow.tools.dashboard_spec import (
    PEERS, PRIMARY_COUNTRY, REFERENCE_PATH, build_finova_spec,
    diff_snapshots, load_pipeline_info, load_reference, snapshot_from_spec,
)
from biflow.tools.kpi import DEFAULT_CATALOG
from biflow.tools.warehouse_reader import WarehouseReader
from biflow.utils.io import load_json, save_json


class DashboardAgent(BaseAgent):
    name = "dashboard"

    def __init__(
        self,
        cfg: dict[str, Any] | None = None,
        run_id: str | None = None,
        log=None,
        *,
        warehouse_path: str | Path | None = None,
        catalog_path: str | Path = DEFAULT_CATALOG,
        lineage_path: str | Path | None = None,
        quality_report_path: str | Path | None = None,
    ) -> None:
        super().__init__(cfg=cfg, run_id=run_id, log=log)
        self.warehouse_path = warehouse_path
        self.catalog_path = catalog_path
        self.lineage_path = lineage_path
        self.quality_report_path = quality_report_path

    def get_llm(self):
        self.llm_error = "Dashboard is deterministic and never uses an LLM"
        return None

    def _service(self) -> AnalysisService:
        paths = self.cfg.get("paths") or {}
        warehouse = self.warehouse_path or Path(
            paths.get("processed", "data/processed")
        ) / "warehouse.duckdb"
        lineage = self.lineage_path or Path(warehouse).with_name("lineage.json")
        quality = self.quality_report_path or Path(
            paths.get("quality", "data/quality")
        ) / "quality_report.json"
        return AnalysisService(
            resolve(warehouse), self.catalog_path,
            lineage_path=lineage, quality_report_path=quality,
        )

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        request = AnalysisRequest.model_validate(ctx.get("analysis_request"))
        reports_dir = path_of(self.cfg, "reports") / self.run_id
        existing = ctx.get("analysis_dataset_path")
        if existing and Path(existing).is_file():
            dataset = load_json(existing)
        else:
            dataset = self._service().build(request)
            save_json(dataset, reports_dir / "analysis_dataset.json")

        data = build_dashboard_data(
            dataset,
            run_id=self.run_id,
            analyst_report=ctx.get("analysis_report"),
        )
        data_path = save_json(data, reports_dir / "dashboard_data.json")
        dashboard_cfg = self.cfg.get("dashboard") or {}
        public_path = export_dashboard_json(
            data,
            dashboard_cfg.get("data_output", "dashboard/public/data/dashboard.json"),
        )
        warnings = [
            notice["message"] for notice in data["notices"]
            if notice["severity"] in {"warning", "review"}
        ]
        return {
            "dashboard_paths": {
                "data": str(data_path),
                "public": str(public_path),
            },
            "dashboard_summary": {
                "cards": len(data["cards"]),
                "series": len(data["series"]),
                "comparisons": len(data["comparisons"]),
                "insights": len(data["insights"]),
                "notices": len(data["notices"]),
                "publication_status": data["publication_status"],
            },
            "warnings": warnings,
        }


class DashboardSpecAgent(BaseAgent):
    """Build the Finova dashboard contract from real artefacts only.

    The preliminary spec (without analyst insights) is used to compute the
    history diff, then the spec is rebuilt with ``context.insights``/``xai``.
    The final validation fails closed: any insight citing an unknown fact id
    aborts the run instead of shipping an unverifiable statement.
    """

    name = "dashboard_spec"

    def __init__(
        self,
        cfg: dict[str, Any] | None = None,
        run_id: str | None = None,
        log=None,
        *,
        warehouse_path: str | Path | None = None,
        catalog_path: str | Path = DEFAULT_CATALOG,
        lineage_path: str | Path | None = None,
        quality_report_path: str | Path | None = None,
        reference_path: str | Path | None = None,
    ) -> None:
        super().__init__(cfg=cfg, run_id=run_id, log=log)
        self.catalog_path = catalog_path
        self.warehouse_path = warehouse_path
        self.lineage_path = lineage_path
        self.quality_report_path = quality_report_path
        self.reference_path = reference_path

    def get_llm(self):
        self.llm_error = "Dashboard is deterministic and never uses an LLM"
        return None

    # ------------------------------------------------------------------ paths
    def _config(self) -> Mapping[str, Any]:
        return self.cfg.get("dashboard") or {}

    def _warehouse(self) -> Path:
        paths = self.cfg.get("paths") or {}
        return resolve(
            self.warehouse_path
            if self.warehouse_path is not None
            else Path(paths.get("processed", "data/processed")) / "warehouse.duckdb"
        )

    def _lineage(self) -> Path:
        return resolve(
            self.lineage_path
            if self.lineage_path is not None
            else self._warehouse().with_name("lineage.json")
        )

    def _quality(self) -> Path:
        paths = self.cfg.get("paths") or {}
        return resolve(
            self.quality_report_path
            if self.quality_report_path is not None
            else Path(paths.get("quality", "data/quality")) / "quality_report.json"
        )

    def _reference(self) -> Path:
        return resolve(
            self.reference_path or self._config().get("reference_path", REFERENCE_PATH)
        )

    def _public_path(self) -> Path:
        return resolve(
            self._config().get("spec_output", "dashboard_app/public/data/finova.json")
        )

    def _history_dir(self) -> Path:
        path = resolve(
            self._config().get("history_dir", "outputs/dashboard/history")
        )
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ---------------------------------------------------------------- dataset
    def default_request(self) -> AnalysisRequest:
        dashboard_cfg = self._config()
        primary = str(dashboard_cfg.get("default_country", PRIMARY_COUNTRY))
        year = int(dashboard_cfg.get("default_year", 2024))
        others = [code for code in PEERS if code != primary]
        return AnalysisRequest(
            iso3=(primary, *others), mode="year", year=year,
        )

    def _dataset(self, ctx: Mapping[str, Any], reports_dir: Path) -> dict[str, Any]:
        existing = ctx.get("analysis_dataset_path")
        if existing and Path(existing).is_file():
            return load_json(existing)
        request = AnalysisRequest.model_validate(
            ctx.get("analysis_request") or self.default_request().model_dump(mode="json")
        )
        paths = self.cfg.get("paths") or {}
        service = AnalysisService(
            self._warehouse(), self.catalog_path,
            lineage_path=self._lineage(), quality_report_path=self._quality(),
        )
        dataset = build_with_findex_wave(service, request)
        save_json(dataset, reports_dir / "analysis_dataset.json")
        return dataset

    def _previous_snapshot(self) -> dict[str, Any] | None:
        files = sorted(
            (item for item in self._history_dir().glob("*.json") if item.is_file()),
            key=lambda item: (item.stat().st_mtime, item.name),
        )
        for path in reversed(files):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("metrics"):
                return data
        return None

    # ---------------------------------------------------------------- execute
    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        run_id = self.run_id
        reports_dir = path_of(self.cfg, "reports") / run_id
        reports_dir.mkdir(parents=True, exist_ok=True)
        dataset = self._dataset(ctx, reports_dir)

        warehouse = self._warehouse()
        reader = WarehouseReader(warehouse) if warehouse.is_file() else None
        reference = load_reference(self._reference())
        history_files = sorted(self._history_dir().glob("*.json"))
        pipeline = load_pipeline_info(
            self.cfg, reader=reader,
            lineage_path=self._lineage(), quality_report_path=self._quality(),
            reports_dir=path_of(self.cfg, "reports"), history_files=history_files,
        )

        preliminary = build_finova_spec(
            dataset, run_id=run_id, reader=reader, reference=reference,
            pipeline=pipeline,
        )
        changes = diff_snapshots(preliminary, self._previous_snapshot())
        spec = build_finova_spec(
            dataset, run_id=run_id, reader=reader, reference=reference,
            history=changes.model_dump(mode="json"), pipeline=pipeline,
            insights=ctx.get("insights"), xai=ctx.get("xai") or None,
        )

        spec_path = save_json(
            spec.model_dump(mode="json"), reports_dir / "finova_spec.json"
        )
        public_path = save_json(spec.model_dump(mode="json"), self._public_path())
        history_path = save_json(
            snapshot_from_spec(spec), self._history_dir() / f"{run_id}.json"
        )
        warnings = [
            notice.message for notice in spec.notices
            if notice.severity in {"warning", "review"}
        ]
        return {
            "finova_spec_path": str(spec_path),
            "dashboard_public_path": str(public_path),
            "dashboard_history_path": str(history_path),
            "spec_year": spec.year,
            "country_name": spec.country.name,
            "dashboard_spec_summary": {
                "schema_version": spec.schema_version,
                "pages": len(spec.pages),
                "facts": len(spec.facts),
                "notices": len(spec.notices),
                "year": spec.year,
                "country": spec.country.iso3,
                "publication_status": spec.publication_status,
                "history_available": changes.available,
            },
            "warnings": warnings,
        }


__all__ = ["DashboardAgent", "DashboardSpecAgent"]
