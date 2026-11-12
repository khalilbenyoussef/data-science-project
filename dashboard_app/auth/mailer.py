"""Envoi des emails d'invitation et de réinitialisation (SMTP ou outbox locale)."""
from __future__ import annotations

import logging
import re
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from dashboard_app.auth.config import AuthSettings

log = logging.getLogger(__name__)


class Mailer:
    """SMTP si configuré ; sinon écriture d'un fichier .eml dans l'outbox locale.

    Le repli outbox permet un déploiement local/démonstration sans serveur mail ;
    il ne remplace jamais SMTP dès que ``SMTP_HOST`` est renseigné.
    """

    def __init__(self, settings: AuthSettings):
        self.settings = settings
        self.outbox = Path(settings.outbox_dir)

    def send(self, *, to: str, subject: str, text: str) -> None:
        message = EmailMessage()
        message["From"] = self.settings.smtp_from
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
        message.set_content(text)
        # Un SMTP a moitie configure (hote sans mot de passe) ne doit pas casser
        # les invitations : on reste alors sur l'outbox locale.
        configured = bool(self.settings.smtp_host) and (
            not self.settings.smtp_user or bool(self.settings.smtp_password)
        )
        if configured:
            self._send_smtp(message)
        else:
            if self.settings.smtp_host:
                log.warning(
                    "SMTP incomplet (SMTP_PASSWORD vide) : email pour %s ecrit dans l'outbox",
                    message["To"],
                )
            self._write_outbox(message, text)

    def _send_smtp(self, message: EmailMessage) -> None:
        settings = self.settings
        context = ssl.create_default_context()
        if settings.smtp_ssl:
            server: smtplib.SMTP = smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, timeout=20, context=context,
            )
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20)
        try:
            server.ehlo()
            if settings.smtp_starttls and not settings.smtp_ssl:
                server.starttls(context=context)
                server.ehlo()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password or "")
            server.send_message(message)
        finally:
            try:
                server.quit()
            except smtplib.SMTPException:
                server.close()

    def _write_outbox(self, message: EmailMessage, text: str) -> None:
        self.outbox.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        slug = re.sub(r"[^a-z0-9]+", "-", message["To"].lower()).strip("-")[:60]
        path = self.outbox / f"{stamp}-{slug}.eml"
        path.write_text(message.as_string(), encoding="utf-8")
        log.warning(
            "SMTP non configuré : email pour %s écrit dans %s (sujet : %s)",
            message["To"], path, message["Subject"],
        )
        # Le lien reste visible dans les journaux du serveur pour la démonstration.
        for line in text.splitlines():
            if line.startswith("http://") or line.startswith("https://"):
                log.warning("lien de démonstration : %s", line.strip())
