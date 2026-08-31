from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.device import Device
from app.schemas.device import (
    DeviceCreate,
    DeviceResponse,
)


router = APIRouter(
    prefix="/devices",
    tags=["devices"],
)


@router.post(
    "",
    response_model=DeviceResponse,
)
def create_device(
    device_data: DeviceCreate,
    db: Session = Depends(get_db),
):
    existing_device = db.scalar(
        select(Device).where(
            Device.device_id ==
            device_data.device_id
        )
    )

    if existing_device:
        raise HTTPException(
            status_code=409,
            detail="Device already exists",
        )

    device = Device(
        device_id=device_data.device_id,
        hardware_id=device_data.hardware_id,
        name=device_data.name,
    )

    db.add(device)
    db.commit()
    db.refresh(device)

    return device


@router.get(
    "",
    response_model=list[DeviceResponse],
)
def list_devices(
    db: Session = Depends(get_db),
):
    devices = db.scalars(
        select(Device)
    ).all()

    return devices