import json
import math
import secrets
import time
from datetime import timedelta

import pyotp
from fastapi import HTTPException, Request
from sqlalchemy import delete, select, update

from app.core.security import (
    APP_URL,
    PASSWORDS,
    aware,
    decrypt,
    digest,
    encrypt,
    utcnow,
)
from app.models.accounts import (
    AccountToken,
    AuditEvent,
    MailJob,
    RateBucket,
    User,
    UserSession,
)


def audit(db, actor, action, target, **details):
    db.add(
        AuditEvent(
            actor_id=actor.id if actor else None,
            action=action,
            target=str(target),
            details=details,
        )
    )


def public_user(user):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "status": user.status,
        "mfa_enabled": user.totp_enabled,
        "activated": user.verified_at is not None,
    }


def throttle(db, request: Request, action: str, identity="", limit=10, seconds=900):
    """DB-backed, atomic counters work across API processes. No user-supplied proxy headers."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    bucket = math.floor(time.time() / seconds)
    ip = request.client.host if request.client else "unknown"
    for suffix, maximum in [(f"identity:{identity}", limit), (f"ip:{ip}", 200)]:
        key = digest(f"{action}:{suffix}:{bucket}")
        insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
        statement = insert(RateBucket).values(
            key=key, count=1, expires_at=utcnow() + timedelta(seconds=seconds * 2)
        )
        count = db.scalar(
            statement.on_conflict_do_update(
                index_elements=[RateBucket.key], set_={"count": RateBucket.count + 1}
            ).returning(RateBucket.count)
        )
        db.commit()
        if count > maximum:
            raise HTTPException(
                429,
                "Muitas tentativas. Aguarde alguns minutos.",
                headers={"Retry-After": str(seconds)},
            )


def revoke_sessions(db, user_id):
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def issue_action(db, user, purpose):
    db.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user.id,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
        )
        .values(used_at=utcnow())
    )
    token = secrets.token_urlsafe(32)
    expires = utcnow() + (
        timedelta(hours=48) if purpose == "invite" else timedelta(minutes=30)
    )
    db.add(
        AccountToken(
            user_id=user.id,
            token_hash=digest(token),
            purpose=purpose,
            expires_at=expires,
        )
    )
    # URL fragment avoids sending the secret in HTTP/proxy logs and referrers.
    link = f"{APP_URL}/#{purpose}={token}"
    subject = (
        "Seu convite para o CASA"
        if purpose == "invite"
        else "Recuperação de senha do CASA"
    )
    body = f"Olá, {user.name}.\n\n{subject}:\n{link}\n\nO link é pessoal, tem validade e funciona uma única vez. Se não solicitou, ignore esta mensagem."
    db.add(
        MailJob(
            payload=encrypt(
                json.dumps({"to": user.email, "subject": subject, "body": body})
            ),
            expires_at=expires,
        )
    )


def consume_action(db, raw, purpose, password):
    action = db.scalar(
        select(AccountToken)
        .where(AccountToken.token_hash == digest(raw), AccountToken.purpose == purpose)
        .with_for_update()
    )
    if not action or action.used_at or aware(action.expires_at) <= utcnow():
        raise HTTPException(400, "Link inválido, expirado ou já utilizado.")
    user = db.scalar(select(User).where(User.id == action.user_id).with_for_update())
    allowed = user and (
        user.status == "pending" if purpose == "invite" else user.status == "active"
    )
    if not allowed:
        raise HTTPException(400, "Link inválido, expirado ou já utilizado.")
    user.password_hash = PASSWORDS.hash(password)
    if purpose == "invite":
        user.status = "active"
        user.verified_at = utcnow()
    # Invalidate every outstanding account link and session after a password change.
    db.execute(
        update(AccountToken)
        .where(AccountToken.user_id == user.id, AccountToken.used_at.is_(None))
        .values(used_at=utcnow())
    )
    revoke_sessions(db, user.id)
    audit(db, user, f"account.{purpose}.completed", user.id)
    db.commit()


def verify_mfa(user, code):
    code = code.strip().replace(" ", "")
    if len(code) == 6 and code.isdigit() and user.totp_secret:
        totp = pyotp.TOTP(decrypt(user.totp_secret))
        step = int(time.time()) // 30
        for counter in (step - 1, step, step + 1):
            if counter > user.totp_last_step and secrets.compare_digest(
                totp.at(counter * 30), code
            ):
                user.totp_last_step = counter
                return True
    recovery = digest(code.upper())
    if recovery in user.recovery_hashes:
        user.recovery_hashes = [h for h in user.recovery_hashes if h != recovery]
        return True
    return False


def cleanup(db):
    cutoff = utcnow()
    db.execute(
        delete(UserSession).where(UserSession.expires_at < cutoff - timedelta(days=7))
    )
    db.execute(
        delete(AccountToken).where(AccountToken.expires_at < cutoff - timedelta(days=7))
    )
    db.execute(delete(RateBucket).where(RateBucket.expires_at < cutoff))
    db.execute(delete(MailJob).where(MailJob.expires_at < cutoff - timedelta(days=7)))
    from app.models.accounts import Provisioning

    db.execute(
        update(Provisioning)
        .where(Provisioning.expires_at < cutoff)
        .values(encrypted_token=None)
    )
    db.commit()
