from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import aliased

from app.models.accounts import User
from app.models.measurement import Measurement
from app.models.measurement_location import (
    MeasurementLocation,
    MeasurementLocationGroup,
    MeasurementLocationLink,
    MeasurementLocationName,
)
from app.schemas.measurement import MeasurementLocationResponse, MeasurementLocationSummary
from app.services.access_service import measurement_location_scope, measurement_scope, require_device


area_id = func.coalesce(MeasurementLocation.area_id, MeasurementLocation.id)


def location_ids_for_filter(device_id, user_id, location_id):
    requested_area = (
        select(area_id)
        .where(MeasurementLocation.id == location_id, MeasurementLocation.device_id == device_id)
        .correlate(None)
        .scalar_subquery()
    )
    link_root = (
        select(MeasurementLocationLink.root_id)
        .where(MeasurementLocationLink.user_id == user_id,
               MeasurementLocationLink.location_id == requested_area)
        .correlate(None)
        .scalar_subquery()
    )
    root = func.coalesce(link_root, requested_area)
    children = select(MeasurementLocationLink.location_id).where(
        MeasurementLocationLink.user_id == user_id, MeasurementLocationLink.root_id == root
    )
    return select(MeasurementLocation.id).where(
        MeasurementLocation.device_id == device_id, or_(area_id == root, area_id.in_(children))
    )


def visible_areas(db, device_id, user):
    # A representative coordinate must come from a measurement the account can see.
    visible_sample = (
        select(Measurement.id)
        .where(
            Measurement.device_id == device_id,
            Measurement.location_id == MeasurementLocation.id,
            measurement_scope(user),
            measurement_location_scope(user),
        )
        .order_by(Measurement.timestamp)
        .limit(1)
        .correlate(MeasurementLocation)
        .scalar_subquery()
    )
    area_name = aliased(MeasurementLocationName)
    query = (
        select(area_id.label("area_id"), Measurement.latitude, Measurement.longitude,
               area_name.name.label("area_name"), MeasurementLocationName.name)
        .select_from(MeasurementLocation)
        .join(Measurement, Measurement.id == visible_sample)
        .outerjoin(area_name, (area_name.location_id == area_id) & (area_name.user_id == user.id))
        .outerjoin(
            MeasurementLocationName,
            (MeasurementLocationName.location_id == MeasurementLocation.id)
            & (MeasurementLocationName.user_id == user.id),
        )
        .where(MeasurementLocation.device_id == device_id)
        .order_by(MeasurementLocation.area_id.is_not(None), MeasurementLocation.id)
    )
    areas = {}
    for row in db.execute(query):
        if row.area_id not in areas:
            name = row.name if row.area_name is None else row.area_name
            areas[row.area_id] = MeasurementLocationSummary(
                location_id=row.area_id, latitude=row.latitude, longitude=row.longitude,
                name=name or None,
            )
        elif row.area_name is None and areas[row.area_id].name is None and row.name:
            areas[row.area_id].name = row.name
    return areas


def location_options(db, device_id, user, areas):
    group_rows = db.execute(
        select(MeasurementLocationGroup.root_id, MeasurementLocationGroup.name,
               MeasurementLocationLink.location_id)
        .join(MeasurementLocation, MeasurementLocation.id == MeasurementLocationGroup.root_id)
        .join(
            MeasurementLocationLink,
            (MeasurementLocationLink.user_id == MeasurementLocationGroup.user_id)
            & (MeasurementLocationLink.root_id == MeasurementLocationGroup.root_id),
        )
        .where(MeasurementLocation.device_id == device_id, MeasurementLocationGroup.user_id == user.id)
        .order_by(MeasurementLocationLink.location_id)
    )
    children = defaultdict(list)
    group_names = {}
    for root_id, name, child_id in group_rows:
        group_names[root_id] = name
        if child_id in areas:
            children[root_id].append(areas[child_id])
    options = {
        key: MeasurementLocationResponse(**area.model_dump()) for key, area in areas.items()
    }
    for root_id, name in group_names.items():
        links = children[root_id]
        representative = areas.get(root_id) or (links[0] if links else None)
        if representative is None:
            continue
        for child in links:
            options.pop(child.location_id, None)
        options[root_id] = MeasurementLocationResponse(
            location_id=root_id, latitude=representative.latitude,
            longitude=representative.longitude, name=name or None, links=links, grouped=True,
        )
    return options


