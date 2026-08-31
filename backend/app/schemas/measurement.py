from pydantic import BaseModel, Field
from datetime import datetime


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

    values: SensorValuesResponse