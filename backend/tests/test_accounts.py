import json
import os
from datetime import datetime, timedelta
from http.cookies import SimpleCookie
from urllib.parse import parse_qs, urlsplit

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import auth as auth_api
from app.api import dependencies as auth_dependencies
from app.core.security import (
    APP_URL,
    COOKIE,
    CSRF_COOKIE,
    PASSWORDS,
    aware,
    decrypt,
    digest,
    encrypt,
    utcnow,
)
from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models.accounts import (
    AccountToken,
    DeviceAccess,
    MailJob,
    Provisioning,
    User,
    UserSession,
)
from app.models.device import Device
from app.models.measurement import Measurement
from app.models.measurement_location import MeasurementLocation, MeasurementLocationGroup
from app.services.device_auth_service import hash_api_token

PASSWORD = "Uma frase de teste bem longa!"
PASSWORD_HASH = PASSWORDS.hash(PASSWORD)
PG_ENGINE = (
    create_engine(
        os.environ["TEST_DATABASE_URL"],
        pool_size=1 if os.getenv("TEST_SINGLE_CONNECTION") else 5,
        max_overflow=0 if os.getenv("TEST_SINGLE_CONNECTION") else 5,
    )
    if os.getenv("TEST_DATABASE_URL")
    else None
)
SECRET = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


@pytest.fixture
def env():
    url = os.getenv("TEST_DATABASE_URL", "sqlite://")
    engine = PG_ENGINE or create_engine(
        url,
        **(
            {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}
            if url == "sqlite://"
            else {}
        ),
    )
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        users = [
            User(
                email=f"{name}@example.com",
                name=name,
                password_hash=PASSWORD_HASH,
                role="admin" if name == "admin" else "user",
                status="active",
                totp_secret=encrypt(SECRET) if name == "admin" else None,
                totp_enabled=name == "admin",
            )
            for name in ["admin", "alice", "bob", "empty"]
        ]
        db.add_all(users)
        db.flush()
        for i in range(1, 3):
            db.add(
                Device(
                    device_id=f"CASA-{i:06d}",
                    hardware_id=f"HW-{i}",
                    name=f"Estação {i}",
                    api_token_hash=hash_api_token(f"device-{i}"),
                    active=True,
                )
            )
        db.flush()
        db.add_all(
            [
                DeviceAccess(
                    user_id=users[1].id,
                    device_id=1,
                    granted_by=users[0].id,
                    data_from=utcnow() - timedelta(days=2),
                    data_until=utcnow() - timedelta(days=1),
                ),
                DeviceAccess(
                    user_id=users[2].id,
                    device_id=2,
                    granted_by=users[0].id,
                    data_from=utcnow() - timedelta(days=10),
                ),
            ]
        )
        for user in users:
            db.add(
                UserSession(
                    user_id=user.id,
                    token_hash=digest(user.name),
                    csrf_hash=digest("csrf"),
                    client="mobile",
                    mfa_authenticated=user.role == "admin",
                    expires_at=utcnow() + timedelta(hours=1),
                )
            )
        db.commit()

    def override():
        with Session(engine, autoflush=False) as db:
            yield db

    app.dependency_overrides[get_db] = override
    with TestClient(app) as client:
        yield client, engine
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    if PG_ENGINE is None:
        engine.dispose()


def auth(name="admin"):
    return {"Authorization": f"Bearer {name}"}


def confirm_fixture_coordinates(engine):
    # Simulate acquisition evidence for the historical coordinates used by these tests.
    with Session(engine) as db:
        for measurement in db.scalars(select(Measurement).where(Measurement.location_id.is_not(None))):
            measurement.location_fallback_at = measurement.timestamp
        db.commit()


def send(client, device=1, days=0):
    return client.post(
        "/measurements",
        headers=auth(f"device-{device}"),
        json={
            "device_id": f"CASA-{device:06d}",
            "timestamp": int((utcnow() - timedelta(days=days)).timestamp()),
            "pm": {},
            "nc": {},
        },
    )


@pytest.mark.parametrize(
    "path",
    [
        "/devices",
        "/measurements/latest",
        "/measurements/history?device_id=CASA-000001",
        "/measurements/locations?device_id=CASA-000001",
        "/admin/users",
        "/admin/access",
        "/admin/audit",
    ],
)
def test_anonymous_and_station_tokens_cannot_read(env, path):
    client, _ = env
    assert client.get(path).status_code == 401
    assert client.get(path, headers=auth("device-1")).status_code == 401


