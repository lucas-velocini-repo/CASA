from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies import admin_user
from app.core.security import utcnow
from app.db.database import get_db
from app.models.accounts import (
    AccountToken,
    AuditEvent,
    DeviceAccess,
    MailJob,
    Provisioning,
    User,
)
from app.models.device import Device
from app.schemas.accounts import AccessRequest, DeviceUpdate, InviteRequest, UserUpdate
from app.schemas.device import DeviceResponse
from app.services.account_service import (
    audit,
    issue_action,
    public_user,
    revoke_sessions,
)

router = APIRouter(
    prefix="/admin", tags=["administration"], dependencies=[Depends(admin_user)]
)


@router.get("/users")
def users(db: Session = Depends(get_db)):
    return [public_user(user) for user in db.scalars(select(User).order_by(User.id))]


@router.post("/invitations", status_code=201)
def invite(
    data: InviteRequest,
    actor: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    existing = db.scalar(select(User).where(User.email == data.email))
    if existing:
        raise HTTPException(
            409,
            "Já existe uma conta com este e-mail. Reenvie o convite pendente, se necessário.",
        )
    user = User(email=data.email, name=data.name, role=data.role, status="pending")
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Já existe uma conta com este e-mail.")
    issue_action(db, user, "invite")
    audit(db, actor, "account.invited", user.id, role=user.role)
    db.commit()
    return public_user(user)


@router.post("/users/{user_id}/resend-invite")
def resend(
    user_id: int, actor: User = Depends(admin_user), db: Session = Depends(get_db)
):
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user or user.status != "pending":
        raise HTTPException(409, "Esta conta não possui convite pendente.")
    issue_action(db, user, "invite")
    audit(db, actor, "account.invite.resent", user.id)
    db.commit()
    return {"message": "Novo convite colocado na fila de envio."}


@router.patch("/users/{user_id}")
def edit_user(
    user_id: int,
    data: UserUpdate,
    actor: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    # Serialize role/status changes so concurrent operations cannot remove the last admin.
    locked = list(
        db.scalars(
            select(User)
            .order_by(User.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    )
    if actor.role != "admin" or actor.status != "active":
        raise HTTPException(401, "Sua permissão mudou. Entre novamente.")
    user = next((row for row in locked if row.id == user_id), None)
    if not user:
        raise HTTPException(404, "Conta não encontrada.")
    if data.status == "active" and (not user.verified_at or not user.password_hash):
        raise HTTPException(409, "A pessoa deve ativar a conta pelo convite.")
    if data.status == "pending" and (user.verified_at or user.password_hash):
        raise HTTPException(
            409, "Uma conta ativada não pode voltar a convite pendente."
        )
    removing = data.status == "disabled" or data.role == "user"
    if user.id == actor.id and removing:
        raise HTTPException(
            409, "Você não pode bloquear ou remover seu próprio perfil administrativo."
        )
    if user.role == "admin" and user.status == "active" and removing:
        if sum(row.role == "admin" and row.status == "active" for row in locked) <= 1:
            raise HTTPException(409, "Mantenha pelo menos um administrador ativo.")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in changes.items():
        setattr(user, key, value.strip() if key == "name" else value)
    if "role" in changes or "status" in changes:
        revoke_sessions(db, user.id)
    if data.status == "disabled":
        from sqlalchemy import update

        db.execute(
            update(AccountToken)
            .where(AccountToken.user_id == user.id, AccountToken.used_at.is_(None))
            .values(used_at=utcnow())
        )
    if data.status == "pending":
        issue_action(db, user, "invite")
    audit(db, actor, "account.updated", user.id, **changes)
    db.commit()
    return public_user(user)


@router.get("/access")
def accesses(db: Session = Depends(get_db)):
    return [
        {
            "id": a.id,
            "user_id": a.user_id,
            "device_id": a.device_id,
            "data_from": a.data_from,
            "data_until": a.data_until,
            "granted_by": a.granted_by,
            "granted_at": a.granted_at,
            "revoked_at": a.revoked_at,
        }
        for a in db.scalars(select(DeviceAccess).order_by(DeviceAccess.id.desc()))
    ]


@router.post("/access", status_code=201)
def grant(
    data: AccessRequest,
    actor: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    user = db.scalar(select(User).where(User.id == data.user_id).with_for_update())
    if not user or not db.get(Device, data.device_id):
        raise HTTPException(404, "Conta ou estação não encontrada.")
    previous = db.scalar(
        select(DeviceAccess).where(
            DeviceAccess.user_id == data.user_id,
            DeviceAccess.device_id == data.device_id,
            DeviceAccess.revoked_at.is_(None),
        )
    )
    if previous:
        previous.revoked_at = utcnow()
        db.flush()
    access = DeviceAccess(**data.model_dump(), granted_by=actor.id)
    db.add(access)
    db.flush()
    audit(
        db,
        actor,
        "station.access.granted",
        access.id,
        user_id=user.id,
        device_id=data.device_id,
        data_from=data.data_from.isoformat(),
        data_until=data.data_until.isoformat() if data.data_until else None,
    )
    db.commit()
    return {"id": access.id}


@router.delete("/access/{access_id}")
def revoke(
    access_id: int, actor: User = Depends(admin_user), db: Session = Depends(get_db)
):
    access = db.scalar(
        select(DeviceAccess).where(DeviceAccess.id == access_id).with_for_update()
    )
    if not access:
        raise HTTPException(404, "Vínculo não encontrado.")
    access.revoked_at = utcnow()
    audit(db, actor, "station.access.revoked", access.id)
    db.commit()
    return {"message": "Acesso revogado."}


@router.patch("/devices/{device_id}", response_model=DeviceResponse)
def edit_device(
    device_id: int,
    data: DeviceUpdate,
    actor: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    device = db.get(Device, device_id)
    if not device:
        raise HTTPException(404, "Estação não encontrada.")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for key, value in changes.items():
        setattr(device, key, value.strip() if key == "name" else value)
    audit(db, actor, "station.updated", device.device_id, **changes)
    db.commit()
    return device


@router.post("/devices/{device_id}/restart-provisioning")
def restart_provisioning(
    device_id: int, actor: User = Depends(admin_user), db: Session = Depends(get_db)
):
    from datetime import timedelta
    from app.core.security import encrypt
    from app.services.device_auth_service import generate_api_token, hash_api_token

    device = db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    pending = db.scalar(
        select(Provisioning)
        .where(Provisioning.device_id == device_id)
        .with_for_update()
    )
    if not device or not pending or pending.confirmed_at or device.last_seen:
        raise HTTPException(
            409,
            "Somente um provisionamento pendente, ainda sem medições, pode ser reiniciado.",
        )
    token = generate_api_token()
    device.api_token_hash = hash_api_token(token)
    pending.actor_id, pending.encrypted_token = actor.id, encrypt(token)
    pending.expires_at = utcnow() + timedelta(hours=24)
    audit(db, actor, "station.provisioning.restarted", device.device_id)
    db.commit()
    return {
        "message": "Provisionamento reiniciado. Reconecte a estação pelo aplicativo para concluir."
    }


@router.get("/audit")
def events(
    before: int | None = None,
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)
    if before:
        query = query.where(AuditEvent.id < before)
    return [
        {
            "id": e.id,
            "actor_id": e.actor_id,
            "action": e.action,
            "target": e.target,
            "details": e.details,
            "created_at": e.created_at,
        }
        for e in db.scalars(query)
    ]


@router.get("/mail-status")
def mail_status(db: Session = Depends(get_db)):
    # Never expose encrypted payloads or account links to the dashboard.
    return [
        {
            "id": j.id,
            "status": j.status,
            "attempts": j.attempts,
            "created_at": j.created_at,
        }
        for j in db.scalars(select(MailJob).order_by(MailJob.id.desc()).limit(100))
    ]
