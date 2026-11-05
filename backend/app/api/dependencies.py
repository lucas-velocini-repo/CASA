import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import APP_URL, COOKIE, aware, digest, utcnow
from app.db.database import get_db
from app.models.accounts import User, UserSession


@dataclass
class Identity:
    user: User
    session: UserSession


def check_origin(request):
    if request.headers.get("origin") != APP_URL:
        raise HTTPException(403, "Origem da requisição não autorizada.")


def get_identity(request: Request, db: Session = Depends(get_db)):
    authorization = request.headers.get("authorization", "")
    bearer = authorization.startswith("Bearer ")
    token = authorization[7:] if bearer else request.cookies.get(COOKIE)
    if not token or len(token) > 128:
        raise HTTPException(401, "Entre na sua conta.")
    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == digest(token))
    )
    if not session or session.revoked_at or aware(session.expires_at) <= utcnow():
        raise HTTPException(401, "Sua sessão expirou. Entre novamente.")
    if session.client != ("mobile" if bearer else "web"):
        raise HTTPException(401, "Sessão inválida para este cliente.")
    user = db.get(User, session.user_id)
    if not user or user.status != "active":
        raise HTTPException(401, "Conta indisponível.")
    if not bearer and request.method not in ("GET", "HEAD", "OPTIONS"):
        check_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or not secrets.compare_digest(digest(csrf), session.csrf_hash):
            raise HTTPException(403, "Requisição inválida. Atualize a página.")
    return Identity(user, session)


def current_user(identity: Identity = Depends(get_identity)):
    if identity.user.role == "admin" and (
        not identity.user.totp_enabled or not identity.session.mfa_authenticated
    ):
        raise HTTPException(403, "Ative a autenticação em dois fatores para continuar.")
    return identity.user


def admin_user(user: User = Depends(current_user)):
    if user.role != "admin":
        raise HTTPException(403, "Ação disponível somente para administradores.")
    return user
