"""Versioned station measurement interval, independent of historical measurements."""
from alembic import op
import sqlalchemy as sa

revision = "d720interval01"
down_revision = "c621accounts01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "station_configurations",
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("devices.id"), primary_key=True),
        sa.Column("desired_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reported_interval_seconds", sa.Integer(), nullable=True),
        sa.Column("applied_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("firmware_version", sa.String(30), nullable=True),
    )


def downgrade():
    op.drop_table("station_configurations")
