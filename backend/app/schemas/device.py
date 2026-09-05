from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DeviceCreate(BaseModel):
    device_id: str
    name: str
    hardware_id: str | None = None
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )


class DeviceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    hardware_id: str | None
    name: str

    latitude: float | None = None
    longitude: float | None = None
    location_updated_at: datetime | None = None

    firmware_version: str | None
    active: bool

    created_at: datetime
    last_seen: datetime | None


class DeviceRegisterRequest(BaseModel):
    hardware_id: str
    name: str
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
    )


class DeviceRegisterResponse(BaseModel):
    device_id: str
    hardware_id: str
    name: str
    api_token: str | None = None
