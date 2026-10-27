"""Station-initiated polling: no inbound connection to a household is needed."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import admin_user
from app.core.security import utcnow
from app.db.database import get_db
from app.models.accounts import User
from app.models.device import Device
from app.models.station_configuration import StationConfiguration
from app.schemas.station_configuration import ConfigurationReport, IntervalRequest
from app.services.account_service import audit
from app.services.device_auth_service import authenticate_device

router = APIRouter(tags=["station configuration"])
bearer = HTTPBearer(auto_error=False)


def station_identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)):
    device = authenticate_device(db, credentials.credentials) if credentials else None
    if device is None:
        raise HTTPException(401, "Credencial de estação inválida.", headers={"WWW-Authenticate": "Bearer"})
    return device


def locked_configuration(db, device_id):
    # Lock the parent first, including when the configuration row does not exist yet.
    db.scalar(select(Device).where(Device.id == device_id).with_for_update())
    config = db.scalar(select(StationConfiguration).where(StationConfiguration.device_id == device_id).with_for_update().execution_options(populate_existing=True))
    if config is None:
        config = StationConfiguration(device_id=device_id, revision=0, applied_revision=0)
        db.add(config)
        db.flush()
    return config


def summary(config, device_id):
    return {
        "device_id": device_id,
        "desired_interval_seconds": config.desired_interval_seconds if config else None,
        "revision": config.revision if config else 0,
        "reported_interval_seconds": config.reported_interval_seconds if config else None,
        "applied_revision": config.applied_revision if config else 0,
        "reported_at": config.reported_at if config else None,
        "polled_at": config.polled_at if config else None,
        "firmware_version": config.firmware_version if config else None,
        "pending": bool(config and config.revision > config.applied_revision),
    }


@router.get("/admin/device-configurations")
def list_configurations(actor: User = Depends(admin_user), db: Session = Depends(get_db)):
    return [summary(config, device.id) for device, config in db.execute(select(Device, StationConfiguration).outerjoin(StationConfiguration, StationConfiguration.device_id == Device.id).order_by(Device.id))]


@router.patch("/admin/devices/{device_id}/configuration")
def set_interval(device_id: int, data: IntervalRequest, actor: User = Depends(admin_user), db: Session = Depends(get_db)):
    if db.get(Device, device_id) is None:
        raise HTTPException(404, "Estação não encontrada.")
    config = locked_configuration(db, device_id)
    if config.desired_interval_seconds != data.interval_seconds:
        config.desired_interval_seconds = data.interval_seconds
        config.revision += 1
        audit(db, actor, "station.interval.requested", f"{device_id}:{data.interval_seconds}s:r{config.revision}")
    db.commit()
    return summary(config, device_id)


@router.get("/devices/config")
def poll_configuration(device: Device = Depends(station_identity), db: Session = Depends(get_db)):
    config = locked_configuration(db, device.id)
    config.polled_at = utcnow()
    db.commit()
    return {"revision": config.revision, "interval_seconds": config.desired_interval_seconds}


@router.post("/devices/config/report")
def report_configuration(data: ConfigurationReport, device: Device = Depends(station_identity), db: Session = Depends(get_db)):
    config = locked_configuration(db, device.id)
    if data.revision > config.revision or (data.revision == config.revision and config.desired_interval_seconds is not None and data.interval_seconds != config.desired_interval_seconds):
        raise HTTPException(409, "Configuração divergente. Consulte novamente o servidor.")
    # A delayed report must not undo confirmation of a newer revision.
    if data.revision >= config.applied_revision:
        config.applied_revision = data.revision
        config.reported_interval_seconds = data.interval_seconds
        config.reported_at = utcnow()
        config.firmware_version = data.firmware_version
    db.commit()
    return {"status": "confirmed", "pending": config.revision > config.applied_revision}
