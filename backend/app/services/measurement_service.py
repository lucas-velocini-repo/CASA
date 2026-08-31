from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func, select

from app.models.device import Device
from app.models.measurement import Measurement
from app.models.sensor_value import SensorValue

from sqlalchemy.orm import Session, joinedload

from sqlalchemy.exc import IntegrityError

from app.schemas.measurement import (
    MeasurementCreate,
    MeasurementDataResponse,
    SensorValuesResponse,
)

def create_measurement(
    db: Session,
    data: MeasurementCreate,
) -> Measurement:

    device = db.scalar(
        select(Device).where(
            Device.device_id == data.device_id
        )
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

    device.last_seen = datetime.now(timezone.utc)

    db.add(measurement)

    try:
        db.commit()
        db.refresh(measurement)

    except IntegrityError:
        db.rollback()

        existing_measurement = db.scalar(
            select(Measurement).where(
                Measurement.device_id == device.id,
                Measurement.timestamp == timestamp,
            )
        )

        if existing_measurement is not None:
            return existing_measurement

        raise

    return measurement

def measurement_to_response(
    measurement: Measurement,
) -> MeasurementDataResponse:

    values = measurement.sensor_values

    return MeasurementDataResponse(
        measurement_id=measurement.id,

        device_id=measurement.device.device_id,
        device_name=measurement.device.name,

        timestamp=measurement.timestamp,
        received_at=measurement.received_at,

        latitude=measurement.latitude,
        longitude=measurement.longitude,

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
) -> list[MeasurementDataResponse]:

    device = db.scalar(
        select(Device).where(
            Device.device_id == device_id
        )
    )

    if device is None:
        raise HTTPException(
            status_code=404,
            detail="Device not registered",
        )

    query = (
        select(Measurement)
        .options(
            joinedload(Measurement.device),
            joinedload(Measurement.sensor_values),
        )
        .where(
            Measurement.device_id == device.id
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

    query = query.order_by(
        Measurement.timestamp.asc()
    ).limit(limit)

    measurements = db.scalars(query).all()

    return [
        measurement_to_response(measurement)
        for measurement in measurements
    ]

def get_latest_measurements(
    db: Session,
) -> list[MeasurementDataResponse]:

    latest_timestamp = (
        select(
            Measurement.device_id,
            func.max(Measurement.timestamp).label(
                "max_timestamp"
            ),
        )
        .group_by(Measurement.device_id)
        .subquery()
    )

    query = (
        select(Measurement)
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

    measurements = db.scalars(query).all()

    return [
        measurement_to_response(measurement)
        for measurement in measurements
    ]