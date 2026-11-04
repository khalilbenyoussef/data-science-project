"""Recalcul en arriere-plan apres l'ajout ou le retrait d'une source utilisateur.

Un seul job a la fois ; etat sur disque (outputs/jobs/<job_id>.json) pour qu'un
rechargement de page ou un redemarrage de l'API retrouve le statut. Le job lance
``main.py run --no-llm --offline-official`` (les sources officielles sont reprises
du snapshot publie, sans reseau) puis Route 2 (finova.json et vues des pairs).
Un job qui depasse le delai configure se termine en erreur avec un message clair.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

from biflow.config import ROOT, path_of, resolve

ACTIVE = ("queued", "running")
STEPS = ("collector", "snapshot", "profiler", "quality", "etl", "semantic_kpi", "auditor", "route2")
HEARTBEAT_S = 5
STALE_S = 120  # sans battement : job orphelin (API redemarree pendant le recalcul)
ROUTE2_CODE = ("import sys; from biflow.route2_graph import run_route2; s = run_route2(); "
               "print('ROUTE2', s.get('status'), s.get('run_id'), flush=True); "
               "sys.exit(0 if s.get('status') == 'success' else 2)")

Runner = Callable[[dict[str, Any], Callable[..., None]], None]


class JobBusy(RuntimeError):
    """Un recalcul est deja en cours (HTTP 409)."""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _age(stamp: str | None) -> float:
    try:
        return time.time() - datetime.fromisoformat(stamp).timestamp() if stamp else 0.0
    except ValueError:
        return 0.0


class JobManager:
    def __init__(self, root: str | Path, *, timeout_s: float, runner: Runner) -> None:
        self.root = resolve(root)
        self.timeout_s = float(timeout_s)
        self.runner = runner
        self._lock = threading.Lock()
        # lectures et ecritures d'un fichier de job serialisees : sous Windows, os.replace
        # echoue (acces refuse) si une requete de suivi lit le fichier au meme moment
        self._io = threading.RLock()
        self._mine: set[str] = set()  # jobs suivis par ce processus

    # ------------------------------------------------------------- stockage
    def _path(self, job_id: str) -> Path:
        if not isinstance(job_id, str) or len(job_id) != 32 or not job_id.isalnum():
            raise KeyError(job_id)
        return self.root / f"{job_id}.json"

    def _write(self, job: Mapping[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(job["job_id"])
        tmp = path.with_suffix(".json.tmp")
        with self._io:
            tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
            for attempt in range(20):  # fichier lu par un autre processus (antivirus, indexation)
                try:
                    os.replace(tmp, path)
                    return
                except PermissionError:
                    if attempt == 19:
                        raise
                    time.sleep(0.05)

    def _read(self, job_id: str) -> dict[str, Any]:
        with self._io:
            try:
                return json.loads(self._path(job_id).read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise KeyError(job_id) from exc

    def get(self, job_id: str) -> dict[str, Any]:
        """Statut ; un job actif trop long ou orphelin est clos en erreur."""
        job = self._read(job_id)
        if job["status"] in ACTIVE:
            if _age(job.get("started_at")) > self.timeout_s + 2 * HEARTBEAT_S:
                job = self._close(job, "error", f"Délai dépassé ({self.timeout_s / 60:g} min) : le recalcul "
                                  "a été interrompu. Relancez l'opération.")
            elif job_id not in self._mine and _age(job.get("heartbeat_at")) > STALE_S:
                job = self._close(job, "error", "Le recalcul a été interrompu (redémarrage du serveur). "
                                  "Relancez l'opération.")
        return job

    def list(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        jobs = []
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                jobs.append(self.get(path.stem))
            except KeyError:
                continue
        return jobs

    def active(self) -> dict[str, Any] | None:
        return next((job for job in self.list() if job["status"] in ACTIVE), None)

    def last_by_source(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for job in self.list():
            out.setdefault(job.get("source") or "", {
                "job_id": job["job_id"], "kind": job["kind"], "status": job["status"],
                "finished_at": job.get("finished_at"), "run_id": job.get("run_id")})
        return out

    def _close(self, job: dict[str, Any], status: str, message: str, **extra: Any) -> dict[str, Any]:
        job = {**job, **extra, "status": status, "message": message, "finished_at": _now(),
               "seconds": round(_age(job.get("started_at")), 1)}
        self._write(job)
        return job

    # ------------------------------------------------------------- execution
    def start(self, kind: str, source: str) -> dict[str, Any]:
        with self._lock:
            if self.active() is not None:
                raise JobBusy("Un recalcul est déjà en cours : attendez la fin avant une nouvelle opération.")
            job_id = uuid.uuid4().hex
            job = {"job_id": job_id, "kind": kind, "source": source, "status": "queued", "step": None,
                   "steps_done": [], "run_id": None, "route2_run_id": None, "message": None, "reasons": [],
                   "started_at": _now(), "heartbeat_at": _now(), "finished_at": None, "seconds": None}
            self._write(job)
            self._mine.add(job_id)
        threading.Thread(target=self._run, args=(job_id,), name=f"source-job-{job_id[:8]}",
                         daemon=True).start()
        return job

    def _run(self, job_id: str) -> None:
        state = self._read(job_id)

        def update(**fields: Any) -> None:
            state.update(fields, heartbeat_at=_now())
            if fields.get("status") not in (None, *ACTIVE):
                state["finished_at"] = _now()
                state["seconds"] = round(_age(state.get("started_at")), 1)
            self._write(state)

        try:
            update(status="running")
            self.runner(state, update)
            if state["status"] in ACTIVE:
                update(status="error", message="Le recalcul s'est terminé sans statut final.")
        except Exception as exc:  # noqa: BLE001 - un job ne fait jamais tomber l'API
            update(status="error", message=f"Erreur pendant le recalcul : {type(exc).__name__}: {exc}")
        finally:
            self._mine.discard(job_id)


# ------------------------------------------------------------------ pipeline
def _stream(command: list[str], deadline: float, update: Callable[..., None], state: Mapping[str, Any],
            on_line: Callable[[str], None]) -> tuple[int | None, list[str]]:
    """Execute une commande, suit ses lignes, battement et delai ; (code | None si delai, fin du log)."""
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONIOENCODING": "utf-8"}
    proc = subprocess.Popen(command, cwd=str(ROOT), env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.DEVNULL)
    tail: list[str] = []

    def read() -> None:
        assert proc.stdout is not None
        for line in proc.stdout:
            tail.append(line.rstrip())
            del tail[:-40]
            on_line(line)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    last = 0.0
    try:
        while proc.poll() is None:
            if time.time() > deadline:
                proc.kill()
                proc.wait()
                return None, tail
            if time.time() - last >= HEARTBEAT_S:
                update(step=state.get("step"))
                last = time.time()
            time.sleep(0.5)
    finally:
        if proc.poll() is None:  # job interrompu : jamais de recalcul orphelin
            proc.kill()
            proc.wait()
    reader.join(timeout=5)
    return proc.returncode, tail


def pipeline_runner(cfg: Mapping[str, Any], timeout_s: float) -> Runner:
    """Runner reel : pipeline hors ligne puis Route 2 ; statut final classe."""

    def run(job: dict[str, Any], update: Callable[..., None]) -> None:
        deadline = time.time() + timeout_s
        run_id = f"user_{job['kind']}_{datetime.now().strftime('%Y%m%dT%H%M%S')}"
        update(run_id=run_id, step="collector")

        def on_line(line: str) -> None:
            for step in STEPS[:-1]:
                if f"| biflow.{step} " in line or f"[{step}]" in line:
                    if step != job.get("step"):
                        done = list(STEPS[:STEPS.index(step)])
                        update(step=step, steps_done=done)
                    break

        code, tail = _stream([sys.executable, "main.py", "run", "--no-llm", "--offline-official",
                              "--run-id", run_id], deadline, update, job, on_line)
        if code is None:
            update(status="error", message=f"Délai dépassé ({timeout_s / 60:g} min) : le recalcul a été "
                   "interrompu. Les données publiées précédentes restent en place.")
            return
        summary = _load(path_of(dict(cfg), "reports") / run_id / "run.json")
        snapshot = summary.get("snapshot") or {}
        audit = summary.get("audit") or {}
        if summary.get("status") == "no_change" or snapshot.get("status") == "no_change":
            update(status="success", steps_done=list(STEPS), step=None,
                   message="Aucune donnée nouvelle : le contenu est identique à la version publiée.")
            return
        if code != 0 or summary.get("status") not in ("success",):
            errors = summary.get("errors") or [line for line in tail if "ERROR" in line][-3:]
            update(status="error", message="Le recalcul a échoué : " + ("; ".join(errors) or "voir le journal"),
                   log_tail=tail[-15:])
            return
        if audit.get("verdict") == "fail" or snapshot.get("status") == "not_published":
            update(status="audit_failed", reasons=[f"verdict d'audit : {audit.get('verdict')}"],
                   message="L'audit a relevé un échec : la version publiée précédente reste en place.")
            return
        quality = _load(resolve((cfg.get("paths") or {}).get("quality", "data/quality")) / "quality_report.json")
        excluded = [item for item in summary.get("excluded_sources") or quality.get("excluded_sources") or []
                    if item.get("source") == job["source"]]
        check = (quality.get("user_sources") or {}).get(job["source"]) or {}
        update(step="route2", steps_done=list(STEPS[:-1]))
        code, tail = _stream([sys.executable, "-c", ROUTE2_CODE], deadline, update, job, lambda line: None)
        route2 = next((line.split()[2] for line in tail if line.startswith("ROUTE2 ") and len(line.split()) > 2),
                      None)
        if code is None:
            update(status="error", message=f"Délai dépassé ({timeout_s / 60:g} min) pendant la mise à jour "
                   "du tableau de bord.")
            return
        if code != 0:
            update(status="error", message="Pipeline terminé, mais la mise à jour du tableau de bord a échoué.",
                   log_tail=tail[-15:])
            return
        if job["kind"] == "add" and excluded:
            reasons = [issue.get("message") or issue.get("code") for issue in check.get("issues") or []] \
                or [item.get("reason") for item in excluded]
            update(status="quality_failed", steps_done=list(STEPS), step=None, route2_run_id=route2,
                   reasons=[r for r in reasons if r], quality_score=check.get("score"),
                   message="Source exclue par le contrôle qualité : elle n'est pas intégrée à l'entrepôt.")
            return
        update(status="success", steps_done=list(STEPS), step=None, route2_run_id=route2,
               quality_score=check.get("score"), audit=audit.get("verdict"),
               message="Source intégrée et tableau de bord recalculé." if job["kind"] == "add"
               else "Source retirée et tableau de bord recalculé.")

    return run


def _load(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


__all__ = ["JobBusy", "JobManager", "STEPS", "pipeline_runner"]
