from datetime import datetime, timedelta, timezone

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class DeviceLocationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    acquired_at: AwareDatetime

    @field_validator("acquired_at")
    @classmethod
    def validate_acquisition_time(cls, value: datetime) -> datetime:
        value = value.astimezone(timezone.utc)
        if value < datetime(2024, 1, 1, tzinfo=timezone.utc):
            raise ValueError("Acquisition time must be on or after 2024-01-01")
        if value > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Acquisition time is in the future")
        return value


class DeviceLocationResponse(BaseModel):
    device_id: str
    latitude: float
    longitude: float
    location_updated_at: datetime
    status: str


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