def test_server_enforces_station_time_and_location_scope(env):
    client, engine = env
    for days in [0, 1.5, 3]:
        assert send(client, days=days).status_code == 201
    assert send(client, device=2).status_code == 201
    assert [
        d["device_id"] for d in client.get("/devices", headers=auth("alice")).json()
    ] == ["CASA-000001"]
    assert client.get("/devices", headers=auth("empty")).json() == []
    assert client.get("/measurements/latest", headers=auth("empty")).json() == []
    assert (
        client.get(
            "/measurements/history?device_id=CASA-000002", headers=auth("alice")
        ).status_code
        == 404
    )
    history = client.get(
        "/measurements/history?device_id=CASA-000001", headers=auth("alice")
    ).json()
    assert len(history) == 1
    latest = client.get("/measurements/latest", headers=auth("alice")).json()
    assert (
        len(latest) == 1 and latest[0]["measurement_id"] == history[0]["measurement_id"]
    )
    assert len(client.get("/measurements/latest", headers=auth()).json()) == 2
    assert (
        len(
            client.get(
                "/measurements/history?device_id=CASA-000001", headers=auth()
            ).json()
        )
        == 3
    )
    with Session(engine) as db:
        device = db.get(Device, 1)
        device.latitude, device.longitude, device.location_updated_at = 1, 2, utcnow()
        db.commit()
    station = client.get("/devices", headers=auth("alice")).json()[0]
    assert station["latitude"] is None and station["last_seen"] is None
    assert client.delete("/admin/access/1", headers=auth()).status_code == 200
    assert client.get("/devices", headers=auth("alice")).json() == []
    assert (
        client.get(
            "/measurements/history?device_id=CASA-000001", headers=auth("alice")
        ).status_code
        == 404
    )


def test_measurement_locations_group_jitter_freeze_reference_and_respect_access(env):
    client, engine = env
    collected_at = utcnow().replace(microsecond=0) - timedelta(days=1.5)

    def measure(seconds, longitude, device=1):
        response = client.post(
            "/measurements",
            headers=auth(f"device-{device}"),
            json={
                "device_id": f"CASA-{device:06d}",
                "timestamp": int(collected_at.timestamp()) + seconds,
                "latitude": 0,
                "longitude": longitude,
                "pm": {},
                "nc": {},
            },
        )
        assert response.status_code == 201
        return response.json()["measurement_id"]

    # Roughly 1 m between samples at the equator.
    seed = measure(-86400, 0)
    assert measure(-86400, 0.0001) == seed
    for seconds, longitude in enumerate([0, 0, 0.00001, 0.00002, 0.00003, 0.00004]):
        measure(seconds, longitude)
    second_location = measure(7, 0.001)
    returned = measure(8, 0.00009)
    measure(86400, 0.002)
    measure(9, 0, device=2)

    with Session(engine) as db:
        groups = db.scalars(
            select(MeasurementLocation)
            .where(MeasurementLocation.device_id == 1)
            .order_by(MeasurementLocation.id)
        ).all()
        assert len(groups) == 3
        first, second, outside_access = groups
        assert len(first.samples) == 5
        assert first.longitude == pytest.approx(0.00002)
        first_id, second_id, outside_id = first.id, second.id, outside_access.id

    path = "/measurements/locations?device_id=CASA-000001"
    assert client.get(path, headers=auth("bob")).status_code == 404
    assert client.get(path, headers=auth("alice")).json() == []
    confirm_fixture_coordinates(engine)
    assert client.get(path, headers=auth("alice")).json() == [
        {"location_id": first_id, "latitude": 0, "longitude": 0, "name": None, "grouped": False, "links": []},
        {"location_id": second_id, "latitude": 0, "longitude": 0.001, "name": None, "grouped": False, "links": []},
    ]
    history = "/measurements/history?device_id=CASA-000001"
    rows = client.get(f"{history}&location_id={first_id}", headers=auth("alice")).json()
    assert len(rows) == 7
    assert rows[-1]["measurement_id"] == returned
    assert {row["location_id"] for row in rows} == {first_id}
    rows = client.get(f"{history}&location_id={second_id}", headers=auth("alice")).json()
    assert [row["measurement_id"] for row in rows] == [second_location]
    assert client.get(f"{history}&location_id={outside_id}", headers=auth("alice")).json() == []


