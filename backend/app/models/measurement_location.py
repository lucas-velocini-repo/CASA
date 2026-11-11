from sqlalchemy import JSON, CheckConstraint, Float, ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MeasurementLocation(Base):
    __tablename__ = "measurement_locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), index=True
    )
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    samples: Mapped[list[list[float]]] = mapped_column(JSON)
    area_id: Mapped[int | None] = mapped_column(
        ForeignKey("measurement_locations.id", name="fk_measurement_locations_area_id", ondelete="SET NULL"),
        index=True,
    )


class MeasurementLocationName(Base):
    __tablename__ = "measurement_location_names"

    location_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_locations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(String(80))


class MeasurementLocationGroup(Base):
    __tablename__ = "measurement_location_groups"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    root_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_locations.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    name: Mapped[str] = mapped_column(String(80))


class MeasurementLocationLink(Base):
    __tablename__ = "measurement_location_links"
    __table_args__ = (
        ForeignKeyConstraint(
            ["user_id", "root_id"],
            ["measurement_location_groups.user_id", "measurement_location_groups.root_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("location_id <> root_id", name="ck_location_link_distinct"),
    )

    user_id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("measurement_locations.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    root_id: Mapped[int] = mapped_column()
