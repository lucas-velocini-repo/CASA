"""Save personal names for measurement locations."""

import sqlalchemy as sa
from alembic import op


revision = "f922locationnames01"
down_revision = "e821locations01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "measurement_location_names",
        sa.Column("location_id", sa.Integer(), sa.ForeignKey(
            "measurement_locations.id", ondelete="CASCADE"
        ), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey(
            "users.id", ondelete="CASCADE"
        ), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
    )
    op.create_index(
        "ix_measurement_location_names_user_id", "measurement_location_names", ["user_id"]
    )


def downgrade():
    op.drop_table("measurement_location_names")
