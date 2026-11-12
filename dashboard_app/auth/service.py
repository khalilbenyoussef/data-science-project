"""Règles métier d'authentification (aucune dépendance aux agents BI)."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import quote

import jwt

from dashboard_app.auth.config import AuthSettings
from dashboard_app.auth.db import AuthStore
from dashboard_app.auth.mailer import Mailer
from dashboard_app.auth.security import (
    access_token, constant_equals, decode_access_token, hash_password, hash_token,
    iso, new_secret, normalize_email, password_needs_rehash, password_problem,
    parse_iso, utcnow, validate_email, verify_password,
)

log = logging.getLogger(__name__)

ROLES = {"admin", "user"}
STATUSES = {"invited", "active", "disabled"}
INVALID_CREDENTIALS = "Identifiants invalides."


class AuthError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    csrf_token: str
    expires_in: int
    user: dict[str, Any]


def public_user(user: dict[str, Any] | None) -> dict[str, Any] | None:
    if user is None:
        return None
    return {
        key: user.get(key) for key in (
            "id", "email", "full_name", "role", "status", "email_verified",
            "created_at", "updated_at", "last_login_at", "password_changed_at",
        )
    }


class AuthService:
    def __init__(
        self, settings: AuthSettings, *, store: AuthStore | None = None,
        mailer: Mailer | None = None,
    ):
        self.settings = settings
        self.store = store or AuthStore(settings.db_path)
        self.mailer = mailer or Mailer(settings)

    # ------------------------------------------------------------- helpers
    def _now(self):
        return utcnow()

    def _audit(self, event: str, *, email: str | None = None, user_id: str | None = None,
               ip: str | None = None, user_agent: str | None = None,
               detail: str | None = None) -> None:
        self.store.log_event(
            at=iso(self._now()), event=event, email=email, user_id=user_id,
            ip=ip, user_agent=(user_agent or "")[:300] or None, detail=detail,
        )

    def _issue_session(self, user: dict[str, Any], *, user_agent: str, ip: str) -> SessionTokens:
        now = self._now()
        session_id = new_secret(12)
        refresh = f"{session_id}.{new_secret(32)}"
        csrf = new_secret(32)
        self.store.create_session(
            session_id=session_id, user_id=user["id"],
            refresh_hash=hash_token(refresh), csrf_hash=hash_token(csrf),
            created_at=iso(now),
            expires_at=iso(now + timedelta(seconds=self.settings.refresh_ttl_seconds)),
            user_agent=(user_agent or "")[:300], ip=(ip or "")[:80],
        )
        token, ttl = access_token(self.settings, user, session_id)
        return SessionTokens(token, refresh, csrf, ttl, public_user(user) or {})

    @staticmethod
    def _split_refresh(refresh: str | None) -> tuple[str, str] | None:
        if not refresh or "." not in refresh:
            return None
        session_id, secret = refresh.split(".", 1)
        if not session_id or not secret:
            return None
        return session_id, secret

    def _send(self, *, to: str, subject: str, text: str) -> bool:
        try:
            self.mailer.send(to=to, subject=subject, text=text)
            return True
        except Exception:  # SMTP indisponible : le parcours reste réessayable
            log.exception("envoi d'email impossible pour %s", to)
            return False

    def _invite_link(self, token: str) -> str:
        return f"{self.settings.public_url}/activate?token={quote(token)}"

    def _reset_link(self, token: str) -> str:
        return f"{self.settings.public_url}/reset-password?token={quote(token)}"

    def _send_invite(self, user: dict[str, Any], *, created_by: str | None) -> bool:
        now = self._now()
        self.store.invalidate_open_tokens(user["id"], "invite", used_at=iso(now))
        token = new_secret(32)
        self.store.create_token(
            user_id=user["id"], kind="invite", token_hash=hash_token(token),
            created_at=iso(now),
            expires_at=iso(now + timedelta(seconds=self.settings.invite_ttl_seconds)),
            created_by=created_by,
        )
        hours = max(1, self.settings.invite_ttl_seconds // 3600)
        text = (
            "Bonjour,\n\n"
            "Un compte vous a été créé sur FinOVA, la plateforme d'analyse de "
            "l'inclusion financière.\n\n"
            f"Activez votre compte et choisissez votre mot de passe :\n{self._invite_link(token)}\n\n"
            f"Ce lien est personnel, à usage unique et expire dans {hours} heures.\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\n"
            "— FinOVA\n"
        )
        return self._send(to=user["email"], subject="FinOVA — activez votre compte", text=text)

    # --------------------------------------------------------------- users
    def bootstrap_user(
        self, *, email: str, password: str | None, role: str = "admin",
        full_name: str = "", status: str = "active", email_verified: bool = True,
    ) -> dict[str, Any]:
        """Création/mise à jour directe réservée à la CLI et aux tests."""
        address = validate_email(email)
        if role not in ROLES:
            raise ValueError("rôle invalide")
        if status not in STATUSES:
            raise ValueError("statut invalide")
        digest = None
        if password:
            problem = password_problem(password, address)
            if problem:
                raise ValueError(problem)
            digest = hash_password(password)
        now = iso(self._now())
        existing = self.store.get_user_by_email(address)
        if existing is None:
            return self.store.create_user(
                email=address, full_name=(full_name or "").strip()[:120], role=role,
                password_hash=digest, status=status, email_verified=email_verified,
                created_at=now, updated_at=now,
            )
        fields: dict[str, Any] = {
            "full_name": (full_name or existing.get("full_name") or "").strip()[:120],
            "role": role, "status": status, "email_verified": email_verified,
        }
        if digest:
            fields.update(password_hash=digest, password_changed_at=now)
        return self.store.update_user(existing["id"], updated_at=now, **fields) or existing

    def login(self, *, email: str, password: str, user_agent: str = "", ip: str = "") -> SessionTokens:
        address = normalize_email(email)
        user = self.store.get_user_by_email(address) if address else None
        digest = user.get("password_hash") if user else None
        if not verify_password(digest, password or ""):
            self._audit("login_failed", email=address or None, ip=ip,
                        user_agent=user_agent, user_id=user["id"] if user else None)
            raise AuthError(401, INVALID_CREDENTIALS)
        if user is None or not user.get("email_verified"):
            self._audit("login_blocked_unverified", email=address, user_id=user["id"] if user else None,
                        ip=ip, user_agent=user_agent)
            raise AuthError(403, "Compte non activé : utilisez le lien d'invitation.")
        if user["status"] == "disabled":
            self._audit("login_blocked_disabled", email=address, user_id=user["id"],
                        ip=ip, user_agent=user_agent)
            raise AuthError(403, "Compte désactivé. Contactez un administrateur.")
        if user["status"] != "active":
            self._audit("login_blocked_inactive", email=address, user_id=user["id"],
                        ip=ip, user_agent=user_agent)
            raise AuthError(403, "Compte non activé : utilisez le lien d'invitation.")
        now = self._now()
        if digest and password_needs_rehash(digest):
            self.store.update_user(user["id"], updated_at=iso(now),
                                   password_hash=hash_password(password))
        self.store.update_user(user["id"], updated_at=iso(now), last_login_at=iso(now))
        fresh = self.store.get_user(user["id"]) or user
        tokens = self._issue_session(fresh, user_agent=user_agent, ip=ip)
        self._audit("login_success", email=address, user_id=user["id"], ip=ip,
                    user_agent=user_agent)
        return tokens

    def authenticate(self, token: str) -> dict[str, Any]:
        try:
            payload = decode_access_token(self.settings, token)
        except jwt.PyJWTError as exc:
            raise AuthError(401, "Session invalide ou expirée.") from exc
        session = self.store.get_session(str(payload.get("sid") or ""))
        now = self._now()
        if session is None or session.get("revoked_at"):
            raise AuthError(401, "Session révoquée.")
        try:
            if parse_iso(session["expires_at"]) <= now:
                raise AuthError(401, "Session expirée.")
        except (ValueError, TypeError) as exc:
            raise AuthError(401, "Session invalide.") from exc
        user = self.store.get_user(str(payload.get("sub") or ""))
        if user is None or user["status"] != "active" or not user.get("email_verified"):
            raise AuthError(401, "Compte inactif.")
        if user["id"] != session["user_id"]:
            raise AuthError(401, "Session invalide.")
        return public_user(user) or {}

    def refresh(self, *, refresh_cookie: str | None, csrf_header: str | None,
                user_agent: str = "", ip: str = "") -> SessionTokens:
        parts = self._split_refresh(refresh_cookie)
        if parts is None:
            raise AuthError(401, "Session absente.")
        session_id, secret = parts
        session = self.store.get_session(session_id)
        if session is None or session.get("revoked_at"):
            raise AuthError(401, "Session expirée.")
        now = self._now()
        try:
            expired = parse_iso(session["expires_at"]) <= now
        except (ValueError, TypeError):
            expired = True
        if expired:
            self.store.revoke_session(session_id, revoked_at=iso(now))
            raise AuthError(401, "Session expirée.")
        if not constant_equals(hash_token(f"{session_id}.{secret}"), session["refresh_hash"]):
            # Réutilisation d'un refresh déjà tourné : on révoque toute la session.
            self.store.revoke_session(session_id, revoked_at=iso(now))
            self._audit("refresh_reuse", user_id=session["user_id"], ip=ip,
                        user_agent=user_agent)
            raise AuthError(401, "Session expirée.")
        if not csrf_header or not constant_equals(hash_token(csrf_header), session["csrf_hash"]):
            raise AuthError(403, "Jeton CSRF invalide.")
        user = self.store.get_user(session["user_id"])
        if user is None or user["status"] != "active" or not user.get("email_verified"):
            self.store.revoke_session(session_id, revoked_at=iso(now))
            raise AuthError(401, "Compte inactif.")
        rotated = f"{session_id}.{new_secret(32)}"
        csrf = new_secret(32)
        self.store.rotate_session(
            session_id, refresh_hash=hash_token(rotated), csrf_hash=hash_token(csrf),
        )
        token, ttl = access_token(self.settings, user, session_id)
        return SessionTokens(token, rotated, csrf, ttl, public_user(user) or {})

    def logout(self, *, refresh_cookie: str | None, csrf_header: str | None,
               ip: str = "", user_agent: str = "") -> None:
        parts = self._split_refresh(refresh_cookie)
        if parts is None:
            return
        session_id, _secret = parts
        session = self.store.get_session(session_id)
        if session is None or session.get("revoked_at"):
            return
        if not csrf_header or not constant_equals(hash_token(csrf_header), session["csrf_hash"]):
            raise AuthError(403, "Jeton CSRF invalide.")
        self.store.revoke_session(session_id, revoked_at=iso(self._now()))
        self._audit("logout", user_id=session["user_id"], ip=ip, user_agent=user_agent)

    def invite_user(self, *, actor_id: str, email: str, full_name: str = "",
                    role: str = "user", ip: str = "", user_agent: str = "") -> dict[str, Any]:
        try:
            address = validate_email(email)
        except ValueError as exc:
            raise AuthError(422, str(exc)) from exc
        if role not in ROLES:
            raise AuthError(422, "Rôle invalide (admin ou user).")
        if self.store.get_user_by_email(address) is not None:
            raise AuthError(409, "Un compte existe déjà avec cette adresse email.")
        now = iso(self._now())
        user = self.store.create_user(
            email=address, full_name=(full_name or "").strip()[:120], role=role,
            password_hash=None, status="invited", email_verified=False,
            created_at=now, updated_at=now,
        )
        sent = self._send_invite(user, created_by=actor_id)
        self._audit("invitation_sent", email=address, user_id=user["id"], ip=ip,
                    user_agent=user_agent, detail="email_envoye" if sent else "email_non_envoye")
        result = public_user(user) or {}
        result["email_sent"] = sent
        return result

    def resend_invitation(self, *, actor_id: str, user_id: str) -> dict[str, Any]:
        user = self.store.get_user(user_id)
        if user is None:
            raise AuthError(404, "Utilisateur introuvable.")
        if user["status"] != "invited":
            raise AuthError(409, "Ce compte est déjà activé.")
        sent = self._send_invite(user, created_by=actor_id)
        self._audit("invitation_resent", email=user["email"], user_id=user["id"],
                    detail="email_envoye" if sent else "email_non_envoye")
        result = public_user(user) or {}
        result["email_sent"] = sent
        return result

    def activate(self, *, token: str, password: str, ip: str = "",
                 user_agent: str = "") -> dict[str, Any]:
        record = self.store.get_token_by_hash(hash_token(token or ""), "invite")
        now = self._now()
        if record is None or record.get("used_at") or parse_iso(record["expires_at"]) <= now:
            raise AuthError(400, "Lien d'activation invalide ou expiré.")
        user = self.store.get_user(record["user_id"])
        if user is None:
            raise AuthError(400, "Lien d'activation invalide ou expiré.")
        problem = password_problem(password, user["email"])
        if problem:
            raise AuthError(422, problem)
        if not self.store.consume_token(record["id"], used_at=iso(now)):
            raise AuthError(400, "Lien d'activation invalide ou expiré.")
        updated = self.store.update_user(
            user["id"], updated_at=iso(now), password_hash=hash_password(password),
            status="active", email_verified=True, password_changed_at=iso(now),
        )
        self.store.revoke_user_sessions(user["id"], revoked_at=iso(now))
        self._audit("account_activated", email=user["email"], user_id=user["id"], ip=ip,
                    user_agent=user_agent)
        return public_user(updated) or {}

    def forgot_password(self, *, email: str, ip: str = "", user_agent: str = "") -> bool:
        """Réponse toujours identique : aucune indication sur l'existence du compte.

        Retourne True uniquement si l'email a réellement été remis au serveur SMTP
        (ou écrit dans l'outbox locale) ; sert au CLI, jamais à l'API.
        """
        address = normalize_email(email)
        if not address:
            return False
        user = self.store.get_user_by_email(address)
        self._audit("password_forgot_requested", email=address,
                    user_id=user["id"] if user else None, ip=ip, user_agent=user_agent)
        if (user is None or user["status"] != "active" or not user.get("password_hash")
                or not user.get("email_verified")):
            return False
        now = self._now()
        self.store.invalidate_open_tokens(user["id"], "reset", used_at=iso(now))
        token = new_secret(32)
        self.store.create_token(
            user_id=user["id"], kind="reset", token_hash=hash_token(token),
            created_at=iso(now),
            expires_at=iso(now + timedelta(seconds=self.settings.reset_ttl_seconds)),
            created_by=None,
        )
        minutes = max(1, self.settings.reset_ttl_seconds // 60)
        text = (
            "Bonjour,\n\n"
            "Vous avez demandé la réinitialisation de votre mot de passe FinOVA.\n\n"
            f"Choisissez un nouveau mot de passe :\n{self._reset_link(token)}\n\n"
            f"Ce lien est personnel, à usage unique et expire dans {minutes} minutes.\n"
            "Après utilisation, toutes vos sessions seront déconnectées.\n"
            "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.\n\n"
            "— FinOVA\n"
        )
        sent = self._send(to=user["email"], subject="FinOVA — réinitialisation du mot de passe", text=text)
        self._audit("password_reset_sent", email=address, user_id=user["id"],
                    detail="email_envoye" if sent else "email_non_envoye")
        return sent

    def reset_password(self, *, token: str, password: str, ip: str = "",
                       user_agent: str = "") -> dict[str, Any]:
        record = self.store.get_token_by_hash(hash_token(token or ""), "reset")
        now = self._now()
        if record is None or record.get("used_at") or parse_iso(record["expires_at"]) <= now:
            raise AuthError(400, "Lien de réinitialisation invalide ou expiré.")
        user = self.store.get_user(record["user_id"])
        if user is None or user["status"] != "active":
            raise AuthError(400, "Lien de réinitialisation invalide ou expiré.")
        problem = password_problem(password, user["email"])
        if problem:
            raise AuthError(422, problem)
        if not self.store.consume_token(record["id"], used_at=iso(now)):
            raise AuthError(400, "Lien de réinitialisation invalide ou expiré.")
        self.store.invalidate_open_tokens(user["id"], "reset", used_at=iso(now))
        self.store.update_user(
            user["id"], updated_at=iso(now), password_hash=hash_password(password),
            password_changed_at=iso(now),
        )
        # Réinitialisation = révocation immédiate de toutes les sessions existantes.
        self.store.revoke_user_sessions(user["id"], revoked_at=iso(now))
        self._audit("password_reset_done", email=user["email"], user_id=user["id"], ip=ip,
                    user_agent=user_agent)
        return public_user(self.store.get_user(user["id"])) or {}

    # --------------------------------------------------------------- admin
    def list_users(self) -> list[dict[str, Any]]:
        return [public_user(user) or {} for user in self.store.list_users()]

    def update_user(self, *, actor_id: str, user_id: str, role: str | None = None,
                    status: str | None = None) -> dict[str, Any]:
        target = self.store.get_user(user_id)
        if target is None:
            raise AuthError(404, "Utilisateur introuvable.")
        if role is not None and role not in ROLES:
            raise AuthError(422, "Rôle invalide (admin ou user).")
        if status is not None and status not in {"active", "disabled"}:
            raise AuthError(422, "Statut invalide (active ou disabled).")
        if target["id"] == actor_id:
            if role is not None and role != target["role"]:
                raise AuthError(400, "Vous ne pouvez pas modifier votre propre rôle.")
            if status == "disabled":
                raise AuthError(400, "Vous ne pouvez pas désactiver votre propre compte.")
        losing_admin = (
            target["role"] == "admin" and target["status"] == "active"
            and (role == "user" or status == "disabled")
        )
        if losing_admin and self.store.count_active_admins() <= 1:
            raise AuthError(400, "Au moins un administrateur actif doit rester.")
        if status == "active" and not target.get("password_hash"):
            raise AuthError(400, "Le compte doit d'abord être activé par son titulaire.")
        fields: dict[str, Any] = {}
        if role is not None:
            fields["role"] = role
        if status is not None:
            fields["status"] = status
        if not fields:
            return public_user(target) or {}
        updated = self.store.update_user(user_id, updated_at=iso(self._now()), **fields)
        if status == "disabled":
            self.store.revoke_user_sessions(user_id, revoked_at=iso(self._now()))
        self._audit("admin_user_updated", email=target["email"], user_id=user_id,
                    detail=f"role={fields.get('role')} statut={fields.get('status')}")
        return public_user(updated) or {}

    def user_count(self) -> int:
        return len(self.store.list_users())

    def close(self) -> None:
        self.store.close()
