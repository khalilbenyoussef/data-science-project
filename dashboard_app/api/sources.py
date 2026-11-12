"""API de la page « Mes données » : sources CSV de l'utilisateur (locale uniquement).

detect -> dry-run -> confirm (copie dans data/uploads/ + recalcul en arriere-plan),
liste, retrait et consultation des valeurs publiees. Messages d'erreur en francais ;
un seul recalcul a la fois (409) ; jamais d'ecrasement d'une source officielle.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from biflow.tools.user_sources import UserSourceError
from biflow.tools.user_sources.comparisons import comparisons, official_kpis
from biflow.tools.user_sources.data import UserData
from biflow.tools.user_sources.jobs import JobBusy, JobManager, Runner, pipeline_runner
from biflow.tools.user_sources.service import (
    DEFAULT_PENDING_DIR, PendingUploads, SourceConflict, SourceNotFound, check_name, confirm,
    detect_upload, discard_old_pending, evaluate, list_sources, max_file_mb, remove, source_data,
)

ACCEPTED_TYPES = {"text/csv", "application/csv", "text/plain", "application/vnd.ms-excel",
                  "application/octet-stream", ""}
CHUNK = 1 << 20


class SourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    upload_id: str = Field(max_length=64)
    name: str = Field(max_length=64)
    mapping: dict[str, Any] = {}


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, SourceNotFound):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (SourceConflict, JobBusy)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


def create_sources_router(cfg: Mapping[str, Any], *, warehouse: Path,
                          runner: Runner | None = None) -> tuple[APIRouter, JobManager]:
    uploads = dict(cfg.get("uploads") or {})
    pending = PendingUploads(uploads.get("pending_dir", DEFAULT_PENDING_DIR))
    timeout_s = float(uploads.get("job_timeout_min", 15)) * 60
    jobs = JobManager(uploads.get("jobs_dir", "outputs/jobs"), timeout_s=timeout_s,
                      runner=runner or pipeline_runner(cfg, timeout_s))
    router = APIRouter(prefix="/api/sources", tags=["sources"])

    def guarded(call: Callable[[], Any]) -> Any:
        try:
            return call()
        except (UserSourceError, JobBusy) as exc:
            raise _http(exc) from exc

    @router.post("/detect")
    async def detect(file: UploadFile = File(...)) -> dict[str, Any]:
        filename = Path(file.filename or "").name
        if not filename.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail="Seuls les fichiers .csv sont acceptés.")
        content_type = (file.content_type or "").split(";")[0].strip().lower()
        if content_type not in ACCEPTED_TYPES:
            raise HTTPException(status_code=415, detail=f"Type de fichier refusé ({content_type}) : "
                                "un fichier CSV texte est attendu.")
        limit = int(max_file_mb(cfg) * 1e6)
        data = bytearray()
        while chunk := await file.read(CHUNK):
            data.extend(chunk)
            if len(data) > limit:
                raise HTTPException(status_code=413, detail=f"Fichier trop volumineux : la limite est de "
                                    f"{max_file_mb(cfg):g} Mo.")
        discard_old_pending(pending.root)
        upload_id = pending.save(filename, bytes(data))
        try:
            result = detect_upload(pending.path(upload_id), cfg, filename)
        except UserSourceError as exc:
            pending.discard(upload_id)
            raise _http(exc) from exc
        return {"upload_id": upload_id, "size_bytes": len(data), "max_file_mb": max_file_mb(cfg), **result}

    @router.post("/dry-run")
    def dry_run(payload: SourceRequest) -> dict[str, Any]:
        result = guarded(lambda: evaluate(pending.path(payload.upload_id), check_name(payload.name),
                                          payload.mapping, cfg))
        result.pop("_mapping", None)
        return result

    @router.post("/confirm")
    def confirm_source(payload: SourceRequest) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            path = pending.path(payload.upload_id)
            check_name(payload.name)
            if jobs.active() is not None:
                raise JobBusy("Un recalcul est déjà en cours : attendez la fin avant d'ajouter une source.")
            done = confirm(path, payload.name, payload.mapping, cfg)
            pending.discard(payload.upload_id)
            job = jobs.start("add", payload.name)
            return {"job_id": job["job_id"], "name": payload.name, "replaced": done["replaced"]}

        return guarded(run)

    @router.get("/comparable-kpis")
    def comparable_kpis() -> dict[str, Any]:
        """KPI officiels proposes a l'etape « Indicateurs » (definition et denominateur)."""
        return {"kpis": sorted(official_kpis().values(), key=lambda kpi: kpi["name_fr"])}

    @router.get("/comparisons")
    def user_comparisons(iso3: str = Query(..., pattern=r"^[A-Za-z]{3}$"),
                         year: int = Query(..., ge=2000, le=2100)) -> dict[str, Any]:
        """Vos indicateurs face aux KPI officiels declares comparables (lecture seule)."""
        return comparisons(UserData(cfg, warehouse), warehouse, iso3.upper(), year, official_kpis())

    @router.get("/jobs/{job_id}")
    def job_status(job_id: str) -> dict[str, Any]:
        try:
            return jobs.get(job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Recalcul introuvable.") from exc

    @router.get("")
    def sources() -> dict[str, Any]:
        return {"sources": list_sources(cfg, warehouse, jobs.last_by_source()), "active_job": jobs.active(),
                "max_file_mb": max_file_mb(cfg)}

    @router.delete("/{name}")
    def delete(name: str) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            check_name(name)
            if jobs.active() is not None:
                raise JobBusy("Un recalcul est déjà en cours : attendez la fin avant de supprimer une source.")
            remove(name, cfg)
            job = jobs.start("delete", name)
            return {"job_id": job["job_id"], "name": name}

        return guarded(run)

    @router.get("/{name}/data")
    def data(name: str, indicator: str | None = Query(default=None, max_length=120),
             iso3: str | None = Query(default=None, min_length=3, max_length=3),
             year: int | None = Query(default=None, ge=1900, le=2100)) -> dict[str, Any]:
        return guarded(lambda: source_data(cfg, warehouse, name, indicator=indicator, iso3=iso3, year=year))

    return router, jobs


__all__ = ["create_sources_router"]

