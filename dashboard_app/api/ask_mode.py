"""« Vos données : IA externe » : choix par session de navigateur, consentement obligatoire.

- Chaque session commence désactivée (traitement local), même si la configuration
  suggère l'option (``llm.ask.allow_user_data_to_llm: true`` ne fait que proposer la
  boîte de consentement) ; seul un POST avec ``consent: true`` l'active, pour cette
  session seulement.
- Le choix vit en mémoire du serveur : il disparaît au redémarrage et n'est jamais
  écrit dans config.yaml.
- ``llm.ask.user_data_llm_switch: false`` masque l'option et refuse toute activation.
- Journal local des consentements (outputs/logs/user_data_consent.log) : horodatage,
  session hachée, état, fournisseur ; jamais la question ni une valeur.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

SESSION = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
NO_KEY = "Aucune clé IA configurée : les réponses restent locales."
SWITCH_OFF = "Option désactivée par l'administrateur : les réponses restent locales."


class ModeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: StrictStr
    enabled: StrictBool
    consent: StrictBool = False


def session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:16]


class UserDataModes:
    """Choix par session (mémoire du processus, LRU), jamais persisté."""

    def __init__(self, *, switch_available: bool, suggested: bool, provider: Callable[[], str | None],
                 log_path: Path, max_sessions: int = 512) -> None:
        self.switch_available = switch_available
        self.suggested = suggested
        self.provider = provider
        self.log_path = log_path
        self.max_sessions = max_sessions
        self._enabled: OrderedDict[str, bool] = OrderedDict()
        self._lock = threading.Lock()

    def enabled(self, session_id: str | None) -> bool:
        if not self.switch_available or not session_id or not SESSION.fullmatch(session_id):
            return False
        with self._lock:
            return self._enabled.get(session_id, False)

    def status(self, session_id: str) -> dict[str, Any]:
        provider = self.provider()
        reason = None
        if not self.switch_available:
            reason = SWITCH_OFF
        elif provider is None:
            reason = NO_KEY
        return {"enabled": self.enabled(session_id) and provider is not None,
                "switch_available": self.switch_available, "llm_available": provider is not None,
                "provider": provider, "suggested": self.suggested and self.switch_available and provider is not None,
                "reason": reason}

    def set(self, session_id: str, enabled: bool, consent: bool) -> dict[str, Any]:
        provider = self.provider()
        if enabled:
            if not self.switch_available:
                raise ValueError(SWITCH_OFF)
            if provider is None:
                raise ValueError(NO_KEY)
            if consent is not True:
                raise ValueError("Consentement requis : cochez « J'accepte que mes données soient envoyées "
                                 f"à {provider} pour cette session » puis « Activer ».")
        with self._lock:
            self._enabled.pop(session_id, None)
            if enabled:
                self._enabled[session_id] = True
                while len(self._enabled) > self.max_sessions:
                    self._enabled.popitem(last=False)
        self._log(session_id, enabled, provider)
        return self.status(session_id)

    def _log(self, session_id: str, enabled: bool, provider: str | None) -> None:
        """Une ligne JSON par changement : jamais la question ni une valeur."""
        line = {"timestamp": datetime.now().isoformat(timespec="seconds"), "session": session_hash(session_id),
                "enabled": enabled, "provider": provider}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def create_ask_mode_router(modes: UserDataModes) -> APIRouter:
    router = APIRouter(prefix="/api/ask", tags=["ask"])

    def checked(session_id: str) -> str:
        if not SESSION.fullmatch(session_id or ""):
            raise HTTPException(status_code=400, detail="Session invalide : rechargez la page.")
        return session_id

    @router.get("/user-data-mode")
    def get_mode(session_id: str = Query(..., max_length=64)) -> dict[str, Any]:
        return modes.status(checked(session_id))

    @router.post("/user-data-mode")
    def set_mode(payload: ModeRequest) -> dict[str, Any]:
        try:
            return modes.set(checked(payload.session_id), payload.enabled, payload.consent)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router


__all__ = ["NO_KEY", "SWITCH_OFF", "UserDataModes", "create_ask_mode_router", "session_hash"]
