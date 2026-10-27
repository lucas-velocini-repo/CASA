import pytest
from test_accounts import env, auth  # noqa: F401 — shared database fixture


def test_permissions_and_station_scoping(env):
    client, _ = env
    assert client.get("/admin/device-configurations").status_code == 401
    assert client.get("/admin/device-configurations", headers=auth("alice")).status_code == 403
    assert client.patch("/admin/devices/1/configuration", headers=auth("alice"), json={"interval_seconds": 60}).status_code == 403
    assert client.get("/devices/config", headers=auth()).status_code == 401
    assert client.get("/devices/config").status_code == 401
    assert client.get("/devices/config", headers=auth("device-1")).json() == {"revision": 0, "interval_seconds": None}
    r = client.patch("/admin/devices/1/configuration", headers=auth(), json={"interval_seconds": 60})
    assert r.status_code == 200 and r.json()["pending"]
    assert client.get("/devices/config", headers=auth("device-1")).json() == {"revision": 1, "interval_seconds": 60}
    assert client.get("/devices/config", headers=auth("device-2")).json()["interval_seconds"] is None
    assert client.patch("/admin/devices/999/configuration", headers=auth(), json={"interval_seconds": 60}).status_code == 404


@pytest.mark.parametrize("seconds", [29, 86401, 30.5, True, "60", None])
def test_invalid_intervals(env, seconds):
    client, _ = env
    assert client.patch("/admin/devices/1/configuration", headers=auth(), json={"interval_seconds": seconds}).status_code == 422


def test_acknowledgement_revisions_and_retries(env):
    client, _ = env
    def set_interval(seconds):
        return client.patch("/admin/devices/1/configuration", headers=auth(), json={"interval_seconds": seconds}).json()
    def report(revision, seconds):
        return client.post("/devices/config/report", headers=auth("device-1"), json={"revision": revision, "interval_seconds": seconds, "firmware_version": "1.2.0"})
    assert report(0, 300).status_code == 200
    assert set_interval(30)["revision"] == 1
    assert set_interval(30)["revision"] == 1
    assert report(1, 60).status_code == 409
    assert report(2, 30).status_code == 409
    assert report(1, 30).json()["pending"] is False
    assert set_interval(600)["revision"] == 2
    assert report(1, 30).json()["pending"] is True
    assert report(2, 600).status_code == 200
    assert report(1, 30).status_code == 200
    row = client.get("/admin/device-configurations", headers=auth()).json()[0]
    assert row["reported_interval_seconds"] == 600 and row["applied_revision"] == 2
    assert row["pending"] is False and row["reported_at"]


def test_eight_character_password_minimum():
    from pydantic import ValidationError
    from app.schemas.accounts import PasswordRequest
    assert PasswordRequest(token="x" * 32, password="Abcd1234").password == "Abcd1234"
    with pytest.raises(ValidationError):
        PasswordRequest(token="x" * 32, password="Abc1234")
