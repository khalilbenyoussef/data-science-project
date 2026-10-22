"""Contrat commun des agents BIFlow.

Chaque agent expose `execute(ctx)` (etat partage -> resultats) et herite de
`BaseAgent` qui fournit la configuration, le logger et un rapport JSON
standardise dans outputs/reports/<run_id>/<agent>.json.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any, Mapping

from langchain_core.messages import HumanMessage, SystemMessage

from biflow.config import load_config, path_of
from biflow.llm import build_agent_llm
from biflow.utils.io import save_json
from biflow.utils.logger import get_logger

AGENT_VERSION = "0.1.0"


def extract_json(text: str) -> Any:
    """Recupere le premier objet JSON d'une reponse LLM (meme entouree de texte)."""
    if not isinstance(text, str):
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = cleaned.find(opener)
        if start == -1:
            continue
        depth = 0
        for index in range(start, len(cleaned)):
            char = cleaned[index]
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cleaned[start : index + 1])
                    except json.JSONDecodeError:
                        break
    return None


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
        self._llm = None
        self._llm_resolved = False
        self.llm_error: str | None = None

    # ------------------------------------------------------------------ LLM
    def get_llm(self):
        """Client LLM de l'agent (None si desactive ou indisponible)."""
        if self._llm_resolved:
            return self._llm
        self._llm_resolved = True
        llm_cfg = self.cfg.get("llm") or {}
        disabled = llm_cfg.get("disabled_agents") or []
        if self.name in disabled:
            self.llm_error = "LLM desactive pour cet agent (fallback deterministe)"
            return None
        if not llm_cfg.get("enabled", True):
            self.llm_error = "LLM desactive dans la configuration"
            return None
        try:
            self._llm = build_agent_llm(self.name, self.cfg)
        except Exception as exc:  # noqa: BLE001 - le pipeline continue sans LLM
            self.llm_error = f"{type(exc).__name__}: {exc}"
            self.log.warning("[%s] LLM indisponible : %s", self.name, exc)
        return self._llm

    def llm_usage(self) -> dict[str, Any]:
        return self._llm.usage() if self._llm is not None else {}

    def ask_text(self, prompt: str, system: str | None = None) -> str | None:
        client = self.get_llm()
        if client is None:
            return None
        messages = []
        if system:
            messages.append(SystemMessage(content=system))
        messages.append(HumanMessage(content=prompt))
        try:
            response = client.invoke(messages)
        except Exception as exc:  # noqa: BLE001 - fallback deterministe
            self.log.warning("[%s] echec LLM : %s", self.name, exc)
            return None
        content = getattr(response, "content", response)
        return content if isinstance(content, str) else str(content)

    def ask_json(self, prompt: str, system: str | None = None, fallback: Any = None) -> Any:
        strict = (
            (system + "\n" if system else "")
            + "Reponds uniquement avec un objet JSON valide, sans texte autour "
            "ni balises Markdown."
        )
        text = self.ask_text(prompt, system=strict)
        if text is None:
            return fallback
        parsed = extract_json(text)
        if parsed is None:
            self.log.warning("[%s] reponse LLM non JSON, fallback applique", self.name)
            return fallback
        return parsed

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
            warnings = list(outputs.get("warnings") or [])
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
            "llm_usage": self.llm_usage(),
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