def test_measurement_location_names_persist_per_account_and_respect_access(env):
    client, engine = env
    device_id = "CASA-000001"
    for days, longitude in [(1.5, 0), (0, 0.001)]:
        response = client.post("/measurements", headers=auth("device-1"), json={
            "device_id": device_id, "timestamp": int((utcnow() - timedelta(days=days)).timestamp()),
            "latitude": 0, "longitude": longitude, "pm": {}, "nc": {},
        })
        assert response.status_code == 201

    confirm_fixture_coordinates(engine)
    locations = f"/measurements/locations?device_id={device_id}"
    visible, hidden = client.get(locations, headers=auth()).json()

    def rename(location_id, name, actor="alice", station=device_id):
        return client.put(
            f"/measurements/locations/{location_id}/name?device_id={station}",
            headers=auth(actor), json={"name": name},
        )

    location_id = visible["location_id"]
    assert rename(location_id, "Horta", "device-1").status_code == 401
    assert rename(location_id, "Horta", "bob").status_code == 404
    assert rename(location_id, "Horta", "admin", "CASA-000002").status_code == 404
    assert rename(hidden["location_id"], "Horta").status_code == 404
    assert rename(location_id, "x" * 81).status_code == 422
    assert rename(location_id, "x\0y").status_code == 422

    assert rename(location_id, "  Horta  ").json()["name"] == "Horta"
    assert client.get(locations, headers=auth("alice")).json() == [{**visible, "name": "Horta"}]
    assert client.get(locations, headers=auth()).json()[0]["name"] is None
    assert rename(location_id, "Jardim", "admin").json()["name"] == "Jardim"
    assert rename(location_id, "Horta 2").json()["name"] == "Horta 2"
    assert rename(location_id, None).json()["name"] is None
    assert client.get(locations, headers=auth("alice")).json() == [visible]
    assert client.get(locations, headers=auth()).json()[0]["name"] == "Jardim"


def test_block_radius_and_manual_location_links_are_reversible_and_personal(env):
    client, engine = env
    device_id = "CASA-000001"
    timestamp = int((utcnow() - timedelta(days=1.5)).timestamp())
    readings = []
    for offset, longitude in enumerate([0, 0.0006, 0.002, 0.0035]):
        result = client.post("/measurements", headers=auth("device-1"), json={
            "device_id": device_id, "timestamp": timestamp + offset,
            "latitude": 0, "longitude": longitude, "pm": {}, "nc": {},
        })
        assert result.status_code == 201
        readings.append(result.json()["measurement_id"])

    base = "/measurements/locations"
    stations = f"?device_id={device_id}"
    alice = auth("alice")
    confirm_fixture_coordinates(engine)
    root, child, other = client.get(base + stations, headers=alice).json()
    root_id, child_id, other_id = (item["location_id"] for item in (root, child, other))
    history = f"/measurements/history{stations}&location_id={root_id}"
    assert [row["measurement_id"] for row in client.get(history, headers=alice).json()] == readings[:2]

    def name(location_id, label):
        return client.put(f"{base}/{location_id}/name{stations}", headers=alice, json={"name": label})

    assert name(root_id, "Principal").status_code == 200
    assert name(child_id, "Pátio").status_code == 200
    link = f"{base}/{root_id}/links/{child_id}{stations}"
    assert client.put(link, headers=auth("bob"), json={"name": "Campus"}).status_code == 404
    assert client.put(link, headers=alice, json={"name": "  "}).status_code == 422
    assert client.put(link, headers=alice, json={"name": "Campus"}).status_code == 200
    assert client.put(link, headers=alice, json={"name": "Campus"}).status_code == 200
    grouped, remaining = client.get(base + stations, headers=alice).json()
    assert remaining["location_id"] == other_id
    assert grouped["location_id"] == root_id and grouped["name"] == "Campus"
    assert grouped["grouped"] and [item["name"] for item in grouped["links"]] == ["Pátio"]
    assert [row["measurement_id"] for row in client.get(history, headers=alice).json()] == readings[:3]
    limited = client.get(history + "&limit=1", headers=alice).json()
    assert limited[0]["measurement_id"] == readings[2]
    assert len(client.get(base + stations, headers=auth()).json()) == 3
    assert [row["measurement_id"] for row in client.get(history, headers=auth()).json()] == readings[:2]

    assert name(root_id, "Campus novo").json()["name"] == "Campus novo"
    assert client.delete(link, headers=auth()).status_code == 404
    assert client.delete(link, headers=alice).json() == {"location_id": root_id}
    restored = client.get(base + stations, headers=alice).json()
    assert [item["name"] for item in restored] == ["Principal", "Pátio", None]
    assert all(not item["grouped"] and not item["links"] for item in restored)
    assert [row["measurement_id"] for row in client.get(history, headers=alice).json()] == readings[:2]

    # A previous version left this group behind when its last link was removed.
    with Session(engine) as db:
        alice_id = db.scalar(select(User.id).where(User.name == "alice"))
        db.add(MeasurementLocationGroup(user_id=alice_id, root_id=root_id, name="Vínculo antigo"))
        db.commit()

    reverse_link = f"{base}/{child_id}/links/{root_id}{stations}"
    assert client.put(reverse_link, headers=alice, json={"name": "Campus de novo"}).status_code == 200
    assert client.delete(reverse_link, headers=alice).status_code == 200
    assert client.put(link, headers=alice, json={"name": "Campus outra vez"}).status_code == 200
    for collected_at, coordinates in [
        (timestamp + 4, {"latitude": 0, "longitude": 0.002}),
        (timestamp + 5, {}),
        (int(utcnow().timestamp()), {"latitude": 0, "longitude": 0.0035}),
    ]:
        assert client.post("/measurements", headers=auth("device-1"), json={
            "device_id": device_id, "timestamp": collected_at,
            "pm": {}, "nc": {}, **coordinates,
        }).status_code == 201

    latest_first = base + stations + "&latest_first=true"
    confirm_fixture_coordinates(engine)
    assert client.get(latest_first, headers=alice).json()[0]["location_id"] == root_id
    assert client.get(latest_first, headers=auth()).json()[0]["location_id"] == other_id
    assert client.delete(link, headers=alice).status_code == 200
    assert client.get(latest_first, headers=alice).json()[0]["location_id"] == child_id


