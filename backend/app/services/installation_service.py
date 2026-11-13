from datetime import timedelta

from sqlalchemy import select, update

from app.core.security import aware
from app.models.device import Device
from app.models.measurement import Measurement
from app.models.measurement_location import MeasurementLocation
from app.models.station_installation import StationFix, StationInstallation
from app.services.location_grouping import LOCATION_RADIUS_METERS, add_reference_sample, closest_location


def lock_station(db, device_id):
    return db.scalar(
        select(Device).where(Device.id == device_id).with_for_update()
        .execution_options(populate_existing=True)
    )


def installation_at(db, device_id, timestamp):
    return db.scalar(
        select(StationInstallation)
        .where(StationInstallation.device_id == device_id, StationInstallation.started_at <= timestamp)
        .order_by(StationInstallation.started_at.desc()).limit(1)
    )


def latest_installation(db, device_id):
    return db.scalar(
        select(StationInstallation).where(StationInstallation.device_id == device_id)
        .order_by(StationInstallation.started_at.desc()).limit(1)
    )


def apply_installation_location(db, installation, measurement):
    fixes = select(StationFix).where(StationFix.installation_id == installation.id)
    fix = db.scalar(fixes.where(StationFix.acquired_at <= measurement.timestamp)
                    .order_by(StationFix.acquired_at.desc()).limit(1))
    if fix is None and installation.backfill_initial:
        candidate = db.scalar(fixes.order_by(StationFix.acquired_at).limit(1))
        if candidate and aware(candidate.acquired_at) <= aware(installation.started_at) + timedelta(hours=24):
            fix = candidate
    measurement.latitude = fix.latitude if fix else None
    measurement.longitude = fix.longitude if fix else None
    measurement.location_id = fix.location_id if fix else None
    measurement.location_fallback_at = fix.acquired_at if fix else None


def store_fix(db, device, installation, data):
    fixes = select(StationFix).where(StationFix.installation_id == installation.id)
    if db.get(StationFix, (installation.id, data.acquired_at)):
        return False
    previous = db.scalar(fixes.where(StationFix.acquired_at < data.acquired_at)
                         .order_by(StationFix.acquired_at.desc()).limit(1))
    following = db.scalar(fixes.where(StationFix.acquired_at > data.acquired_at)
                          .order_by(StationFix.acquired_at).limit(1))
    locations = db.scalars(select(MeasurementLocation).where(
        MeasurementLocation.installation_id == installation.id,
    ))
    location = closest_location(locations, data.latitude, data.longitude, LOCATION_RADIUS_METERS)
    if location is None:
        location = MeasurementLocation(device_id=device.id, installation_id=installation.id,
                                       latitude=data.latitude, longitude=data.longitude, samples=[])
        db.add(location)
    add_reference_sample(location, data.latitude, data.longitude)
    db.flush()
    db.add(StationFix(installation_id=installation.id, acquired_at=data.acquired_at,
                      location_id=location.id, latitude=data.latitude, longitude=data.longitude))

    next_installation = db.scalar(select(StationInstallation.started_at).where(
        StationInstallation.device_id == device.id,
        StationInstallation.started_at > installation.started_at,
    ).order_by(StationInstallation.started_at).limit(1))
    start = data.acquired_at
    if not previous and installation.backfill_initial and data.acquired_at <= aware(installation.started_at) + timedelta(hours=24):
        start = installation.started_at
    statement = update(Measurement).where(Measurement.device_id == device.id, Measurement.timestamp >= start)
    if following:
        statement = statement.where(Measurement.timestamp < following.acquired_at)
    if next_installation:
        statement = statement.where(Measurement.timestamp < next_installation)
    db.execute(statement.values(latitude=data.latitude, longitude=data.longitude,
                                location_id=location.id, location_fallback_at=data.acquired_at))
    return next_installation is None and (
        device.location_updated_at is None or data.acquired_at > aware(device.location_updated_at)
    )
