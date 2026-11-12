"""Primitives de sécurité : Argon2id, jetons opaques, JWT HS256."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from dashboard_app.auth.config import AuthSettings

# Paramètres OWASP 2024 pour Argon2id (mémoire 64 Mio, 3 passes).
_hasher = PasswordHasher(
    time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16,
)
# Hachage factice : égalise le coût d'un email inconnu et limite l'énumération.
_dummy_hash: str | None = None
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")

PASSWORD_MIN = 10
PASSWORD_MAX = 128


class PasswordPolicyError(ValueError):
    pass


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_email(email: str) -> str:
    value = normalize_email(email)
    if not value or len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("Adresse email invalide.")
    return value


def password_problem(password: str, email: str | None = None) -> str | None:
    """Règle de mot de passe ; retourne un message français ou None."""
    if not isinstance(password, str) or len(password) < PASSWORD_MIN:
        return f"Le mot de passe doit contenir au moins {PASSWORD_MIN} caractères."
    if len(password) > PASSWORD_MAX:
        return f"Le mot de passe ne peut pas dépasser {PASSWORD_MAX} caractères."
    if password.strip() != password:
        return "Le mot de passe ne doit pas commencer ou finir par un espace."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        return "Le mot de passe doit contenir au moins une lettre et un chiffre."
    if email:
        local = normalize_email(email).split("@", 1)[0]
        if local and len(local) >= 4 and local in password.lower():
            return "Le mot de passe ne doit pas contenir l'adresse email."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    global _dummy_hash
    if not password_hash:
        if _dummy_hash is None:
            _dummy_hash = _hasher.hash(secrets.token_urlsafe(24))
        try:
            _hasher.verify(_dummy_hash, password or "")
        except (VerificationError, VerifyMismatchError, InvalidHashError):
            pass
        return False
    try:
        return _hasher.verify(password_hash, password or "")
    except (VerificationError, VerifyMismatchError, InvalidHashError, TypeError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, TypeError):
        return True


def new_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def constant_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def access_token(settings: AuthSettings, user: Mapping[str, Any], session_id: str) -> tuple[str, int]:
    now = utcnow()
    expires = now + timedelta(seconds=settings.access_ttl_seconds)
    payload = {
        "sub": user["id"],
        "sid": session_id,
        "role": user["role"],
        "email": user["email"],
        "typ": "access",
        "iss": settings.issuer,
        "aud": settings.audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": secrets.token_hex(8),
    }
    token = jwt.encode(payload, settings.secret, algorithm="HS256")
    return token, settings.access_ttl_seconds


def decode_access_token(settings: AuthSettings, token: str) -> dict[str, Any]:
    payload = jwt.decode(
        token,
        settings.secret,
        algorithms=["HS256"],
        audience=settings.audience,
        issuer=settings.issuer,
        options={"require": ["exp", "iat", "sub", "sid", "iss", "aud"]},
    )
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("type de jeton inattendu")
    return payload
