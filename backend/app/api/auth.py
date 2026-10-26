import secrets
from datetime import timedelta

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import Identity, check_origin, get_identity
from app.core.security import (
    COOKIE,
    CSRF_COOKIE,
    PRODUCTION,
    decrypt,
    digest,
    encrypt,
    utcnow,
    verify_password,
)
from app.db.database import get_db
from app.models.accounts import User, UserSession
from app.schemas.accounts import EmailRequest, LoginRequest, MFARequest, PasswordRequest
from app.services.account_service import (
    audit,
    consume_action,
    issue_action,
    public_user,
    throttle,
    verify_mfa,
)

router = APIRouter(prefix="/auth", tags=["accounts"])


@router.post("/login")
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    if data.client == "web":
        check_origin(request)
    throttle(db, request, "login", data.email)
    user = db.scalar(select(User).where(User.email == data.email).with_for_update())
    valid = verify_password(data.password, user.password_hash if user else None)
    if not user or not valid or user.status != "active":
        raise HTTPException(401, "E-mail, senha ou código incorretos.")
    if (
        user.role == "admin"
        and user.totp_enabled
        and not verify_mfa(user, data.mfa_code)
    ):
        raise HTTPException(
            401, "Informe um código de autenticação válido ou um código de recuperação."
        )
    restricted = user.role == "admin" and not user.totp_enabled
    expires = utcnow() + (
        timedelta(minutes=10)
        if restricted
        else timedelta(days=7)
        if data.client == "mobile"
        else timedelta(hours=12)
    )
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(
        UserSession(
            user_id=user.id,
            token_hash=digest(token),
            csrf_hash=digest(csrf),
            client=data.client,
            expires_at=expires,
            mfa_authenticated=user.role == "admin" and user.totp_enabled,
        )
    )
    audit(db, user, "account.login", user.id, client=data.client)
    db.commit()
    if data.client == "web":
        age = int((expires - utcnow()).total_seconds())
        for name, value, http_only in (
            (COOKIE, token, True),
            (CSRF_COOKIE, csrf, False),
        ):
            response.set_cookie(
                name,
                value,
                max_age=age,
                secure=PRODUCTION,
                httponly=http_only,
                samesite="lax",
                path="/",
            )
    response.headers["Cache-Control"] = "no-store"
    return {
        "user": public_user(user),
        "mfa_setup_required": restricted,
        "expires_at": expires,
        **({"token": token} if data.client == "mobile" else {}),
    }


@router.get("/me")
def me(identity: Identity = Depends(get_identity)):
    return {
        "user": public_user(identity.user),
        "expires_at": identity.session.expires_at,
        "mfa_setup_required": identity.user.role == "admin"
        and not identity.session.mfa_authenticated,
    }


@router.post("/logout")
def logout(
    response: Response,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    identity.session.revoked_at = utcnow()
    audit(db, identity.user, "account.logout", identity.user.id)
    db.commit()
    for name in (COOKIE, CSRF_COOKIE):
        response.delete_cookie(
            name, path="/", secure=PRODUCTION, httponly=name == COOKIE, samesite="lax"
        )
    return {"message": "Sessão encerrada."}


@router.post("/forgot-password")
def forgot(data: EmailRequest, request: Request, db: Session = Depends(get_db)):
    throttle(db, request, "password-reset", data.email, limit=3)
    user = db.scalar(select(User).where(User.email == data.email).with_for_update())
    if user and user.status == "active":
        issue_action(db, user, "reset")
        db.commit()
    return {
        "message": "Se houver uma conta disponível, enviaremos as instruções por e-mail."
    }


@router.post("/accept-invite")
def accept_invite(
    data: PasswordRequest, request: Request, db: Session = Depends(get_db)
):
    throttle(db, request, "account-link", digest(data.token), limit=10)
    consume_action(db, data.token, "invite", data.password)
    return {"message": "Conta ativada. Entre com seu e-mail e senha."}


@router.post("/reset-password")
def reset_password(
    data: PasswordRequest, request: Request, db: Session = Depends(get_db)
):
    throttle(db, request, "account-link", digest(data.token), limit=10)
    consume_action(db, data.token, "reset", data.password)
    return {"message": "Senha alterada. Entre novamente nos seus dispositivos."}


@router.post("/mfa/setup")
def mfa_setup(
    identity: Identity = Depends(get_identity), db: Session = Depends(get_db)
):
    user = db.scalar(
        select(User)
        .where(User.id == identity.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user.role != "admin" or user.totp_enabled:
        raise HTTPException(409, "Configuração indisponível.")
    if not user.totp_secret:
        user.totp_secret = encrypt(pyotp.random_base32())
        db.commit()
    secret = decrypt(user.totp_secret)
    return {
        "secret": secret,
        "uri": pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="CASA"),
    }


@router.post("/mfa/enable")
def mfa_enable(
    data: MFARequest,
    request: Request,
    identity: Identity = Depends(get_identity),
    db: Session = Depends(get_db),
):
    throttle(db, request, "mfa-setup", str(identity.user.id))
    user = db.scalar(
        select(User)
        .where(User.id == identity.user.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (
        user.role != "admin"
        or user.totp_enabled
        or not user.totp_secret
        or not verify_mfa(user, data.code)
    ):
        raise HTTPException(400, "Código inválido ou configuração indisponível.")
    recovery = [secrets.token_hex(8).upper() for _ in range(10)]
    user.recovery_hashes = [digest(code) for code in recovery]
    user.totp_enabled = True
    # Setup sessions never become full sessions; login again with the second factor.
    from app.services.account_service import revoke_sessions

    revoke_sessions(db, user.id)
    audit(db, user, "account.mfa.enabled", user.id)
    db.commit()
    return {
        "recovery_codes": recovery,
        "message": "Guarde estes códigos. Entre novamente com o segundo fator.",
    }
