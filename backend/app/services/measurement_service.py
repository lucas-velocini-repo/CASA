from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, or_, select

from app.core.security import aware
from app.models.device import Device
from app.models.measurement import Measurement
from app.models.measurement_location import MeasurementLocation
from app.models.sensor_value import SensorValue
from app.models.accounts import Provisioning
from app.services.access_service import measurement_location_scope, measurement_scope, require_device
from app.services.measurement_location_service import location_ids_for_filter
from app.services.installation_service import apply_installation_location, installation_at, latest_installation
from app.services.location_grouping import (
    LOCATION_RADIUS_METERS,
    add_reference_sample,
    closest_location,
    valid_coordinates,
)

from sqlalchemy.orm import Session, joinedload

from sqlalchemy.exc import IntegrityError

from app.schemas.measurement import (
    LocationFilter,
    MeasurementCreate,
    MeasurementDataResponse,
    SensorValuesResponse,
)

def assign_measurement_location(db: Session, measurement: Measurement, device: Device):
    installation = installation_at(db, device.id, measurement.timestamp)
    if installation is not None:
        apply_installation_location(db, installation, measurement)
        return
    latitude, longitude = measurement.latitude, measurement.longitude
    fallback_at = None
    if (
        latitude is None
        and longitude is None
        and device.location_updated_at is not None
        and latest_installation(db, device.id) is None
        and aware(device.location_updated_at) <= measurement.timestamp
    ):
        latitude, longitude = device.latitude, device.longitude
        fallback_at = device.location_updated_at
    if not valid_coordinates(latitude, longitude):
        return

    locations = db.scalars(
        select(MeasurementLocation).where(
            MeasurementLocation.device_id == device.id, MeasurementLocation.area_id.is_(None),
            MeasurementLocation.installation_id.is_(None),
        )
    )
    location = closest_location(locations, latitude, longitude, LOCATION_RADIUS_METERS)
    if location is None:
        location = MeasurementLocation(
            device_id=device.id, latitude=latitude, longitude=longitude, samples=[]
        )
        db.add(location)
    add_reference_sample(location, latitude, longitude)
    if location.id is None:
        db.flush()
    measurement.latitude, measurement.longitude = latitude, longitude
    measurement.location_id = location.id
    measurement.location_fallback_at = fallback_at


def create_measurement(
    db: Session,
    data: MeasurementCreate,
) -> Measurement:

    # Serialize grouping and location updates for this station.
    device = db.scalar(
        select(Device)
        .where(Device.device_id == data.device_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not registered",
        )

    timestamp = datetime.fromtimestamp(
        data.timestamp,
        tz=timezone.utc,
    )

    existing_measurement_query = select(Measurement).where(
        Measurement.device_id == device.id,
        Measurement.timestamp == timestamp,
    )
    existing_measurement = db.scalar(existing_measurement_query)
    if existing_measurement is not None:
        return existing_measurement

    measurement = Measurement(
        device_id=device.id,
        timestamp=timestamp,
        latitude=data.latitude,
        longitude=data.longitude,
    )

    measurement.sensor_values = SensorValue(
        temperature=data.temperature,
        humidity=data.humidity,
        pressure=data.pressure,
        light=data.light,

        pm1=data.pm.pm1,
        pm25=data.pm.pm25,
        pm4=data.pm.pm4,
        pm10=data.pm.pm10,

        nc05=data.nc.nc05,
        nc10=data.nc.nc10,
        nc25=data.nc.nc25,
        nc40=data.nc.nc40,
        nc100=data.nc.nc100,

        typical_particle_size=data.typical_size,
    )

    try:
        assign_measurement_location(db, measurement, device)
        current_installation = latest_installation(db, device.id)
        if current_installation is None or timestamp >= aware(current_installation.started_at):
            device.last_seen = datetime.now(timezone.utc)
        db.add(measurement)
        pending = db.scalar(select(Provisioning).where(Provisioning.device_id == device.id))
        if pending and not pending.confirmed_at:
            pending.confirmed_at = datetime.now(timezone.utc)
            pending.encrypted_token = None
        db.commit()
        db.refresh(measurement)

    except IntegrityError:
        db.rollback()

        existing_measurement = db.scalar(existing_measurement_query)

        if existing_measurement is not None:
            return existing_measurement

        raise

    return measurement

def measurement_to_response(
    measurement: Measurement,
    show_location: bool,
) -> MeasurementDataResponse:

    values = measurement.sensor_values

    return MeasurementDataResponse(
        measurement_id=measurement.id,

        device_id=measurement.device.device_id,
        device_name=measurement.device.name,

        timestamp=measurement.timestamp,
        received_at=measurement.received_at,

        latitude=measurement.latitude if show_location else None,
        longitude=measurement.longitude if show_location else None,
        location_id=measurement.location_id if show_location else None,

        values=SensorValuesResponse(
            temperature=values.temperature,
            humidity=values.humidity,
            pressure=values.pressure,
            light=values.light,

            pm1=values.pm1,
            pm25=values.pm25,
            pm4=values.pm4,
            pm10=values.pm10,

            nc05=values.nc05,
            nc10=values.nc10,
            nc25=values.nc25,
            nc40=values.nc40,
            nc100=values.nc100,

            typical_particle_size=(
                values.typical_particle_size
            ),
        ),
    )

def get_measurement_history(
    db: Session,
    device_id: str,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = 1000,
    *, user, location_id: LocationFilter | None = None,
) -> list[MeasurementDataResponse]:

    device = require_device(db, user, device_id)

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not registered",
        )

    show_location = measurement_location_scope(user)
    query = (
        select(Measurement, show_location)
        .options(
            joinedload(Measurement.device),
            joinedload(Measurement.sensor_values),
        )
        .where(
            Measurement.device_id == device.id,
            measurement_scope(user),
        )
    )

    if start is not None:
        query = query.where(
            Measurement.timestamp >= start
        )

    if end is not None:
        query = query.where(
            Measurement.timestamp <= end
        )

    if location_id == "unknown":
        query = query.where(or_(Measurement.location_id.is_(None), ~show_location))
    elif location_id is not None:
        query = query.where(
            Measurement.location_id.in_(location_ids_for_filter(device.id, user.id, location_id)),
            show_location,
        )

    query = query.order_by(
        Measurement.timestamp.desc()
    ).limit(limit)

    return [
        measurement_to_response(measurement, visible)
        for measurement, visible in reversed(db.execute(query).all())
    ]

def get_latest_measurements(
    db: Session,
    user,
) -> list[MeasurementDataResponse]:

    latest_timestamp = (
        select(
            Measurement.device_id,
            func.max(Measurement.timestamp).label(
                "max_timestamp"
            ),
        )
        .where(measurement_scope(user))
        .group_by(Measurement.device_id)
        .subquery()
    )

    query = (
        select(Measurement, measurement_location_scope(user))
        .join(
            latest_timestamp,
            (
                Measurement.device_id
                == latest_timestamp.c.device_id
            )
            & (
                Measurement.timestamp
                == latest_timestamp.c.max_timestamp
            ),
        )
        .options(
            joinedload(Measurement.device),
            joinedload(Measurement.sensor_values),
        )
        .order_by(
            Measurement.device_id.asc()
        )
    )

    return [
        measurement_to_response(measurement, visible)
        for measurement, visible in db.execute(query)
    ]
