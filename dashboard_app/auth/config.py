"""Réglages d'authentification lus dans l'environnement (jamais dans config.yaml)."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

from biflow.config import resolve

DEFAULT_DB = "data/auth/auth.sqlite3"
DEFAULT_PUBLIC_URL = "http://127.0.0.1:8000"


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} doit être un entier (reçu : {raw!r})") from exc
    if value <= 0:
        raise ValueError(f"{name} doit être strictement positif")
    return value


def _env_bool(name: str, default: bool = False) -> bool:
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "oui"}


def _load_secret(db_path: Path) -> str:
    """Secret JWT : variable d'environnement sinon clé locale persistée (0600)."""
    configured = (os.getenv("BIFLOW_AUTH_SECRET") or "").strip()
    if configured:
        return configured
    key_file = db_path.parent / "jwt.key"
    try:
        existing = key_file.read_text(encoding="utf-8").strip()
    except OSError:
        existing = ""
    if existing:
        return existing
    generated = secrets.token_urlsafe(48)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_text(generated + "\n", encoding="utf-8")
    try:
        key_file.chmod(0o600)
    except OSError:
        pass
    return generated


@dataclass(frozen=True)
class AuthSettings:
    db_path: Path
    secret: str
    public_url: str = DEFAULT_PUBLIC_URL
    access_ttl_seconds: int = 15 * 60
    refresh_ttl_seconds: int = 30 * 24 * 3600
    invite_ttl_seconds: int = 7 * 24 * 3600
    reset_ttl_seconds: int = 15 * 60
    cookie_secure: bool = False
    issuer: str = "finova"
    audience: str = "finova-web"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "FinOVA <no-reply@finova.tn>"
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    outbox_dir: Path = field(default_factory=lambda: resolve("data/auth/outbox"))


def load_settings(db_path: str | Path | None = None) -> AuthSettings:
    path = resolve(db_path if db_path is not None else
                   (os.getenv("BIFLOW_AUTH_DB") or DEFAULT_DB))
    smtp_host = (os.getenv("SMTP_HOST") or "").strip() or None
    return AuthSettings(
        db_path=path,
        secret=_load_secret(path),
        public_url=(os.getenv("BIFLOW_PUBLIC_URL") or DEFAULT_PUBLIC_URL).rstrip("/"),
        access_ttl_seconds=_env_int("BIFLOW_ACCESS_TOKEN_MINUTES", 15) * 60,
        refresh_ttl_seconds=_env_int("BIFLOW_REFRESH_DAYS", 30) * 24 * 3600,
        invite_ttl_seconds=_env_int("BIFLOW_INVITE_HOURS", 7 * 24) * 3600,
        reset_ttl_seconds=_env_int("BIFLOW_RESET_MINUTES", 15) * 60,
        cookie_secure=_env_bool("BIFLOW_COOKIE_SECURE", False),
        smtp_host=smtp_host,
        smtp_port=_env_int("SMTP_PORT", 587),
        smtp_user=(os.getenv("SMTP_USER") or "").strip() or None,
        smtp_password=os.getenv("SMTP_PASSWORD") or None,
        smtp_from=(os.getenv("SMTP_FROM") or "FinOVA <no-reply@finova.tn>").strip(),
        smtp_starttls=_env_bool("SMTP_STARTTLS", True),
        smtp_ssl=_env_bool("SMTP_SSL", False),
        outbox_dir=resolve(os.getenv("BIFLOW_AUTH_OUTBOX") or "data/auth/outbox"),
    )
