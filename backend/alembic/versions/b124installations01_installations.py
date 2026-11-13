"""Track physical installations and timestamped GPS fixes."""

import sqlalchemy as sa
from alembic import op

revision = "b124installations01"
down_revision = "a023locationareas01"
branch_labels = depends_on = None


def upgrade():
    op.create_table(
        "station_installations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("backfill_initial", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("device_id", "started_at"),
    )
    op.create_table(
        "station_fixes",
        sa.Column("installation_id", sa.Integer(), sa.ForeignKey("station_installations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("acquired_at", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("measurement_locations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
    )
    op.add_column("device_access", sa.Column("retain_history", sa.Boolean(), server_default=sa.false(), nullable=False))
    with op.batch_alter_table("measurement_locations") as batch:
        batch.add_column(sa.Column("installation_id", sa.Integer()))
        batch.create_foreign_key("fk_measurement_locations_installation", "station_installations", ["installation_id"], ["id"], ondelete="CASCADE")
        batch.create_index("ix_measurement_locations_installation_id", ["installation_id"])


def downgrade():
    op.drop_table("station_fixes")
    with op.batch_alter_table("measurement_locations") as batch:
        batch.drop_index("ix_measurement_locations_installation_id")
        batch.drop_constraint("fk_measurement_locations_installation", type_="foreignkey")
        batch.drop_column("installation_id")
    op.drop_column("device_access", "retain_history")
    op.drop_table("station_installations")
