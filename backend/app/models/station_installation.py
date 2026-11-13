from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StationInstallation(Base):
    __tablename__ = "station_installations"
    __table_args__ = (UniqueConstraint("device_id", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    backfill_initial: Mapped[bool] = mapped_column()


class StationFix(Base):
    __tablename__ = "station_fixes"

    installation_id: Mapped[int] = mapped_column(
        ForeignKey("station_installations.id", ondelete="CASCADE"), primary_key=True
    )
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("measurement_locations.id", ondelete="CASCADE"))
    latitude: Mapped[float] = mapped_column()
    longitude: Mapped[float] = mapped_column()
