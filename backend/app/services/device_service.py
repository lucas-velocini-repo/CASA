import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device
from app.services.device_auth_service import (
    generate_api_token,
    hash_api_token,
)


def register_device(
    db: Session,
    hardware_id: str,
    name: str,
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[Device, str | None]:

    existing_device = db.scalar(select(Device).where(Device.hardware_id == hardware_id))

    if existing_device is not None:
        if existing_device.api_token_hash is None:
            api_token = generate_api_token()

            existing_device.api_token_hash = hash_api_token(api_token)

            db.commit()
            db.refresh(existing_device)

            return existing_device, api_token

        return existing_device, None

    temporary_device_id = f"TEMP-{uuid.uuid4()}"

    api_token = generate_api_token()

    device = Device(
        device_id=temporary_device_id,
        hardware_id=hardware_id,
        name=name,
        latitude=latitude,
        longitude=longitude,
        api_token_hash=hash_api_token(api_token),
    )

    db.add(device)

    # Força o INSERT sem finalizar a transação,
    # para o PostgreSQL gerar device.id.
    db.flush()

    device.device_id = f"CASA-{device.id:06d}"

    db.commit()
    db.refresh(device)

    return device, api_token
