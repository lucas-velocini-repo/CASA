"""Consolidate nearby locations and support reversible personal links."""

from collections import defaultdict

import sqlalchemy as sa
from alembic import op

from app.services.location_grouping import closest_location


revision = "a023locationareas01"
down_revision = "f922locationnames01"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("measurement_locations") as batch:
        batch.add_column(sa.Column("area_id", sa.Integer()))
        batch.create_foreign_key(
            "fk_measurement_locations_area_id", "measurement_locations",
            ["area_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_index("ix_measurement_locations_area_id", ["area_id"])

    locations = sa.table(
        "measurement_locations",
        sa.column("id", sa.Integer()),
        sa.column("device_id", sa.Integer()),
        sa.column("latitude", sa.Float()),
        sa.column("longitude", sa.Float()),
        sa.column("area_id", sa.Integer()),
    )
    db = op.get_bind()
    areas = defaultdict(list)
    rows = db.execute(sa.select(locations).order_by(locations.c.id)).all()
    for location in rows:
        roots = areas[location.device_id]
        root = closest_location(roots, location.latitude, location.longitude, radius_meters=100)
        if root is None:
            roots.append(location)
        else:
            db.execute(locations.update().where(locations.c.id == location.id).values(area_id=root.id))

    op.create_table(
        "measurement_location_groups",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("root_id", sa.Integer(), sa.ForeignKey("measurement_locations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
    )
    op.create_index("ix_measurement_location_groups_root_id", "measurement_location_groups", ["root_id"])
    op.create_table(
        "measurement_location_links",
        sa.Column("user_id", sa.Integer(), primary_key=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("measurement_locations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("root_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id", "root_id"],
            ["measurement_location_groups.user_id", "measurement_location_groups.root_id"],
            ondelete="CASCADE",
        ),
        sa.CheckConstraint("location_id <> root_id", name="ck_location_link_distinct"),
    )
    op.create_index("ix_measurement_location_links_location_id", "measurement_location_links", ["location_id"])


def downgrade():
    op.drop_table("measurement_location_links")
    op.drop_table("measurement_location_groups")
    with op.batch_alter_table("measurement_locations") as batch:
        batch.drop_index("ix_measurement_locations_area_id")
        batch.drop_constraint("fk_measurement_locations_area_id", type_="foreignkey")
        batch.drop_column("area_id")