def test_transfer_keeps_other_house_private_and_restores_prior_window(env, monkeypatch):
    from app.api import admin as admin_api

    client, engine = env
    start = utcnow().replace(microsecond=0) - timedelta(minutes=30)
    station = "CASA-000001"
    with Session(engine) as db:
        users = dict(db.execute(select(User.name, User.id)).all())
        db.commit()

    def transfer(name, when):
        monkeypatch.setattr(admin_api, "utcnow", lambda: when)
        response = client.post("/admin/access", headers=auth(), json={
            "user_id": users[name], "device_id": 1, "data_from": when.isoformat(),
            "new_installation": True, "backfill_initial": True,
        })
        assert response.status_code == 201

    def read(when):
        response = client.post("/measurements", headers=auth("device-1"), json={
            "device_id": station, "timestamp": int(when.timestamp()),
            "latitude": 50, "longitude": 50, "pm": {}, "nc": {},
        })
        assert response.status_code == 201

    def fix(when, latitude):
        response = client.patch("/devices/location", headers=auth("device-1"), json={
            "acquired_at": when.isoformat(), "latitude": latitude, "longitude": 0,
        })
        assert response.status_code == 200

    def history(name):
        return client.get(f"/measurements/history?device_id={station}", headers=auth(name)).json()

    transfer("alice", start)
    read(start + timedelta(seconds=1))
    assert history("alice")[0]["latitude"] is None
    fix(start + timedelta(seconds=3), 10)
    assert history("alice")[0]["latitude"] == 10
    transfer("bob", start + timedelta(minutes=10))
    fix(start + timedelta(seconds=4), 10)
    read(start + timedelta(minutes=11))
    assert history("bob")[0]["latitude"] is None
    fix(start + timedelta(minutes=12), 20)
    assert history("bob")[0]["latitude"] == 20
    transfer("alice", start + timedelta(minutes=20))
    read(start + timedelta(minutes=21))
    assert [row["latitude"] for row in history("alice")] == [10, None]
    fix(start + timedelta(minutes=22), 10)
    response = client.get("/measurements/station-map", headers=auth("alice"))
    assert response.status_code == 200
    assert {pin["latitude"] for pin in response.json()} == {10}
    assert client.get("/measurements/station-map", headers=auth("bob")).json() == []


