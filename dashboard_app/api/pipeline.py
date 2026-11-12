"""Demonstration multi-agents de la page « Sources et qualité ».

``GET /api/pipeline/agents`` : frise des agents du dernier run (Route 1 et
Route 2) lue dans les rapports d'agent, ou d'un run donne (``run_id``).
``POST /api/pipeline/demo`` : relance le recalcul hors ligne existant (sources
officielles reprises du snapshot publie, sans telechargement) ; 409 si un
recalcul est deja en cours. La progression se suit avec
``GET /api/sources/jobs/{job_id}`` (etape courante, etapes faites, ignorees).
"""
from __future__ import annotations

import re
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query

from biflow.tools.deliverables import Context, run_timeline
from biflow.tools.user_sources.jobs import JobBusy, JobManager

RUN_ID = re.compile(r"^[A-Za-z0-9_]{1,80}$")


def create_pipeline_router(*, context: Callable[[], Context], jobs: JobManager) -> APIRouter:
    router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

    @router.get("/agents")
    def agents(run_id: str | None = Query(default=None, max_length=80)) -> dict[str, Any]:
        if run_id is not None and not RUN_ID.fullmatch(run_id):
            raise HTTPException(status_code=400, detail="Identifiant de run invalide.")
        try:
            timeline = run_timeline(context(), run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Run introuvable : {run_id}") from exc
        return {**timeline, "active_job": jobs.active()}

    @router.post("/demo")
    def demo() -> dict[str, Any]:
        try:
            job = jobs.start("demo", "")
        except JobBusy as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"job_id": job["job_id"], "status": job["status"]}

    return router


__all__ = ["create_pipeline_router"]
