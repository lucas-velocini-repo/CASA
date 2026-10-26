from fastapi import HTTPException
from sqlalchemy import exists, or_, select

from app.core.security import aware
from app.models.accounts import DeviceAccess
from app.models.device import Device
from app.models.measurement import Measurement
from app.schemas.device import DeviceResponse


def device_scope(user):
    if user.role == "admin":
        return True
    return exists(
        select(DeviceAccess.id).where(
            DeviceAccess.user_id == user.id,
            DeviceAccess.device_id == Device.id,
            DeviceAccess.revoked_at.is_(None),
        )
    )


def measurement_scope(user):
    if user.role == "admin":
        return True
    return exists(
        select(DeviceAccess.id).where(
            DeviceAccess.user_id == user.id,
            DeviceAccess.device_id == Measurement.device_id,
            DeviceAccess.revoked_at.is_(None),
            Measurement.timestamp >= DeviceAccess.data_from,
            or_(
                DeviceAccess.data_until.is_(None),
                Measurement.timestamp < DeviceAccess.data_until,
            ),
        )
    )


def require_device(db, user, device_id):
    device = db.scalar(
        select(Device).where(Device.device_id == device_id, device_scope(user))
    )
    if not device:
        # Do not reveal whether another participant's station exists.
        raise HTTPException(404, "Estação não encontrada.")
    return device


def visible_device(db, user, device):
    result = DeviceResponse.model_validate(device)
    if user.role == "admin":
        return result
    access = db.scalar(
        select(DeviceAccess).where(
            DeviceAccess.user_id == user.id,
            DeviceAccess.device_id == device.id,
            DeviceAccess.revoked_at.is_(None),
        )
    )

    def allowed(timestamp):
        return (
            timestamp is not None
            and aware(timestamp) >= aware(access.data_from)
            and (
                access.data_until is None or aware(timestamp) < aware(access.data_until)
            )
        )

    # Current metadata must not expose the next household's location/activity.
    if not allowed(device.location_updated_at):
        result.latitude = result.longitude = result.location_updated_at = None
    if not allowed(device.last_seen):
        result.last_seen = None
    result.hardware_id = None
    return result
