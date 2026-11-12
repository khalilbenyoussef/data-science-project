"""Dépendances FastAPI : utilisateur authentifié et contrôle de rôle."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request

from dashboard_app.auth.service import AuthError, AuthService


def _service(request: Request) -> AuthService:
    service = getattr(request.app.state, "auth", None)
    if service is None:  # ne devrait pas arriver : create_app installe le service
        raise HTTPException(status_code=503, detail="Authentification non configurée.")
    return service


def _bearer(request: Request) -> str:
    header = request.headers.get("Authorization") or ""
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401, detail="Authentification requise.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def require_user(request: Request) -> dict[str, Any]:
    service = _service(request)
    try:
        user = service.authenticate(_bearer(request))
    except AuthError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    request.state.user = user
    return user


def require_admin(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux administrateurs.")
    return user