def test_measurement_location_fallback_uses_fix_at_or_before_collection(env):
    client, engine = env
    fixed_at = utcnow().replace(microsecond=0) - timedelta(minutes=1)
    with Session(engine) as db:
        device = db.get(Device, 1)
        device.latitude, device.longitude, device.location_updated_at = 1, 2, fixed_at
        access = db.get(DeviceAccess, 1)
        access.data_from, access.data_until = fixed_at + timedelta(seconds=1), None
        db.commit()

    before_fix = send(client, days=1).json()["measurement_id"]
    after_fix = send(client).json()["measurement_id"]
    history = "/measurements/history?device_id=CASA-000001"
    rows = client.get(history, headers=auth()).json()
    assert rows[1]["measurement_id"] == after_fix
    assert rows[1]["location_id"] is not None
    assert (rows[1]["latitude"], rows[1]["longitude"]) == (1, 2)
    unknown = client.get(f"{history}&location_id=unknown", headers=auth()).json()
    assert [row["measurement_id"] for row in unknown] == [before_fix]
    visible = client.get(f"{history}&location_id=unknown", headers=auth("alice")).json()
    assert [row["measurement_id"] for row in visible] == [after_fix]
    assert visible[0]["location_id"] is None and visible[0]["latitude"] is None
    latest = client.get("/measurements/latest", headers=auth("alice")).json()
    assert latest[0]["longitude"] is None and latest[0]["location_id"] is None
    assert client.get(
        f"{history}&location_id={rows[1]['location_id']}", headers=auth("alice")
    ).json() == []
    assert client.get(
        "/measurements/locations?device_id=CASA-000001", headers=auth("alice")
    ).json() == []


def test_start_inclusive_end_exclusive_for_delayed_measurements(env):
    client, engine = env
    with Session(engine) as db:
        access = db.get(DeviceAccess, 1)
        start = utcnow().replace(microsecond=0) - timedelta(days=2)
        access.data_from, access.data_until = start, start + timedelta(hours=1)
        db.commit()
    for seconds in [-1, 0, 3599, 3600]:
        assert (
            client.post(
                "/measurements",
                headers=auth("device-1"),
                json={
                    "device_id": "CASA-000001",
                    "timestamp": int(start.timestamp()) + seconds,
                    "pm": {},
                    "nc": {},
                },
            ).status_code
            == 201
        )
    assert (
        len(
            client.get(
                "/measurements/history?device_id=CASA-000001", headers=auth("alice")
            ).json()
        )
        == 2
    )


@pytest.mark.parametrize(
    "path,method,body",
    [
        ("/devices", "post", {"device_id": "FAKE", "name": "Fake"}),
        ("/devices/register", "post", {"hardware_id": "new", "name": "New"}),
        ("/admin/invitations", "post", {"email": "e@example.com", "name": "Other"}),
        (
            "/admin/access",
            "post",
            {"user_id": 2, "device_id": 1, "data_from": "2026-01-01T00:00:00Z"},
        ),
        ("/admin/devices/1", "patch", {"active": False}),
    ],
)
def test_regular_users_cannot_administer(env, path, method, body):
    client, _ = env
    assert (
        getattr(client, method)(path, headers=auth("alice"), json=body).status_code
        == 403
    )


def test_blocking_account_revokes_sessions_and_preserves_ingestion(env):
    client, _ = env
    assert (
        client.patch(
            "/admin/users/2", headers=auth(), json={"status": "disabled"}
        ).status_code
        == 200
    )
    assert client.get("/devices", headers=auth("alice")).status_code == 401
    assert send(client).status_code == 201
    assert (
        client.patch(
            "/admin/users/1", headers=auth(), json={"role": "user"}
        ).status_code
        == 409
    )


def extract_link(engine, kind):
    with Session(engine) as db:
        mail = db.scalar(select(MailJob).order_by(MailJob.id.desc()))
        payload = json.loads(decrypt(mail.payload))
        token = parse_qs(urlsplit(payload["body"].splitlines()[3]).fragment)[kind][0]
        assert token not in mail.payload
        assert db.scalar(
            select(AccountToken).where(AccountToken.token_hash == digest(token))
        )
        return token


def test_invite_single_use_reset_revokes_all_sessions_and_generic_response(env):
    client, engine = env
    result = client.post(
        "/admin/invitations",
        headers=auth(),
        json={"email": "New@Example.com", "name": "New"},
    )
    assert result.status_code == 201 and "password_hash" not in result.json()
    token = extract_link(engine, "invite")
    assert (
        client.post(
            "/auth/accept-invite", json={"token": token, "password": PASSWORD}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/accept-invite", json={"token": token, "password": PASSWORD}
        ).status_code
        == 400
    )
    login = client.post(
        "/auth/login",
        json={"email": "new@example.com", "password": PASSWORD, "client": "mobile"},
    )
    assert login.status_code == 200
    session = auth(login.json()["token"])
    assert client.get("/devices", headers=session).json() == []
    present = client.post("/auth/forgot-password", json={"email": "new@example.com"})
    absent = client.post("/auth/forgot-password", json={"email": "absent@example.com"})
    assert present.json() == absent.json()
    token = extract_link(engine, "reset")
    assert (
        client.post(
            "/auth/reset-password",
            json={"token": token, "password": PASSWORD + " Nova"},
        ).status_code
        == 200
    )
    assert client.get("/devices", headers=session).status_code == 401