def get_measurement_locations(db, device_id, *, user, latest_first=False):
    device = require_device(db, user, device_id)
    options = location_options(db, device.id, user, visible_areas(db, device.id, user))
    latest = None
    if latest_first and options:
        latest = db.scalar(
            select(func.coalesce(MeasurementLocationLink.root_id, area_id))
            .select_from(Measurement)
            .join(MeasurementLocation, MeasurementLocation.id == Measurement.location_id)
            .outerjoin(
                MeasurementLocationLink,
                (MeasurementLocationLink.location_id == area_id)
                & (MeasurementLocationLink.user_id == user.id),
            )
            .where(
                Measurement.device_id == device.id,
                measurement_scope(user),
                measurement_location_scope(user),
            )
            .order_by(Measurement.timestamp.desc())
            .limit(1)
        )
    return [options[key] for key in sorted(options, key=lambda key: (key != latest, key))]


def editable_locations(db, device_id, user):
    device = require_device(db, user, device_id)
    # Keep simultaneous edits by the same account from creating overlapping groups.
    db.scalar(select(User.id).where(User.id == user.id).with_for_update())
    areas = visible_areas(db, device.id, user)
    return areas, location_options(db, device.id, user, areas)


def set_measurement_location_name(db, device_id, location_id, name, *, user):
    _, options = editable_locations(db, device_id, user)
    option = options.get(location_id)
    if option is None:
        raise HTTPException(404, "Local de coleta não encontrado.")
    if option.grouped:
        group = db.get(MeasurementLocationGroup, (user.id, location_id))
        group.name = name or ""
    else:
        insert = pg_insert if db.get_bind().dialect.name == "postgresql" else sqlite_insert
        statement = insert(MeasurementLocationName).values(
            location_id=location_id, user_id=user.id, name=name or ""
        )
        db.execute(statement.on_conflict_do_update(
            index_elements=[MeasurementLocationName.location_id, MeasurementLocationName.user_id],
            set_={"name": statement.excluded.name},
        ))
    db.commit()
    return option.model_copy(update={"name": name or None})


def link_measurement_locations(db, device_id, root_id, child_id, name, *, user):
    areas, options = editable_locations(db, device_id, user)
    if root_id not in options or child_id not in areas:
        raise HTTPException(404, "Local de coleta não encontrado.")
    if root_id == child_id:
        raise HTTPException(409, "Escolha outro local para vincular.")
    current = db.get(MeasurementLocationLink, (user.id, child_id))
    if (current and current.root_id != root_id) or (child_id in options and options[child_id].grouped):
        raise HTTPException(409, "Esse local já pertence a outro vínculo.")

    group = db.get(MeasurementLocationGroup, (user.id, root_id))
    if group is None:
        db.add(MeasurementLocationGroup(user_id=user.id, root_id=root_id, name=name))
        db.flush()
    else:
        group.name = name
    if current is None:
        db.add(MeasurementLocationLink(user_id=user.id, root_id=root_id, location_id=child_id))
    db.commit()
    return {"location_id": root_id}


def unlink_measurement_location(db, device_id, root_id, child_id, *, user):
    areas, options = editable_locations(db, device_id, user)
    link = db.get(MeasurementLocationLink, (user.id, child_id))
    if root_id not in options or child_id not in areas or link is None or link.root_id != root_id:
        raise HTTPException(404, "Vínculo não encontrado.")

    db.delete(link)
    db.flush()  # The application session disables autoflush.
    remaining = db.scalars(select(MeasurementLocationLink.location_id).where(
        MeasurementLocationLink.user_id == user.id, MeasurementLocationLink.root_id == root_id
    )).all()
    if not remaining:
        db.delete(db.get(MeasurementLocationGroup, (user.id, root_id)))
    db.commit()
    keep_root = root_id in areas or any(child in areas for child in remaining)
    return {"location_id": root_id if keep_root else child_id}
