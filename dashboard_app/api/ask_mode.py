"""« Vos données : IA externe » : choix par compte et par session, consentement obligatoire.

- Portée du choix : compte connecté + session de connexion (``sid`` du jeton d'accès,
  stable au renouvellement du jeton, révoquée à la déconnexion) + session de navigateur
  (onglet). Un compte ne voit ni ne modifie jamais le choix d'un autre compte ; après
  une déconnexion, la session de connexion suivante repart en traitement local.
- Chaque session commence désactivée (traitement local), même si la configuration
  suggère l'option (``llm.ask.allow_user_data_to_llm: true`` ne fait que proposer la
  boîte de consentement) ; seul un POST avec ``consent: true`` l'active, pour cette
  session seulement.
- Le choix vit en mémoire du serveur : il disparaît au redémarrage et n'est jamais
  écrit dans config.yaml.
- ``llm.ask.user_data_llm_switch: false`` masque l'option et refuse toute activation.
- Routes protégées par l'authentification FinOVA (``require_user``).
- Journal local des consentements (outputs/logs/user_data_consent.log) : horodatage,
  portée hachée, état, fournisseur ; jamais la question, une valeur ni l'adresse email.
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

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, StrictBool, StrictStr

from dashboard_app.auth.deps import require_user
from dashboard_app.auth.security import decode_access_token

SESSION = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
NO_KEY = "Aucune clé IA configurée : les réponses restent locales."
SWITCH_OFF = "Option désactivée par l'administrateur : les réponses restent locales."


class ModeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: StrictStr
    enabled: StrictBool
    consent: StrictBool = False


def session_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def consent_scope(request: Request, user: dict[str, Any] = Depends(require_user)) -> str:
    """« <id du compte>:<sid> » : compte et session de connexion du jeton déjà validé par
    ``require_user`` (aucune autre vérification d'identité ici)."""
    token = (request.headers.get("Authorization") or "").partition(" ")[2].strip()
    try:
        sid = str(decode_access_token(request.app.state.auth.settings, token).get("sid") or "")
    except jwt.PyJWTError as exc:  # jeton expire entre-temps
        raise HTTPException(status_code=401, detail="Session invalide ou expirée.",
                            headers={"WWW-Authenticate": "Bearer"}) from exc
    if not sid:
        raise HTTPException(status_code=401, detail="Session invalide.", headers={"WWW-Authenticate": "Bearer"})
    return f"{user['id']}:{sid}"


class UserDataModes:
    """Choix par (compte, session de connexion, onglet) en mémoire du processus (LRU), jamais persisté."""

    def __init__(self, *, switch_available: bool, suggested: bool, provider: Callable[[], str | None],
                 log_path: Path, max_sessions: int = 512) -> None:
        self.switch_available = switch_available
        self.suggested = suggested
        self.provider = provider
        self.log_path = log_path
        self.max_sessions = max_sessions
        self._enabled: OrderedDict[str, bool] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def key(scope: str, session_id: str) -> str:
        return f"{scope}|{session_id}"

    def enabled(self, scope: str | None, session_id: str | None) -> bool:
        if (not self.switch_available or not scope or not session_id
                or not SESSION.fullmatch(session_id)):
            return False
        with self._lock:
            return self._enabled.get(self.key(scope, session_id), False)

    def status(self, scope: str, session_id: str) -> dict[str, Any]:
        provider = self.provider()
        reason = None
        if not self.switch_available:
            reason = SWITCH_OFF
        elif provider is None:
            reason = NO_KEY
        return {"enabled": self.enabled(scope, session_id) and provider is not None,
                "switch_available": self.switch_available, "llm_available": provider is not None,
                "provider": provider, "suggested": self.suggested and self.switch_available and provider is not None,
                "reason": reason}

    def set(self, scope: str, session_id: str, enabled: bool, consent: bool) -> dict[str, Any]:
        provider = self.provider()
        if enabled:
            if not self.switch_available:
                raise ValueError(SWITCH_OFF)
            if provider is None:
                raise ValueError(NO_KEY)
            if consent is not True:
                raise ValueError("Consentement requis : cochez « J'accepte que mes données soient envoyées "
                                 f"à {provider} pour cette session » puis « Activer ».")
        key = self.key(scope, session_id)
        with self._lock:
            self._enabled.pop(key, None)
            if enabled:
                self._enabled[key] = True
                while len(self._enabled) > self.max_sessions:
                    self._enabled.popitem(last=False)
        self._log(key, enabled, provider)
        return self.status(scope, session_id)

    def _log(self, key: str, enabled: bool, provider: str | None) -> None:
        """Une ligne JSON par changement : jamais la question, une valeur ni l'identité en clair."""
        line = {"timestamp": datetime.now().isoformat(timespec="seconds"), "session": session_hash(key),
                "enabled": enabled, "provider": provider}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(line, ensure_ascii=False) + "\n")


def create_ask_mode_router(modes: UserDataModes) -> APIRouter:
    router = APIRouter(prefix="/api/ask", tags=["ask"], dependencies=[Depends(require_user)])

    def checked(session_id: str) -> str:
        if not SESSION.fullmatch(session_id or ""):
            raise HTTPException(status_code=400, detail="Session invalide : rechargez la page.")
        return session_id

    @router.get("/user-data-mode")
    def get_mode(session_id: str = Query(..., max_length=64),
                 scope: str = Depends(consent_scope)) -> dict[str, Any]:
        return modes.status(scope, checked(session_id))

    @router.post("/user-data-mode")
    def set_mode(payload: ModeRequest, scope: str = Depends(consent_scope)) -> dict[str, Any]:
        try:
            return modes.set(scope, checked(payload.session_id), payload.enabled, payload.consent)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router


__all__ = ["NO_KEY", "SWITCH_OFF", "UserDataModes", "consent_scope", "create_ask_mode_router", "session_hash"]
