from typing import Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailRequest(StrictModel):
    email: EmailStr = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).casefold()


class LoginRequest(EmailRequest):
    password: str = Field(min_length=1, max_length=128)
    mfa_code: str = Field(default="", max_length=64)
    client: Literal["web", "mobile"] = "web"


class PasswordRequest(StrictModel):
    token: str = Field(min_length=20, max_length=128)
    password: str = Field(min_length=8, max_length=128)


class InviteRequest(EmailRequest):
    name: str = Field(min_length=1, max_length=100)
    role: Literal["user", "admin"] = "user"

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Informe um nome.")
        return value.strip()


class UserUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Literal["user", "admin"] | None = None
    status: Literal["active", "pending", "disabled"] | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Informe um nome.")
        return value.strip() if value else value


class AccessRequest(StrictModel):
    user_id: int
    device_id: int
    data_from: AwareDatetime
    data_until: AwareDatetime | None = None

    @model_validator(mode="after")
    def period(self):
        if self.data_until and self.data_until <= self.data_from:
            raise ValueError("O fim do período deve ser posterior ao início.")
        return self


class MFARequest(StrictModel):
    code: str = Field(min_length=6, max_length=64)


class DeviceUpdate(StrictModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    active: bool | None = None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if value is not None and not value.strip():
            raise ValueError("Informe um nome.")
        return value.strip() if value else value
