"""CLI d'administration des comptes FinOVA.

Exemples :
    python -m dashboard_app.auth.cli create-admin --email admin@finova.tn --name "Admin"
    python -m dashboard_app.auth.cli invite --email analyste@finova.tn --role user
    python -m dashboard_app.auth.cli list
    python -m dashboard_app.auth.cli disable --email analyste@finova.tn
    python -m dashboard_app.auth.cli reset --email analyste@finova.tn
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

from dashboard_app.auth.config import load_settings
from dashboard_app.auth.service import AuthService


def _password(args) -> str:
    value = args.password or os.getenv("BIFLOW_AUTH_PASSWORD")
    if value:
        return value
    first = getpass.getpass("Mot de passe : ")
    second = getpass.getpass("Confirmer le mot de passe : ")
    if first != second:
        raise SystemExit("Les mots de passe ne correspondent pas.")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="finova-auth", description="Comptes FinOVA")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-admin", help="créer ou réinitialiser un administrateur")
    create.add_argument("--email", required=True)
    create.add_argument("--name", default="")
    create.add_argument("--password", default=None, help="préférer BIFLOW_AUTH_PASSWORD")
    create.add_argument("--user", action="store_true", help="créer un rôle user")

    invite = sub.add_parser("invite", help="inviter un utilisateur par email")
    invite.add_argument("--email", required=True)
    invite.add_argument("--name", default="")
    invite.add_argument("--role", choices=["admin", "user"], default="user")

    reset = sub.add_parser("reset", help="envoyer un lien de réinitialisation")
    reset.add_argument("--email", required=True)

    disable = sub.add_parser("disable", help="désactiver un compte")
    disable.add_argument("--email", required=True)
    enable = sub.add_parser("enable", help="réactiver un compte déjà activé")
    enable.add_argument("--email", required=True)

    sub.add_parser("list", help="lister les comptes")

    args = parser.parse_args(argv)
    service = AuthService(load_settings())
    try:
        if args.command == "create-admin":
            user = service.bootstrap_user(
                email=args.email, password=_password(args),
                role="user" if args.user else "admin", full_name=args.name,
            )
            print(f"Compte prêt : {user['email']} ({user['role']}, {user['status']})")
            return 0
        if args.command == "invite":
            user = service.invite_user(
                actor_id="cli", email=args.email, full_name=args.name, role=args.role,
            )
            print(f"Invitation {'envoyée' if user.get('email_sent') else 'créée (email non envoyé)'}"
                  f" pour {user['email']}.")
            return 0
        if args.command == "reset":
            settings = service.settings
            smtp_ready = bool(settings.smtp_host) and (
                not settings.smtp_user or bool(settings.smtp_password)
            )
            sent = service.forgot_password(email=args.email)
            if sent and smtp_ready:
                print(f"Email de réinitialisation envoyé via {settings.smtp_host} "
                      f"à {args.email}.")
                return 0
            if sent:
                print("SMTP incomplet ou non configuré : l'email a seulement été écrit "
                      f"dans {settings.outbox_dir} (aucune remise réelle).")
                return 1
            if smtp_ready:
                print("Échec de l'envoi : l'email N'A PAS été envoyé (identifiants SMTP "
                      "refusés ou serveur injoignable), ou le compte est inactif/inconnu.")
                print("Vérifiez SMTP_USER / SMTP_PASSWORD dans .env — Gmail exige un "
                      "mot de passe d'application, pas le mot de passe du compte.")
            else:
                print("SMTP incomplet : SMTP_PASSWORD est vide, l'email N'A PAS été envoyé.")
                print(f"Repli local : {settings.outbox_dir}")
            return 1
        if args.command in {"disable", "enable"}:
            target = service.store.get_user_by_email(args.email.strip().lower())
            if target is None:
                print("Utilisateur introuvable.", file=sys.stderr)
                return 1
            if args.command == "disable":
                service.update_user(actor_id="cli", user_id=target["id"], status="disabled")
            else:
                service.update_user(actor_id="cli", user_id=target["id"], status="active")
            print(f"{target['email']} : {args.command}d")
            return 0
        if args.command == "list":
            users = service.list_users()
            print(f"{len(users)} compte(s)")
            for user in users:
                print(f"- {user['email']:<40} {user['role']:<6} {user['status']:<9}"
                      f" vérifié={user['email_verified']}")
            return 0
    finally:
        service.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
