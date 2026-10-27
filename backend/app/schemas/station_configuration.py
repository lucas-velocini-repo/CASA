from pydantic import BaseModel, ConfigDict, Field


class IntervalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    interval_seconds: int = Field(strict=True, ge=30, le=86400)


class ConfigurationReport(IntervalRequest):
    revision: int = Field(strict=True, ge=0, le=2147483647)
    firmware_version: str = Field(min_length=1, max_length=30)
