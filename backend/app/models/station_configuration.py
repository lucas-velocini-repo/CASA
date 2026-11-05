from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StationConfiguration(Base):
    __tablename__ = "station_configurations"

    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), primary_key=True)
    desired_interval_seconds: Mapped[int | None] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reported_interval_seconds: Mapped[int | None] = mapped_column(Integer)
    applied_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reported_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    firmware_version: Mapped[str | None] = mapped_column(String(30))
