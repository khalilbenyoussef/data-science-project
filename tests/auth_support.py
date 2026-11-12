"""Aides de test : créer un compte et ouvrir une session authentifiée."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

TEST_EMAIL = "test@finova.tn"
TEST_PASSWORD = "Fixtures2026!"


def authenticated_client(
    app: FastAPI, *, email: str = TEST_EMAIL, password: str = TEST_PASSWORD,
    role: str = "admin",
) -> TestClient:
    """Compte actif + jeton d'accès en en-tête (aucun contournement de l'API)."""
    app.state.auth.bootstrap_user(
        email=email, password=password, role=role, full_name="Compte de test",
    )
    client = TestClient(app)
    response = client.post(
        "/api/auth/login", json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    client.headers.update(
        {"Authorization": f"Bearer {response.json()['access_token']}"},
    )
    return client


def read_outbox_email(path) -> str:
    """Corps décodé d'un fichier .eml (quoted-printable / base64)."""
    from email import message_from_string

    message = message_from_string(path.read_text(encoding="utf-8"))
    payload = message.get_payload(decode=True)
    if payload is None:
        return path.read_text(encoding="utf-8")
    return payload.decode(message.get_content_charset() or "utf-8")


def token_from_email(path, route: str) -> str:
    """Extrait le jeton d'un lien /activate?token=... ou /reset-password?token=..."""
    import re
    from urllib.parse import unquote

    body = read_outbox_email(path)
    match = re.search(rf"{route}\?token=([A-Za-z0-9_%.=-]+)", body)
    assert match, body
    return unquote(match.group(1))
