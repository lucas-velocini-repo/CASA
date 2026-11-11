"""Group measurements by location and classify existing coordinates."""

from dataclasses import dataclass, field

import sqlalchemy as sa
from alembic import op

from app.services.location_grouping import (
    add_reference_sample,
    closest_location,
    valid_coordinates,
)


revision = "e821locations01"
down_revision = "d720interval01"
branch_labels = None
depends_on = None


@dataclass
class Location:
    id: int
    latitude: float
    longitude: float
    samples: list[list[float]] = field(default_factory=list)


def backfill(db, locations):
    measurements = sa.table(
        "measurements",
        sa.column("id", sa.Integer()),
        sa.column("device_id", sa.Integer()),
        sa.column("timestamp", sa.DateTime(timezone=True)),
        sa.column("latitude", sa.Float()),
        sa.column("longitude", sa.Float()),
        sa.column("location_id", sa.Integer()),
    )
    has_coordinates = sa.and_(
        measurements.c.latitude.is_not(None),
        measurements.c.longitude.is_not(None),
    )
    devices = db.scalars(
        sa.select(measurements.c.device_id).where(has_coordinates).distinct()
    ).all()
    assign_location = (
        measurements.update()
        .where(measurements.c.id == sa.bindparam("measurement_id"))
        .values(location_id=sa.bindparam("group_id"))
    )
    for device_id in devices:
        groups = []
        cursor = None
        query = (
            sa.select(measurements)
            .where(measurements.c.device_id == device_id, has_coordinates)
            .order_by(measurements.c.timestamp)
            .limit(1000)
        )
        while True:
            page = query if cursor is None else query.where(measurements.c.timestamp > cursor)
            rows = db.execute(page).all()
            if not rows:
                break
            cursor = rows[-1].timestamp
            assignments = []
            changed_groups = {}
            for row in rows:
                if not valid_coordinates(row.latitude, row.longitude):
                    continue
                group = closest_location(groups, row.latitude, row.longitude, radius_meters=20)
                if group is None:
                    result = db.execute(locations.insert().values(
                        device_id=device_id,
                        latitude=row.latitude,
                        longitude=row.longitude,
                        samples=[],
                    ))
                    group = Location(result.inserted_primary_key[0], row.latitude, row.longitude)
                    groups.append(group)
                if add_reference_sample(group, row.latitude, row.longitude):
                    changed_groups[group.id] = group
                assignments.append({"measurement_id": row.id, "group_id": group.id})

            for group in changed_groups.values():
                db.execute(locations.update().where(locations.c.id == group.id).values(
                    latitude=group.latitude, longitude=group.longitude, samples=group.samples
                ))
            if assignments:
                db.execute(assign_location, assignments)


def upgrade():
    locations = op.create_table(
        "measurement_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("samples", sa.JSON(), nullable=False),
    )
    op.create_index("ix_measurement_locations_device_id", "measurement_locations", ["device_id"])
    with op.batch_alter_table("measurements") as batch:
        batch.add_column(sa.Column("location_id", sa.Integer()))
        batch.add_column(sa.Column("location_fallback_at", sa.DateTime(timezone=True)))
        batch.create_foreign_key(
            "fk_measurements_location_id", "measurement_locations",
            ["location_id"], ["id"], ondelete="SET NULL",
        )
    backfill(op.get_bind(), locations)
    op.create_index(
        "ix_measurements_device_location_timestamp", "measurements",
        ["device_id", "location_id", "timestamp"],
    )


def downgrade():
    op.drop_index("ix_measurements_device_location_timestamp", table_name="measurements")
    with op.batch_alter_table("measurements") as batch:
        batch.drop_constraint("fk_measurements_location_id", type_="foreignkey")
        batch.drop_column("location_fallback_at")
        batch.drop_column("location_id")
    op.drop_table("measurement_locations")
