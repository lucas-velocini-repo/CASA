from pydantic import BaseModel, Field, StringConstraints
from datetime import datetime
from typing import Annotated, Literal


LocationFilter = int | Literal["unknown"]


class ParticulateMass(BaseModel):
    pm1: float | None = Field(default=None, alias="1.0")
    pm25: float | None = Field(default=None, alias="2.5")
    pm4: float | None = Field(default=None, alias="4.0")
    pm10: float | None = Field(default=None, alias="10.0")


class ParticleCount(BaseModel):
    nc05: float | None = Field(default=None, alias="0.5")
    nc10: float | None = Field(default=None, alias="1.0")
    nc25: float | None = Field(default=None, alias="2.5")
    nc40: float | None = Field(default=None, alias="4.0")
    nc100: float | None = Field(default=None, alias="10.0")


class MeasurementCreate(BaseModel):
    device_id: str
    timestamp: int

    latitude: float | None = None
    longitude: float | None = None

    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    light: float | None = None

    pm: ParticulateMass
    nc: ParticleCount

    typical_size: float | None = None


class MeasurementResponse(BaseModel):
    measurement_id: int
    device_id: str
    status: str

class SensorValuesResponse(BaseModel):
    temperature: float | None
    humidity: float | None
    pressure: float | None
    light: float | None

    pm1: float | None
    pm25: float | None
    pm4: float | None
    pm10: float | None

    nc05: float | None
    nc10: float | None
    nc25: float | None
    nc40: float | None
    nc100: float | None

    typical_particle_size: float | None


class MeasurementDataResponse(BaseModel):
    measurement_id: int

    device_id: str
    device_name: str

    timestamp: datetime
    received_at: datetime

    latitude: float | None
    longitude: float | None
    location_id: int | None = None

    values: SensorValuesResponse


class MeasurementLocationSummary(BaseModel):
    location_id: int
    latitude: float
    longitude: float
    name: str | None = None


class MeasurementLocationResponse(MeasurementLocationSummary):
    links: list[MeasurementLocationSummary] = Field(default_factory=list)
    grouped: bool = False


LocationName = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=80, pattern=r"^[^\x00]*$")
]


class MeasurementLocationNameUpdate(BaseModel):
    name: LocationName | None


class MeasurementLocationLinkUpdate(BaseModel):
    name: Annotated[LocationName, Field(min_length=1)]


class MeasurementLocationSelection(BaseModel):
    location_id: int


class StationMapVisit(BaseModel):
    start: datetime
    end: datetime


class StationMapPin(BaseModel):
    area_id: int
    location_id: int
    device_id: str
    device_name: str
    name: str | None
    latitude: float
    longitude: float
    status: Literal["active", "inactive", "old"]
    last_measurement: datetime
    visits: list[StationMapVisit]
