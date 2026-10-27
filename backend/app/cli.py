"""Privileged maintenance through the VM console, never through a public endpoint."""

import argparse
import getpass

from email_validator import validate_email
from sqlalchemy import select, text

from app.core.security import PASSWORDS, utcnow
from app.db.database import SessionLocal
from app.models.accounts import User
from app.services.account_service import audit, revoke_sessions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-admin", "reset-mfa"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", default="Administrador CASA")
    args = parser.parse_args()
    email = validate_email(args.email, check_deliverability=False).normalized.casefold()
    with SessionLocal() as db:
        if db.bind.dialect.name == "postgresql":
            db.execute(text("SELECT pg_advisory_xact_lock(716201001)"))
        if args.command == "create-admin":
            if db.scalar(select(User.id).where(User.role == "admin")):
                parser.error(
                    "Já existe um administrador. Use o painel para convidar os demais."
                )
            password = getpass.getpass("Senha (mínimo 8 caracteres): ")
            if (
                len(password) < 8
                or len(password) > 128
                or password != getpass.getpass("Confirme a senha: ")
            ):
                parser.error("Senha inválida ou confirmação diferente.")
            user = User(
                email=email,
                name=args.name,
                role="admin",
                status="active",
                password_hash=PASSWORDS.hash(password),
                verified_at=utcnow(),
            )
            db.add(user)
            db.flush()
            audit(db, None, "cli.admin.created", user.id)
            db.commit()
            print(
                "Administrador criado. Entre no site para configurar o segundo fator."
            )
        else:
            user = db.scalar(select(User).where(User.email == email).with_for_update())
            if not user:
                parser.error("Conta não encontrada.")
            if input(f"Redefinir MFA de {email}? Digite REDEFINIR: ") != "REDEFINIR":
                return
            user.totp_enabled, user.totp_secret = False, None
            user.totp_last_step, user.recovery_hashes = -1, []
            revoke_sessions(db, user.id)
            audit(db, None, "cli.mfa.reset", user.id)
            db.commit()
            print("MFA redefinido. O próximo login exigirá nova configuração.")


if __name__ == "__main__":
    main()
