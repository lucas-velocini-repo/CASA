from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.models.device import Device
from app.schemas.device import DeviceLocationResponse, DeviceLocationUpdate


def update_device_location(
    db: Session, device: Device, data: DeviceLocationUpdate
) -> DeviceLocationResponse:
    # Keep the timestamp comparison in the UPDATE so concurrent requests and
    # delayed offline retries cannot overwrite a newer fix. Equal times are
    # idempotent, including retries after a lost HTTP response.
    result = db.execute(
        update(Device)
        .where(
            Device.id == device.id,
            or_(
                Device.location_updated_at.is_(None),
                Device.location_updated_at < data.acquired_at,
            ),
        )
        .values(
            latitude=data.latitude,
            longitude=data.longitude,
            location_updated_at=data.acquired_at,
        )
        .execution_options(synchronize_session=False)
    )
    changed = result.rowcount > 0
    db.commit()
    db.refresh(device)
    # Location contact intentionally does not change environmental last_seen.
    return DeviceLocationResponse(
        device_id=device.device_id,
        latitude=device.latitude,
        longitude=device.longitude,
        location_updated_at=device.location_updated_at,
        status="stored" if changed else "unchanged",
    )
