"""Parcours d'authentification FinOVA : connexion, invitations, reset, RBAC."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from auth_support import token_from_email
from dashboard_app.api.app import create_app

ADMIN_EMAIL = "admin@finova.tn"
ADMIN_PASSWORD = "RootPass2026!"
MEMBER_EMAIL = "member@finova.tn"
MEMBER_PASSWORD = "Access2026Secure!"


def _spec() -> dict:
    return {
        "schema_version": "2.0", "generated_at": "2026-10-29T12:00:00",
        "run_id": "auth_test", "country": {"iso3": "TUN", "name": "Tunisie"},
        "year": 2024,
        "pages": [{"id": "overview", "title": "Vue d'ensemble", "metrics": [],
                   "charts": [], "insights": [], "blocks": [], "notices": []}],
        "facts": [], "notices": [], "publication_status": "not_evaluated",
    }


@pytest.fixture()
def auth_app(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BIFLOW_AUTH_OUTBOX", str(tmp_path / "outbox"))
    spec_path = tmp_path / "finova.json"
    spec_path.write_text(json.dumps(_spec()), encoding="utf-8")
    app = create_app(
        spec_path=spec_path, warehouse_path=tmp_path / "missing.duckdb",
        reports_dir=tmp_path / "reports", history_dir=tmp_path / "history",
        web_dist=tmp_path / "dist", spec_builder=lambda iso3, year: _spec(),
        auth_db=tmp_path / "auth.sqlite3",
    )
    app.state.auth.bootstrap_user(
        email=ADMIN_EMAIL, password=ADMIN_PASSWORD, role="admin",
        full_name="Administrateur",
    )
    return app


def _client(app) -> TestClient:
    return TestClient(app)


def _login(client: TestClient, email: str = ADMIN_EMAIL,
           password: str = ADMIN_PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _headers(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _admin(app) -> TestClient:
    client = _client(app)
    response = _login(client)
    assert response.status_code == 200, response.text
    client.headers.update(_headers(response))
    return client


def _db(app) -> Path:
    return app.state.auth.settings.db_path


def _outbox(app) -> Path:
    return app.state.auth.settings.outbox_dir


def _latest_mail(app) -> Path:
    files = sorted(_outbox(app).glob("*.eml"))
    assert files, "aucun email écrit dans l'outbox"
    return files[-1]


def _expire_token(app, kind: str) -> None:
    with sqlite3.connect(_db(app)) as con:
        con.execute(
            "UPDATE tokens SET expires_at = ? WHERE kind = ? AND used_at IS NULL",
            ("2000-01-01T00:00:00+00:00", kind),
        )


def test_protected_api_requires_a_valid_session(auth_app):
    client = _client(auth_app)
    for method, path in (
        ("get", "/api/health"), ("get", "/api/spec"), ("get", "/api/runs"),
        ("get", "/api/audit/summary"), ("get", "/api/sources"),
        ("get", "/api/sources/comparable-kpis"),
        ("get", "/api/recommendations?iso3=TUN&year=2024"),
        ("get", "/api/pipeline/agents"),
        ("get", "/api/reports/insights.pdf?iso3=TUN&year=2024"),
        ("get", "/api/auth/me"),
    ):
        assert getattr(client, method)(path).status_code == 401, path
    assert client.post("/api/ask", json={"question": "Compte ?"}).status_code == 401
    bogus = {"Authorization": "Bearer not-a-token"}
    assert client.get("/api/spec", headers=bogus).status_code == 401

    response = _login(client)
    assert response.status_code == 200
    headers = _headers(response)
    assert client.get("/api/spec", headers=headers).status_code == 200
    assert client.get("/api/health", headers=headers).json()["status"] == "ok"
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["user"]["email"] == ADMIN_EMAIL and me["is_admin"] is True


def test_login_rejects_unknown_wrong_disabled_and_invited(auth_app):
    client = _client(auth_app)
    unknown = _login(client, "nobody@finova.tn", "Whatever2026!")
    wrong = _login(client, ADMIN_EMAIL, "WrongPass2026!")
    assert unknown.status_code == 401 and wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]  # pas d'énumération

    auth_app.state.auth.bootstrap_user(
        email="blocked@finova.tn", password="Locked2026Now!", role="user",
        status="disabled",
    )
    disabled = _login(client, "blocked@finova.tn", "Locked2026Now!")
    assert disabled.status_code == 403 and "désactivé" in disabled.json()["detail"].lower()

    invited = auth_app.state.auth.invite_user(
        actor_id="test", email="invited@finova.tn", role="user",
    )
    assert invited["status"] == "invited"
    assert _login(client, "invited@finova.tn", "Anything2026!").status_code == 401

    # Le mot de passe n'est jamais stocké en clair et utilise Argon2id.
    with sqlite3.connect(_db(auth_app)) as con:
        digest = con.execute(
            "SELECT password_hash FROM users WHERE email = ?", (ADMIN_EMAIL,),
        ).fetchone()[0]
    assert digest.startswith("$argon2id$") and ADMIN_PASSWORD not in digest


def test_login_issues_secure_cookies_and_access_token(auth_app):
    client = _client(auth_app)
    response = _login(client)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] > 0
    assert body["user"]["email"] == ADMIN_EMAIL
    assert "finova_refresh" in client.cookies and "finova_csrf" in client.cookies

    cookies = response.headers.get_list("set-cookie")
    refresh = next(item for item in cookies if item.startswith("finova_refresh="))
    csrf = next(item for item in cookies if item.startswith("finova_csrf="))
    assert "HttpOnly" in refresh and "samesite=strict" in refresh.lower()
    assert "Path=/api/auth" in refresh
    assert "HttpOnly" not in csrf

    payload = jwt.decode(body["access_token"], options={"verify_signature": False})
    assert payload["sub"] and payload["sid"] and payload["role"] == "admin"
    assert payload["exp"] > payload["iat"]


def test_admin_invitation_activation_and_single_use(auth_app):
    admin = _admin(auth_app)
    response = admin.post("/api/auth/admin/users", json={
        "email": MEMBER_EMAIL, "full_name": "Membre", "role": "user",
    })
    assert response.status_code == 201, response.text
    created = response.json()["user"]
    assert created["status"] == "invited" and created["email_verified"] is False
    assert created["email_sent"] is True

    token = token_from_email(_latest_mail(auth_app), "/activate")
    public = _client(auth_app)
    weak = public.post("/api/auth/activate", json={"token": token, "password": "short"})
    assert weak.status_code == 422
    activated = public.post("/api/auth/activate", json={
        "token": token, "password": MEMBER_PASSWORD,
    })
    assert activated.status_code == 200, activated.text
    assert activated.json()["user"]["status"] == "active"
    reused = public.post("/api/auth/activate", json={
        "token": token, "password": MEMBER_PASSWORD,
    })
    assert reused.status_code == 400

    logged = _login(public, MEMBER_EMAIL, MEMBER_PASSWORD)
    assert logged.status_code == 200 and logged.json()["user"]["role"] == "user"
    users = admin.get("/api/auth/admin/users")
    assert users.status_code == 200 and users.json()["count"] == 2


def test_invitation_token_expires(auth_app):
    admin = _admin(auth_app)
    admin.post("/api/auth/admin/users", json={"email": MEMBER_EMAIL, "role": "user"})
    token = token_from_email(_latest_mail(auth_app), "/activate")
    assert (auth_app.state.auth.settings.invite_ttl_seconds
            == 7 * 24 * 3600)
    _expire_token(auth_app, "invite")
    response = _client(auth_app).post("/api/auth/activate", json={
        "token": token, "password": MEMBER_PASSWORD,
    })
    assert response.status_code == 400


def test_forgot_password_is_generic_and_reset_revokes_sessions(auth_app):
    auth_app.state.auth.bootstrap_user(
        email=MEMBER_EMAIL, password=MEMBER_PASSWORD, role="user",
    )
    user = _client(auth_app)
    session = _login(user, MEMBER_EMAIL, MEMBER_PASSWORD)
    headers = _headers(session)
    refresh_cookie = user.cookies.get("finova_refresh")
    mail_count = len(list(_outbox(auth_app).glob("*.eml")))

    generic = _client(auth_app).post("/api/auth/forgot-password", json={
        "email": "unknown@finova.tn",
    })
    assert generic.status_code == 202
    assert len(list(_outbox(auth_app).glob("*.eml"))) == mail_count

    known = _client(auth_app).post("/api/auth/forgot-password", json={
        "email": MEMBER_EMAIL,
    })
    assert known.status_code == 202
    assert known.json() == generic.json()  # même réponse, que le compte existe ou non
    assert len(list(_outbox(auth_app).glob("*.eml"))) == mail_count + 1
    token = token_from_email(_latest_mail(auth_app), "/reset-password")

    reset = _client(auth_app).post("/api/auth/reset-password", json={
        "token": token, "password": "NewSecret2026!",
    })
    assert reset.status_code == 200, reset.text
    assert reset.json()["message"].startswith("Mot de passe réinitialisé")

    # Sessions existantes révoquées immédiatement.
    assert user.get("/api/auth/me", headers=headers).status_code == 401
    replay_refresh = user.post("/api/auth/refresh", headers={
        "X-CSRF-Token": user.cookies.get("finova_csrf") or "",
    })
    assert replay_refresh.status_code == 401
    assert refresh_cookie

    assert _login(_client(auth_app), MEMBER_EMAIL, MEMBER_PASSWORD).status_code == 401
    assert _login(_client(auth_app), MEMBER_EMAIL, "NewSecret2026!").status_code == 200

    reused = _client(auth_app).post("/api/auth/reset-password", json={
        "token": token, "password": "Another2026Secret!",
    })
    assert reused.status_code == 400


def test_reset_token_expires_after_fifteen_minutes(auth_app):
    auth_app.state.auth.bootstrap_user(
        email=MEMBER_EMAIL, password=MEMBER_PASSWORD, role="user",
    )
    client = _client(auth_app)
    client.post("/api/auth/forgot-password", json={"email": MEMBER_EMAIL})
    assert auth_app.state.auth.settings.reset_ttl_seconds == 15 * 60
    token = token_from_email(_latest_mail(auth_app), "/reset-password")
    _expire_token(auth_app, "reset")
    response = client.post("/api/auth/reset-password", json={
        "token": token, "password": "NewSecret2026!",
    })
    assert response.status_code == 400


def test_refresh_requires_csrf_and_rotates_the_token(auth_app):
    client = _client(auth_app)
    first = _login(client)
    old_refresh = client.cookies.get("finova_refresh")
    old_csrf = client.cookies.get("finova_csrf")

    assert client.post("/api/auth/refresh").status_code == 403
    rotated = client.post("/api/auth/refresh", headers={"X-CSRF-Token": old_csrf or ""})
    assert rotated.status_code == 200, rotated.text
    assert client.cookies.get("finova_refresh") != old_refresh
    assert client.cookies.get("finova_csrf") != old_csrf
    new_headers = _headers(rotated)
    assert client.get("/api/auth/me", headers=new_headers).status_code == 200
    assert old_refresh and first.status_code == 200

    # Rejeu de l'ancien refresh : la session entière est révoquée.
    replay_client = _client(auth_app)
    replay_client.cookies.set("finova_refresh", old_refresh, path="/api/auth")
    replay_client.cookies.set("finova_csrf", old_csrf or "", path="/")
    replay = replay_client.post("/api/auth/refresh", headers={"X-CSRF-Token": old_csrf or ""})
    assert replay.status_code == 401
    assert client.get("/api/auth/me", headers=new_headers).status_code == 401


def test_logout_requires_csrf_and_invalidates_the_session(auth_app):
    client = _client(auth_app)
    session = _login(client)
    headers = _headers(session)
    csrf = client.cookies.get("finova_csrf") or ""
    refresh = client.cookies.get("finova_refresh") or ""

    assert client.post("/api/auth/logout", headers=headers).status_code == 403
    assert client.post("/api/auth/logout", headers={
        **headers, "X-CSRF-Token": csrf,
    }).status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401

    # Le refresh cookie a été effacé et la session révoquée côté serveur.
    assert client.cookies.get("finova_refresh") is None
    client.cookies.set("finova_refresh", refresh, path="/api/auth")
    client.cookies.set("finova_csrf", csrf, path="/")
    assert client.post("/api/auth/refresh", headers={
        "X-CSRF-Token": csrf,
    }).status_code == 401


def test_rbac_admin_only_and_deactivation_revokes_access(auth_app):
    member = auth_app.state.auth.bootstrap_user(
        email=MEMBER_EMAIL, password=MEMBER_PASSWORD, role="user",
    )
    user_client = _client(auth_app)
    user_session = _login(user_client, MEMBER_EMAIL, MEMBER_PASSWORD)
    user_headers = _headers(user_session)

    assert user_client.get("/api/auth/admin/users", headers=user_headers).status_code == 403
    assert user_client.post("/api/auth/admin/users", headers=user_headers, json={
        "email": "other@finova.tn", "role": "user",
    }).status_code == 403
    assert user_client.patch(
        f"/api/auth/admin/users/{member['id']}", headers=user_headers,
        json={"role": "admin"},
    ).status_code == 403

    admin = _admin(auth_app)
    disabled = admin.patch(f"/api/auth/admin/users/{member['id']}", json={
        "status": "disabled",
    })
    assert disabled.status_code == 200
    assert disabled.json()["user"]["status"] == "disabled"
    assert user_client.get("/api/auth/me", headers=user_headers).status_code == 401
    assert _login(_client(auth_app), MEMBER_EMAIL, MEMBER_PASSWORD).status_code == 403

    enabled = admin.patch(f"/api/auth/admin/users/{member['id']}", json={
        "status": "active",
    })
    assert enabled.status_code == 200
    assert _login(_client(auth_app), MEMBER_EMAIL, MEMBER_PASSWORD).status_code == 200

    own = _login(_client(auth_app))
    own_headers = _headers(own)
    me = _client(auth_app).get("/api/auth/me", headers=own_headers).json()["user"]
    assert admin.patch(f"/api/auth/admin/users/{me['id']}", json={
        "role": "user",
    }).status_code == 400
    assert admin.patch(f"/api/auth/admin/users/{me['id']}", json={
        "status": "disabled",
    }).status_code == 400


def test_admin_can_resend_invitation_and_duplicate_email_is_refused(auth_app):
    admin = _admin(auth_app)
    created = admin.post("/api/auth/admin/users", json={
        "email": MEMBER_EMAIL, "role": "user",
    })
    assert created.status_code == 201
    duplicate = admin.post("/api/auth/admin/users", json={
        "email": MEMBER_EMAIL, "role": "admin",
    })
    assert duplicate.status_code == 409
    user_id = created.json()["user"]["id"]
    mails = len(list(_outbox(auth_app).glob("*.eml")))
    resent = admin.post(f"/api/auth/admin/users/{user_id}/resend-invitation")
    assert resent.status_code == 200 and resent.json()["user"]["email_sent"] is True
    assert len(list(_outbox(auth_app).glob("*.eml"))) == mails + 1


def test_spa_routes_serve_the_front_shell(auth_app, tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    app = create_app(
        spec_path=tmp_path / "finova.json", warehouse_path=tmp_path / "w.duckdb",
        reports_dir=tmp_path / "reports", history_dir=tmp_path / "history",
        web_dist=dist, spec_builder=lambda iso3, year: _spec(),
        auth_db=tmp_path / "auth2.sqlite3",
    )
    client = _client(app)
    for path in ("/login", "/forgot-password", "/reset-password", "/activate",
                 "/admin/users"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert "id=root" in response.text
    assert client.get("/api/spec").status_code == 401