def test_web_cookie_csrf_origin_logout_and_transport_separation(env):
    client, _ = env
    body = {"email": "alice@example.com", "password": PASSWORD, "client": "web"}
    assert client.post("/auth/login", json=body).status_code == 403
    assert (
        client.post(
            "/auth/login", json=body, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    result = client.post("/auth/login", json=body, headers={"Origin": APP_URL})
    assert result.status_code == 200 and "token" not in result.json()
    assert "HttpOnly" in result.headers.get_list("set-cookie")[0]
    assert client.get("/devices").status_code == 200
    assert client.post("/auth/logout", headers={"Origin": APP_URL}).status_code == 403
    assert (
        client.post(
            "/auth/logout",
            headers={
                "Origin": APP_URL,
                "X-CSRF-Token": client.cookies.get(CSRF_COOKIE),
            },
        ).status_code
        == 200
    )
    assert client.get("/devices").status_code == 401
    client.cookies.set(COOKIE, "alice")
    assert client.get("/devices").status_code == 401


@pytest.mark.parametrize(
    "transport, restricted, lifetime",
    [
        ("web", False, timedelta(days=14)),
        ("mobile", False, timedelta(days=7)),
        ("web", True, timedelta(minutes=10)),
    ],
)
def test_login_expiration_matches_transport_and_cookie(
    env, monkeypatch, transport, restricted, lifetime
):
    client, engine = env
    now = utcnow()
    monkeypatch.setattr(auth_api, "utcnow", lambda: now)
    email = "alice@example.com"
    if restricted:
        email = "admin@example.com"
        with Session(engine) as db:
            admin = db.scalar(select(User).where(User.email == email))
            admin.totp_enabled = False
            db.commit()
    result = client.post(
        "/auth/login",
        json={"email": email, "password": PASSWORD, "client": transport},
        headers={"Origin": APP_URL},
    )
    assert result.status_code == 200
    assert result.json()["mfa_setup_required"] is restricted
    assert datetime.fromisoformat(result.json()["expires_at"]) == now + lifetime
    headers = {}
    if transport == "web":
        cookies = SimpleCookie()
        for value in result.headers.get_list("set-cookie"):
            cookies.load(value)
        for name in (COOKIE, CSRF_COOKIE):
            assert int(cookies[name]["max-age"]) == lifetime.total_seconds()
    else:
        assert "set-cookie" not in result.headers
        headers = auth(result.json()["token"])
    me = client.get("/auth/me", headers=headers)
    assert me.status_code == 200
    assert aware(datetime.fromisoformat(me.json()["expires_at"])) == now + lifetime
    monkeypatch.setattr(auth_dependencies, "utcnow", lambda: now + lifetime)
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_admin_mfa_setup_is_restricted_and_recovery_codes_single_use(env):
    client, engine = env
    with Session(engine) as db:
        user = db.get(User, 1)
        user.totp_enabled, user.totp_secret, user.recovery_hashes = False, None, []
        db.commit()
    body = {"email": "admin@example.com", "password": PASSWORD, "client": "mobile"}
    login = client.post("/auth/login", json=body)
    assert login.json()["mfa_setup_required"]
    headers = auth(login.json()["token"])
    assert client.get("/devices", headers=headers).status_code == 403
    setup = client.post("/auth/mfa/setup", headers=headers).json()
    enabled = client.post(
        "/auth/mfa/enable",
        headers=headers,
        json={"code": pyotp.TOTP(setup["secret"]).now()},
    )
    assert enabled.status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.post("/auth/login", json=body).status_code == 401
    body["mfa_code"] = enabled.json()["recovery_codes"][0]
    assert client.post("/auth/login", json=body).status_code == 200
    assert client.post("/auth/login", json=body).status_code == 401


def test_provisioning_can_resume_and_preserves_existing_credentials(env):
    client, engine = env
    body = {"hardware_id": "HW-NEW", "name": "Nova"}
    a = client.post("/devices/register", headers=auth(), json=body)
    b = client.post("/devices/register", headers=auth(), json=body)
    assert a.status_code == b.status_code == 201 and a.json() == b.json()
    token, device_id = a.json()["api_token"], a.json()["device_id"]
    assert token
    with Session(engine) as db:
        assert token not in db.scalar(select(Provisioning)).encrypted_token
    assert (
        client.post(
            f"/devices/{device_id}/provisioning/confirm", headers=auth()
        ).status_code
        == 200
    )
    assert (
        client.post("/devices/register", headers=auth(), json=body).json()["api_token"]
        is None
    )
    assert (
        client.post(
            "/measurements",
            headers=auth(token),
            json={
                "device_id": device_id,
                "timestamp": int(utcnow().timestamp()),
                "pm": {},
                "nc": {},
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/devices/register",
            headers=auth(),
            json={"hardware_id": "HW-1", "name": "Other"},
        ).json()["api_token"]
        is None
    )
    assert send(client).status_code == 201


def test_account_tokens_cannot_submit_station_data_and_session_expiry(env):
    client, engine = env
    assert (
        client.post(
            "/measurements",
            headers=auth("alice"),
            json={
                "device_id": "CASA-000001",
                "timestamp": int(utcnow().timestamp()),
                "pm": {},
                "nc": {},
            },
        ).status_code
        == 401
    )
    assert (
        client.patch(
            "/devices/location",
            headers=auth("alice"),
            json={"latitude": 1, "longitude": 1, "acquired_at": utcnow().isoformat()},
        ).status_code
        == 401
    )
    with Session(engine) as db:
        session = db.scalar(
            select(UserSession).where(UserSession.token_hash == digest("alice"))
        )
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert client.get("/devices", headers=auth("alice")).status_code == 401


def test_login_rate_limit(env):
    client, _ = env
    for _ in range(10):
        assert (
            client.post(
                "/auth/login",
                json={
                    "email": "unknown@example.com",
                    "password": "wrong",
                    "client": "mobile",
                },
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/auth/login",
            json={
                "email": "unknown@example.com",
                "password": "wrong",
                "client": "mobile",
            },
        ).status_code
        == 429
    )


def test_expired_links_disabled_invites_and_restoring_pending_account(env):
    client, engine = env
    assert (
        client.post(
            "/admin/invitations",
            headers=auth(),
            json={"email": "pending@example.com", "name": "Pending"},
        ).status_code
        == 201
    )
    token = extract_link(engine, "invite")
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == "pending@example.com"))
        link = db.scalar(
            select(AccountToken).where(AccountToken.token_hash == digest(token))
        )
        link.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert (
        client.post(
            "/auth/accept-invite", json={"token": token, "password": PASSWORD}
        ).status_code
        == 400
    )
    assert (
        client.post(f"/admin/users/{user_id}/resend-invite", headers=auth()).status_code
        == 200
    )
    token = extract_link(engine, "invite")
    assert (
        client.patch(
            f"/admin/users/{user_id}", headers=auth(), json={"status": "disabled"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/auth/accept-invite", json={"token": token, "password": PASSWORD}
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/admin/users/{user_id}", headers=auth(), json={"status": "active"}
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/admin/users/{user_id}", headers=auth(), json={"status": "pending"}
        ).status_code
        == 200
    )
    token = extract_link(engine, "invite")
    assert (
        client.post(
            "/auth/accept-invite", json={"token": token, "password": PASSWORD}
        ).status_code
        == 200
    )


def test_expired_provisioning_can_be_restarted_but_working_stations_cannot(env):
    client, engine = env
    body = {"hardware_id": "HW-NEW", "name": "Nova"}
    a = client.post("/devices/register", headers=auth(), json=body).json()
    with Session(engine) as db:
        pending = db.scalar(select(Provisioning))
        pending.expires_at = utcnow() - timedelta(seconds=1)
        device_id = pending.device_id
        db.commit()
    assert (
        client.post("/devices/register", headers=auth(), json=body).status_code == 409
    )
    assert (
        client.post(
            f"/admin/devices/{device_id}/restart-provisioning", headers=auth()
        ).status_code
        == 200
    )
    b = client.post("/devices/register", headers=auth(), json=body).json()
    assert a["device_id"] == b["device_id"] and a["api_token"] != b["api_token"]
    assert (
        client.post("/admin/devices/1/restart-provisioning", headers=auth()).status_code
        == 409
    )


def test_mail_outbox_retries_redacts_payload_and_recovers_expired_lease(
    env, monkeypatch
):
    from app import mail_worker

    client, engine = env
    monkeypatch.setattr(mail_worker, "SessionLocal", lambda: Session(engine))
    assert (
        client.post(
            "/admin/invitations",
            headers=auth(),
            json={"email": "mail@example.com", "name": "Mail"},
        ).status_code
        == 201
    )

    def failing(_):
        raise RuntimeError("SMTP unavailable")

    monkeypatch.setattr(mail_worker, "send_mail", failing)
    assert mail_worker.process_one()
    with Session(engine) as db:
        job = db.scalar(select(MailJob))
        assert job.status == "pending" and job.attempts == 1 and job.payload
        job.status, job.lease_until = "processing", utcnow() - timedelta(seconds=1)
        db.commit()
    deliveries = []
    monkeypatch.setattr(mail_worker, "send_mail", deliveries.append)
    assert mail_worker.process_one()
    assert deliveries[0]["to"] == "mail@example.com"
    with Session(engine) as db:
        job = db.scalar(select(MailJob))
        assert job.status == "sent" and job.payload is None and job.attempts == 2
    assert not mail_worker.process_one()


def test_grant_replaces_old_period_and_role_change_revokes_session(env):
    client, _ = env
    body = {"user_id": 2, "device_id": 1, "data_from": "2026-01-01T00:00:00Z"}
    assert client.post("/admin/access", headers=auth(), json=body).status_code == 201
    access = client.get("/admin/access", headers=auth()).json()
    assert len([a for a in access if a["user_id"] == 2 and not a["revoked_at"]]) == 1
    assert (
        client.patch(
            "/admin/users/2", headers=auth(), json={"role": "admin"}
        ).status_code
        == 200
    )
    assert client.get("/devices", headers=auth("alice")).status_code == 401
    login = client.post(
        "/auth/login",
        json={"email": "alice@example.com", "password": PASSWORD, "client": "mobile"},
    )
    assert login.json()["mfa_setup_required"]


@pytest.mark.skipif(
    PG_ENGINE is None or bool(os.getenv("TEST_SINGLE_CONNECTION")),
    reason="Requires a disposable concurrent PostgreSQL server",
)
def test_concurrent_registration_and_grants(env):
    from concurrent.futures import ThreadPoolExecutor

    client, _ = env

    def register(_):
        return client.post(
            "/devices/register",
            headers=auth(),
            json={"hardware_id": "HW-RACE", "name": "Concorrência"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(register, range(2)))
    assert all(r.status_code == 201 for r in responses)
    assert responses[0].json() == responses[1].json()

    def grant(_):
        return client.post(
            "/admin/access",
            headers=auth(),
            json={"user_id": 2, "device_id": 1, "data_from": "2026-01-01T00:00:00Z"},
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(grant, range(2)))
    assert all(r.status_code == 201 for r in responses)
    accesses = client.get("/admin/access", headers=auth()).json()
    assert (
        len(
            [
                a
                for a in accesses
                if a["user_id"] == 2 and a["device_id"] == 1 and not a["revoked_at"]
            ]
        )
        == 1
    )


@pytest.mark.skipif(
    PG_ENGINE is None or bool(os.getenv("TEST_SINGLE_CONNECTION")),
    reason="Requires a disposable concurrent PostgreSQL server",
)
def test_concurrent_demotions_preserve_an_active_administrator(env):
    from concurrent.futures import ThreadPoolExecutor

    client, engine = env
    with Session(engine) as db:
        other = User(
            email="other-admin@example.com",
            name="Other",
            role="admin",
            status="active",
            password_hash=PASSWORD_HASH,
            verified_at=utcnow(),
            totp_enabled=True,
            totp_secret=encrypt(SECRET),
        )
        db.add(other)
        db.flush()
        other_id = other.id
        db.add(
            UserSession(
                user_id=other.id,
                token_hash=digest("other-admin"),
                csrf_hash=digest("csrf"),
                client="mobile",
                mfa_authenticated=True,
                expires_at=utcnow() + timedelta(hours=1),
            )
        )
        db.commit()

    def demote(item):
        actor, target = item
        return client.patch(
            f"/admin/users/{target}", headers=auth(actor), json={"role": "user"}
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(demote, [("admin", other_id), ("other-admin", 1)]))
    assert any(r.status_code == 200 for r in responses)
    with Session(engine) as db:
        assert (
            len(
                list(
                    db.scalars(
                        select(User).where(
                            User.role == "admin", User.status == "active"
                        )
                    )
                )
            )
            >= 1
        )
