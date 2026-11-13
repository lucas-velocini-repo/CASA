from collections import defaultdict
from datetime import timedelta

from sqlalchemy import case, func, select

from app.core.security import aware, utcnow
from app.models.device import Device
from app.models.measurement import Measurement
from app.models.measurement_location import MeasurementLocation
from app.models.station_installation import StationFix, StationInstallation
from app.schemas.measurement import StationMapPin, StationMapVisit
from app.services.access_service import device_scope, measurement_location_scope, measurement_scope, visible_device
from app.services.measurement_location_service import area_id, location_options, visible_areas


def map_visits(db, device_id, user, interval):
    # Compute runs before discarding unknown locations, so a later return stays a distinct visit.
    visible_area = case((measurement_location_scope(user), area_id), else_=None)
    rows = (
        select(Measurement.timestamp.label("stamp"), visible_area.label("area"))
        .select_from(Measurement)
        .outerjoin(MeasurementLocation, MeasurementLocation.id == Measurement.location_id)
        .where(Measurement.device_id == device_id, measurement_scope(user))
        .subquery()
    )
    # Break visits at access gaps even when the surrounding authorized readings share an area.
    if user.role != "admin":
        from app.models.accounts import DeviceAccess
        from sqlalchemy import or_

        window = select(func.max(DeviceAccess.data_from)).where(
            DeviceAccess.user_id == user.id, DeviceAccess.device_id == device_id,
            or_(DeviceAccess.revoked_at.is_(None), DeviceAccess.retain_history),
            DeviceAccess.data_from <= Measurement.timestamp,
            or_(DeviceAccess.data_until.is_(None), Measurement.timestamp < DeviceAccess.data_until),
        ).correlate(Measurement).scalar_subquery()
        rows = select(
            Measurement.timestamp.label("stamp"), visible_area.label("area"), window.label("window_start"),
        ).select_from(Measurement).outerjoin(
            MeasurementLocation, MeasurementLocation.id == Measurement.location_id,
        ).where(Measurement.device_id == device_id, measurement_scope(user)).subquery()
    else:
        rows = select(rows, rows.c.stamp.is_(None).label("window_start")).subquery()
    ordered = select(
        rows, func.lag(rows.c.area).over(order_by=rows.c.stamp).label("previous_area"),
        func.lag(rows.c.stamp).over(order_by=rows.c.stamp).label("previous_stamp"),
        func.lag(rows.c.window_start).over(order_by=rows.c.stamp).label("previous_window"),
    ).subquery()
    time_gap = (
        (func.julianday(ordered.c.stamp) - func.julianday(ordered.c.previous_stamp)) * 86400
        if db.get_bind().dialect.name == "sqlite"
        else func.extract("epoch", ordered.c.stamp - ordered.c.previous_stamp)
    )
    starts = case((
        ordered.c.area.is_distinct_from(ordered.c.previous_area)
        | ordered.c.window_start.is_distinct_from(ordered.c.previous_window)
        | (time_gap > max(3600, 3 * (interval or 300))),
        1,
    ), else_=0)
    runs = select(ordered.c.area, ordered.c.stamp, func.sum(starts).over(order_by=ordered.c.stamp).label("run")).subquery()
    visits = defaultdict(list)
    for key, start, end in db.execute(
        select(runs.c.area, func.min(runs.c.stamp), func.max(runs.c.stamp))
        .group_by(runs.c.area, runs.c.run).order_by(func.max(runs.c.stamp).desc())
    ):
        if key is not None:
            visits[key].append(StationMapVisit(start=aware(start), end=aware(end)))
    return visits


def station_map(db, user):
    result = []
    now = utcnow()
    for device in db.scalars(select(Device).where(device_scope(user)).order_by(Device.id)):
        metadata = visible_device(db, user, device)
        areas = visible_areas(db, device.id, user)
        visits = map_visits(db, device.id, user, metadata.measurement_interval_seconds)
        options = location_options(db, device.id, user, areas)
        targets = {member.location_id: option.location_id for option in options.values() for member in option.links}
        last_measurement = db.scalar(select(func.max(Measurement.timestamp)).where(
            Measurement.device_id == device.id, measurement_scope(user),
        ))
        latest = next(iter(visits), None)
        if metadata.location_pending:
            latest = None
        if metadata.location_updated_at:
            fix_area = db.scalar(
                select(StationFix.location_id).join(StationInstallation)
                .where(StationInstallation.device_id == device.id, StationFix.acquired_at == metadata.location_updated_at)
            )
            if fix_area is not None:
                latest = fix_area if fix_area in areas else None
        active = metadata.active and metadata.last_seen and (
            timedelta(0) <= now - aware(metadata.last_seen)
            <= timedelta(seconds=max(360, 1.2 * (metadata.measurement_interval_seconds or 0)))
        )
        references = {}
        if user.role == "admin":
            references = {item.id: item for item in db.scalars(
                select(MeasurementLocation).where(MeasurementLocation.id.in_(areas))
            )}
        else:
            # Average only distinct confirmed fixes attached to authorized readings.
            samples = select(
                area_id.label("area"), Measurement.latitude.label("latitude"),
                Measurement.longitude.label("longitude"),
            ).select_from(Measurement).join(
                MeasurementLocation, MeasurementLocation.id == Measurement.location_id,
            ).where(
                Measurement.device_id == device.id, measurement_scope(user),
                measurement_location_scope(user),
            ).distinct().subquery()
            references = {row.area: row for row in db.execute(
                select(samples.c.area, func.avg(samples.c.latitude).label("latitude"),
                       func.avg(samples.c.longitude).label("longitude")).group_by(samples.c.area)
            )}
        for key, intervals in visits.items():
            area = areas.get(key)
            if area is None:
                continue
            reference = references.get(key, area)
            target = targets.get(key, key)
            result.append(StationMapPin(
                area_id=key, location_id=target, device_id=device.device_id, device_name=device.name,
                name=options[target].name or area.name,
                latitude=reference.latitude, longitude=reference.longitude,
                status=("active" if active else "inactive") if key == latest else "old",
                last_measurement=aware(last_measurement), visits=intervals,
            ))
    return result
