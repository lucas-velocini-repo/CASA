import base64
import hashlib
import os
import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pwdlib import PasswordHash

from app.core import config  # noqa: F401 -- load .env before reading security settings.

ENV = os.getenv("CASA_ENV", "production")
if ENV not in ("production", "development", "test"):
    raise RuntimeError("CASA_ENV deve ser production, development ou test.")
PRODUCTION = ENV == "production"
APP_URL = os.getenv("PUBLIC_APP_URL", "http://localhost:5173").rstrip("/")
parts = urlsplit(APP_URL)
if (
    not parts.hostname
    or parts.username
    or parts.password
    or parts.query
    or parts.fragment
    or parts.path
):
    raise RuntimeError("PUBLIC_APP_URL deve conter somente a origem, sem caminho.")
if PRODUCTION and parts.scheme != "https":
    raise RuntimeError("Contas em produção exigem PUBLIC_APP_URL com HTTPS.")
if parts.scheme not in ("http", "https"):
    raise RuntimeError("PUBLIC_APP_URL inválida.")
key = os.getenv("AUTH_ENCRYPTION_KEY")
if not key:
    if PRODUCTION:
        raise RuntimeError("Defina AUTH_ENCRYPTION_KEY (Fernet) antes de iniciar.")
    key = base64.urlsafe_b64encode(
        hashlib.sha256(b"CASA-local-development-only").digest()
    ).decode()
BOX = Fernet(key.encode())
COOKIE = "__Host-casa_session" if PRODUCTION else "casa_session"
CSRF_COOKIE = "__Host-casa_csrf" if PRODUCTION else "casa_csrf"
PASSWORDS = PasswordHash.recommended()
DUMMY_HASH = PASSWORDS.hash(secrets.token_urlsafe(32))


def utcnow():
    return datetime.now(timezone.utc)


def aware(value):
    return (
        value.replace(tzinfo=timezone.utc)
        if value.tzinfo is None
        else value.astimezone(timezone.utc)
    )


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def encrypt(value):
    return BOX.encrypt(value.encode()).decode()


def decrypt(value):
    return BOX.decrypt(value.encode()).decode()


def verify_password(password, hashed):
    try:
        return PASSWORDS.verify(password, hashed or DUMMY_HASH)
    except Exception:
        return False
