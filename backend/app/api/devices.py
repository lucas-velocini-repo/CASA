from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.device import Device
from app.schemas.device import (
    DeviceCreate,
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceResponse,
    DeviceLocationUpdate,
    DeviceLocationResponse,
)
from app.services.device_auth_service import authenticate_device
from app.services.device_location_service import update_device_location
from app.services.device_service import (
    register_device,
)
from app.api.dependencies import admin_user, current_user
from app.models.accounts import Provisioning, User
from app.services.access_service import device_scope, visible_device
from app.services.account_service import audit
from app.core.security import utcnow

router = APIRouter(
    prefix="/devices",
    tags=["devices"],
)

bearer_scheme = HTTPBearer(auto_error=False)


@router.patch("/location", response_model=DeviceLocationResponse)
def receive_device_location(
    data: DeviceLocationUpdate,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    device = (
        authenticate_device(db, credentials.credentials)
        if credentials is not None else None
    )
    if device is None:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not device.active:
        raise HTTPException(status_code=403, detail="Device is inactive")
    return update_device_location(db, device, data)


@router.post(
    "",
    response_model=DeviceResponse,
)
def create_device(
    device_data: DeviceCreate,
    actor: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    existing_device = db.scalar(
        select(Device).where(Device.device_id == device_data.device_id)
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
        latitude=device_data.latitude,
        longitude=device_data.longitude,
    )

    db.add(device)
    audit(db, actor, "station.created", device.device_id)
    db.commit()
    db.refresh(device)

    return device


@router.get(
    "",
    response_model=list[DeviceResponse],
)
def list_devices(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    devices = db.scalars(select(Device).where(device_scope(user)).order_by(Device.id)).all()

    return [visible_device(db, user, device) for device in devices]


@router.post(
    "/register",
    response_model=DeviceRegisterResponse,
    status_code=201,
)
def register_new_device(
    data: DeviceRegisterRequest,
    actor: User = Depends(admin_user),
    db: Session = Depends(get_db),
):
    device, api_token = register_device(
        db=db,
        hardware_id=data.hardware_id,
        name=data.name,
        latitude=data.latitude,
        longitude=data.longitude,
        actor=actor,
    )

    return DeviceRegisterResponse(
        device_id=device.device_id,
        hardware_id=device.hardware_id,
        name=device.name,
        api_token=api_token,
    )


@router.post("/{device_id}/provisioning/confirm")
def confirm_provisioning(device_id: str, actor: User = Depends(admin_user), db: Session = Depends(get_db)):
    device = db.scalar(select(Device).where(Device.device_id == device_id))
    if not device:
        raise HTTPException(404, "Estação não encontrada.")
    pending = db.scalar(select(Provisioning).where(Provisioning.device_id == device.id).with_for_update())
    if pending and not pending.confirmed_at:
        pending.confirmed_at, pending.encrypted_token = utcnow(), None
        audit(db, actor, "station.provisioning.confirmed", device_id)
        db.commit()
    return {"message": "Provisionamento confirmado."}
