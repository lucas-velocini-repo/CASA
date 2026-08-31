from sqlalchemy import Float, ForeignKey
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.db.base import Base


class SensorValue(Base):
    __tablename__ = "sensor_values"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    measurement_id: Mapped[int] = mapped_column(
        ForeignKey(
            "measurements.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
    )

    temperature: Mapped[float | None] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float)
    pressure: Mapped[float | None] = mapped_column(Float)
    light: Mapped[float | None] = mapped_column(Float)

    pm1: Mapped[float | None] = mapped_column(Float)
    pm25: Mapped[float | None] = mapped_column(Float)
    pm4: Mapped[float | None] = mapped_column(Float)
    pm10: Mapped[float | None] = mapped_column(Float)

    nc05: Mapped[float | None] = mapped_column(Float)
    nc10: Mapped[float | None] = mapped_column(Float)
    nc25: Mapped[float | None] = mapped_column(Float)
    nc40: Mapped[float | None] = mapped_column(Float)
    nc100: Mapped[float | None] = mapped_column(Float)

    typical_particle_size: Mapped[float | None] = mapped_column(
        Float
    )

    measurement = relationship(
        "Measurement",
        back_populates="sensor_values",
    )