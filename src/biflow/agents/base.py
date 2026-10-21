"""Contrat commun des agents BIFlow.

Chaque agent expose `execute(ctx)` (etat partage -> resultats) et herite de
`BaseAgent` qui fournit la configuration, le logger et un rapport JSON
standardise dans outputs/reports/<run_id>/<agent>.json.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Mapping

from biflow.config import load_config, path_of
from biflow.utils.io import save_json
from biflow.utils.logger import get_logger

AGENT_VERSION = "0.1.0"


class AgentError(RuntimeError):
    """Erreur bloquante levee volontairement par un agent."""


class BaseAgent:
    """Socle commun : configuration, logger, execution et rapport."""

    name = "base"

    def __init__(
        self,
        cfg: dict[str, Any] | None = None,
        run_id: str | None = None,
        log=None,
    ) -> None:
        self.cfg = cfg if cfg is not None else load_config()
        self.run_id = run_id or datetime.now().strftime("%Y%m%dT%H%M%S")
        self.log = log or get_logger(f"biflow.{self.name}")

    def execute(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        """A implementer : recoit l'etat partage, renvoie les sorties de l'agent."""
        raise NotImplementedError(f"{type(self).__name__}.execute() n'est pas implemente")

    def __call__(self, ctx: Mapping[str, Any]) -> dict[str, Any]:
        return self.execute(ctx)

    def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute l'agent, mesure la duree et ecrit un rapport standardise."""
        started_at = datetime.now().isoformat(timespec="seconds")
        started = time.perf_counter()
        status = "success"
        outputs: dict[str, Any] = {}
        warnings: list[str] = []
        errors: list[str] = []

        try:
            outputs = self.execute(*args, **kwargs) or {}
        except Exception as exc:  # noqa: BLE001 - le rapport doit capturer l'echec
            status = "failed"
            errors.append(f"{type(exc).__name__}: {exc}")
            self.log.exception("[%s] echec : %s", self.name, exc)

        report = {
            "agent": self.name,
            "agent_version": AGENT_VERSION,
            "run_id": self.run_id,
            "started_at": started_at,
            "duration_s": round(time.perf_counter() - started, 3),
            "status": status,
            "outputs": outputs,
            "warnings": warnings,
            "errors": errors,
        }
        self.save_report(report)
        return report

    def report_path(self):
        """Chemin du rapport JSON de l'agent pour le run courant."""
        reports_dir = path_of(self.cfg, "reports") / self.run_id
        reports_dir.mkdir(parents=True, exist_ok=True)
        return reports_dir / f"{self.name}.json"

    def save_report(self, report: dict[str, Any]) -> None:
        save_json(report, self.report_path())
        self.log.info("[%s] rapport ecrit : %s", self.name, self.report_path())
