"""Authentification FinOVA (base dédiée, indépendante de DuckDB).

Le paquet ne dépend d'aucun agent BI : il fournit des comptes, des sessions
JWT/refresh et des jetons d'invitation/réinitialisation à usage unique.
"""
from dashboard_app.auth.config import AuthSettings, load_settings
from dashboard_app.auth.deps import require_admin, require_user
from dashboard_app.auth.routes import create_auth_router
from dashboard_app.auth.service import AuthError, AuthService

__all__ = [
    "AuthError",
    "AuthService",
    "AuthSettings",
    "create_auth_router",
    "load_settings",
    "require_admin",
    "require_user",
]
