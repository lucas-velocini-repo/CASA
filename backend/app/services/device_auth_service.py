import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.device import Device


def generate_api_token() -> str:
    return secrets.token_urlsafe(32)


def hash_api_token(
    token: str,
) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def authenticate_device(
    db: Session,
    token: str,
) -> Device | None:

    token_hash = hash_api_token(token)

    return db.scalar(select(Device).where(Device.api_token_hash == token_hash))
