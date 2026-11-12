"""Routeur HTTP d'authentification (`/api/auth`)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dashboard_app.auth.config import AuthSettings
from dashboard_app.auth.deps import require_admin, require_user
from dashboard_app.auth.service import AuthError, AuthService, SessionTokens

REFRESH_COOKIE = "finova_refresh"
CSRF_COOKIE = "finova_csrf"
REFRESH_PATH = "/api/auth"
CSRF_HEADER = "X-CSRF-Token"
COOKIE_SAMESITE = "strict"


class LoginBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)


class ForgotBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class TokenPasswordBody(BaseModel):
    token: str = Field(min_length=10, max_length=512)
    password: str = Field(min_length=1, max_length=256)


class InviteBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    full_name: str = Field(default="", max_length=120)
    role: str = Field(default="user", pattern="^(admin|user)$")


class UpdateUserBody(BaseModel):
    role: str | None = Field(default=None, pattern="^(admin|user)$")
    status: str | None = Field(default=None, pattern="^(active|disabled)$")


def _execute(call, *args, **kwargs):
    try:
        return call(*args, **kwargs)
    except AuthError as exc:
        raise _http_error(exc) from exc


def _http_error(exc: AuthError):
    from fastapi import HTTPException
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _profile(request: Request) -> tuple[str, str]:
    ip = request.client.host if request.client else ""
    return (request.headers.get("user-agent") or "")[:300], ip[:80]


def _session_payload(tokens: SessionTokens) -> dict[str, Any]:
    return {
        "access_token": tokens.access_token,
        "token_type": "bearer",
        "expires_in": tokens.expires_in,
        "user": tokens.user,
    }


def _set_cookies(response: Response, tokens: SessionTokens, settings: AuthSettings) -> None:
    max_age = settings.refresh_ttl_seconds
    response.set_cookie(
        REFRESH_COOKIE, tokens.refresh_token, max_age=max_age,
        httponly=True, samesite=COOKIE_SAMESITE, secure=settings.cookie_secure,
        path=REFRESH_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE, tokens.csrf_token, max_age=max_age,
        httponly=False, samesite=COOKIE_SAMESITE, secure=settings.cookie_secure,
        path="/",
    )


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH, samesite=COOKIE_SAMESITE)
    response.delete_cookie(CSRF_COOKIE, path="/", samesite=COOKIE_SAMESITE)


def create_auth_router(service: AuthService) -> APIRouter:
    settings = service.settings
    router = APIRouter(prefix="/api/auth", tags=["authentification"])

    @router.post("/login")
    def login(body: LoginBody, request: Request, response: Response) -> dict[str, Any]:
        agent, ip = _profile(request)
        tokens = _execute(
            service.login, email=body.email, password=body.password,
            user_agent=agent, ip=ip,
        )
        _set_cookies(response, tokens, settings)
        return _session_payload(tokens)

    @router.post("/refresh")
    def refresh(request: Request, response: Response) -> dict[str, Any]:
        agent, ip = _profile(request)
        tokens = _execute(
            service.refresh,
            refresh_cookie=request.cookies.get(REFRESH_COOKIE),
            csrf_header=request.headers.get(CSRF_HEADER),
            user_agent=agent, ip=ip,
        )
        _set_cookies(response, tokens, settings)
        return _session_payload(tokens)

    @router.post("/logout")
    def logout(request: Request) -> Response:
        agent, ip = _profile(request)
        try:
            service.logout(
                refresh_cookie=request.cookies.get(REFRESH_COOKIE),
                csrf_header=request.headers.get(CSRF_HEADER),
                user_agent=agent, ip=ip,
            )
        except AuthError as exc:
            raise _http_error(exc) from exc
        response = Response(status_code=204)
        _clear_cookies(response)
        return response

    @router.get("/me")
    def me(user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
        return {"user": user, "is_admin": user.get("role") == "admin"}

    @router.post("/forgot-password", status_code=202)
    def forgot_password(body: ForgotBody, request: Request) -> dict[str, Any]:
        agent, ip = _profile(request)
        service.forgot_password(email=body.email, ip=ip, user_agent=agent)
        # Message constant : impossible de savoir si l'adresse existe.
        return {
            "message": "Si un compte correspond à cette adresse, un lien de "
                       "réinitialisation vient d'être envoyé.",
        }

    @router.post("/reset-password")
    def reset_password(body: TokenPasswordBody, request: Request) -> dict[str, Any]:
        agent, ip = _profile(request)
        user = _execute(
            service.reset_password, token=body.token, password=body.password,
            ip=ip, user_agent=agent,
        )
        return {
            "message": "Mot de passe réinitialisé. Toutes les sessions ont été déconnectées.",
            "user": user,
        }

    @router.post("/activate")
    def activate(body: TokenPasswordBody, request: Request) -> dict[str, Any]:
        agent, ip = _profile(request)
        user = _execute(
            service.activate, token=body.token, password=body.password,
            ip=ip, user_agent=agent,
        )
        return {"message": "Compte activé. Vous pouvez maintenant vous connecter.", "user": user}

    # ------------------------------------------------------------- admin
    @router.get("/admin/users")
    def admin_users(admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
        del admin
        return {"users": service.list_users(), "count": service.user_count()}

    @router.post("/admin/users", status_code=201)
    def admin_create_user(
        body: InviteBody, request: Request,
        admin: dict[str, Any] = Depends(require_admin),
    ) -> JSONResponse:
        agent, ip = _profile(request)
        user = _execute(
            service.invite_user, actor_id=admin["id"], email=body.email,
            full_name=body.full_name, role=body.role, ip=ip, user_agent=agent,
        )
        return JSONResponse(status_code=201, content={"user": user})

    @router.post("/admin/users/{user_id}/resend-invitation")
    def admin_resend(user_id: str, admin: dict[str, Any] = Depends(require_admin)) -> dict[str, Any]:
        user = _execute(service.resend_invitation, actor_id=admin["id"], user_id=user_id)
        return {"user": user}

    @router.patch("/admin/users/{user_id}")
    def admin_update(
        user_id: str, body: UpdateUserBody,
        admin: dict[str, Any] = Depends(require_admin),
    ) -> dict[str, Any]:
        if body.role is None and body.status is None:
            return {"user": next(
                (item for item in service.list_users() if item["id"] == user_id), None,
            )}
        user = _execute(
            service.update_user, actor_id=admin["id"], user_id=user_id,
            role=body.role, status=body.status,
        )
        return {"user": user}

    return router
