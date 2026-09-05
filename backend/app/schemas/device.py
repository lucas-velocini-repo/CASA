from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeviceCreate(BaseModel):
    device_id: str
    name: str
    hardware_id: str | None = None


class DeviceResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: int
    device_id: str
    hardware_id: str | None
    name: str

    firmware_version: str | None
    active: bool

    created_at: datetime
    last_seen: datetime | None

class DeviceRegisterRequest(BaseModel):
    hardware_id: str
    name: str

class DeviceRegisterResponse(BaseModel):
    device_id: str
    hardware_id: str
    name: str