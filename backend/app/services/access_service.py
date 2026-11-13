from fastapi import HTTPException
from sqlalchemy import exists, func, or_, select, true
from sqlalchemy.orm import aliased

from app.core.security import aware
from app.models.accounts import DeviceAccess
from app.models.device import Device
from app.models.measurement import Measurement
from app.schemas.device import DeviceResponse
from app.services.installation_service import latest_installation


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


def measurement_scope(user, timestamp=Measurement.timestamp, *, fix_timestamp=None):
    if user.role == "admin":
        return True
    current = aliased(DeviceAccess)
    window = [
        timestamp >= DeviceAccess.data_from,
        or_(DeviceAccess.data_until.is_(None), timestamp < DeviceAccess.data_until),
    ]
    if fix_timestamp is not None:
        window.extend([
            fix_timestamp >= DeviceAccess.data_from,
            or_(DeviceAccess.data_until.is_(None), fix_timestamp < DeviceAccess.data_until),
        ])
    return exists(
        select(DeviceAccess.id).where(
            DeviceAccess.user_id == user.id,
            DeviceAccess.device_id == Measurement.device_id,
            or_(DeviceAccess.revoked_at.is_(None), DeviceAccess.retain_history),
            exists(
                select(current.id).where(
                    current.user_id == DeviceAccess.user_id,
                    current.device_id == DeviceAccess.device_id,
                    current.revoked_at.is_(None),
                ).correlate(DeviceAccess)
            ),
            *window,
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


def measurement_location_scope(user):
    if user.role == "admin":
        return true()
    return measurement_scope(user, fix_timestamp=Measurement.location_fallback_at)


def visible_communication(db, device, access):
    conditions = [Measurement.device_id == device.id, Measurement.timestamp >= access.data_from]
    if access.data_until:
        conditions.append(Measurement.timestamp < access.data_until)
    return db.scalar(select(func.max(Measurement.received_at)).where(*conditions))


def visible_device(db, user, device):
    result = DeviceResponse.model_validate(device)
    installation = latest_installation(db, device.id)
    result.location_pending = installation is not None and device.location_updated_at is None
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
    if installation is None or not allowed(device.location_updated_at):
        result.latitude = result.longitude = result.location_updated_at = None
    result.last_seen = visible_communication(db, device, access)
    if not allowed(result.last_seen) or not device.last_seen or (
        installation and not allowed(installation.started_at) and not allowed(device.location_updated_at)
    ):
        result.last_seen = None
        result.measurement_interval_seconds = None
    if installation:
        result.location_pending = allowed(installation.started_at) and result.location_updated_at is None
    result.hardware_id = None
    return result
