import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models.device import Device
from app.services.device_auth_service import hash_api_token


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        for i, active in enumerate([True, True, False], start=1):
            db.add(Device(
                device_id=f"CASA-{i:06d}", name=f"Station {i}", active=active,
                api_token_hash=hash_api_token(f"token-{i}"),
                last_seen=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ))
        db.commit()

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def payload(**changes):
    result = {
        "latitude": -23.123456, "longitude": -47.123456,
        "acquired_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
    }
    result.update(changes)
    return result


def patch(client, data, token="token-1"):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.patch("/devices/location", json=data, headers=headers)


@pytest.mark.parametrize("token,status", [(None, 401), ("wrong", 401), ("token-3", 403)])
def test_authentication(client, token, status):
    assert patch(client, payload(), token).status_code == status
    assert all(d["latitude"] is None for d in client.get("/devices").json())


def test_persists_for_authenticated_device_and_does_not_change_last_seen(client):
    before = client.get("/devices").json()
    response = patch(client, payload())
    assert response.status_code == 200
    assert response.json()["status"] == "stored"
    devices = client.get("/devices").json()
    assert devices[0]["latitude"] == -23.123456
    assert devices[0]["longitude"] == -47.123456
    assert devices[0]["location_updated_at"] is not None
    assert devices[0]["last_seen"] == before[0]["last_seen"]
    assert devices[1]["latitude"] is None


def test_offline_retries_equal_and_older_times_cannot_overwrite_newer_fix(client):
    data = payload()
    assert patch(client, data).json()["status"] == "stored"
    assert patch(client, data).json()["status"] == "unchanged"
    # An equal timestamp with different coordinates also cannot overwrite it.
    assert patch(client, {**data, "latitude": 10}).json()["status"] == "unchanged"
    older = payload(acquired_at="2024-01-01T00:00:00Z", latitude=20)
    assert patch(client, older).json()["status"] == "unchanged"
    assert client.get("/devices").json()[0]["latitude"] == data["latitude"]
    newer = payload(acquired_at=datetime.now(timezone.utc).isoformat(), latitude=0, longitude=0)
    assert patch(client, newer).json()["status"] == "stored"
    assert client.get("/devices").json()[0]["latitude"] == 0


@pytest.mark.parametrize("changes", [
    {"latitude": 91}, {"longitude": -181}, {"latitude": None},
    {"acquired_at": "2026-01-01T12:00:00"},  # naive time rejected
    {"acquired_at": "1970-01-01T00:00:00Z"},
    {"acquired_at": "2100-01-01T00:00:00Z"},
    {"device_id": "CASA-000002"},  # token, not caller-supplied identity
])
def test_invalid_location_rejected_without_mutation(client, changes):
    assert patch(client, payload(**changes)).status_code == 422
    assert client.get("/devices").json()[0]["latitude"] is None


def test_epoch_seconds_and_offset_datetime_are_supported(client):
    epoch = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp())
    assert patch(client, payload(acquired_at=epoch)).status_code == 200
    assert patch(client, payload(acquired_at="2024-01-01T03:00:00+03:00")).json()["status"] == "unchanged"


def test_environmental_measurement_does_not_refresh_location_date(client):
    patch(client, payload())
    before = client.get("/devices").json()[0]["location_updated_at"]
    measurement = {
        "device_id": "CASA-000001", "timestamp": 1780000000,
        "latitude": None, "longitude": None, "pm": {}, "nc": {},
    }
    response = client.post("/measurements", json=measurement,
        headers={"Authorization": "Bearer token-1"})
    assert response.status_code == 201
    assert client.get("/devices").json()[0]["location_updated_at"] == before
