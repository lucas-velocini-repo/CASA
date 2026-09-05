import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device


def register_device(
    db: Session,
    hardware_id: str,
    name: str,
) -> Device:

    existing_device = db.scalar(
        select(Device).where(
            Device.hardware_id == hardware_id
        )
    )

    if existing_device is not None:
        return existing_device

    temporary_device_id = (
        f"TEMP-{uuid.uuid4()}"
    )

    device = Device(
        device_id=temporary_device_id,
        hardware_id=hardware_id,
        name=name,
    )

    db.add(device)

    # Força o INSERT sem finalizar a transação,
    # para o PostgreSQL gerar device.id.
    db.flush()

    device.device_id = (
        f"CASA-{device.id:06d}"
    )

    db.commit()
    db.refresh(device)

    return device