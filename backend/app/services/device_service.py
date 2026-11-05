import uuid
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.security import aware, decrypt, digest, encrypt, utcnow
from app.models.accounts import Provisioning
from app.models.device import Device
from app.services.account_service import audit
from app.services.device_auth_service import generate_api_token, hash_api_token


def register_device(
    db: Session, hardware_id: str, name: str, actor, latitude=None, longitude=None
) -> tuple[Device, str | None]:
    # One station per hardware ID even if two phones provision concurrently.
    if db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": int(digest(hardware_id)[:15], 16)},
        )
    existing = db.scalar(
        select(Device).where(Device.hardware_id == hardware_id).with_for_update()
    )
    if existing:
        pending = db.scalar(
            select(Provisioning)
            .where(Provisioning.device_id == existing.id)
            .with_for_update()
        )
        if pending and not pending.confirmed_at and not existing.last_seen:
            if aware(pending.expires_at) <= utcnow() or not pending.encrypted_token:
                raise HTTPException(
                    409,
                    "Provisionamento expirado. A equipe deve reiniciar o provisionamento pendente.",
                )
            audit(db, actor, "station.provisioning.resumed", existing.device_id)
            token = decrypt(pending.encrypted_token)
            db.commit()
            return existing, token
        # Never replace the credential of a working or already configured station.
        return existing, None
    token = generate_api_token()
    device = Device(
        device_id=f"TEMP-{uuid.uuid4()}",
        hardware_id=hardware_id,
        name=name,
        latitude=latitude,
        longitude=longitude,
        api_token_hash=hash_api_token(token),
    )
    db.add(device)
    db.flush()
    device.device_id = f"CASA-{device.id:06d}"
    db.add(
        Provisioning(
            device_id=device.id,
            actor_id=actor.id,
            encrypted_token=encrypt(token),
            expires_at=utcnow() + timedelta(hours=24),
        )
    )
    audit(db, actor, "station.provisioning.started", device.device_id)
    db.commit()
    db.refresh(device)
    return device, token
