"""Backend tests for meeting scheduling with invitees, upcoming, ICS, and admin SMTP config."""
import os
import time
import requests
import pytest
from datetime import datetime, timezone, timedelta

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="module")
def demo():
    return _login("demo@stitches.app", "Demo@123")


@pytest.fixture(scope="module")
def alice():
    return _login("alice@stitches.app", "Alice@123")


@pytest.fixture(scope="module")
def admin():
    return _login("admin@stitches.app", "Admin@123")


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------------- create scheduled meeting with invitees ----------------
def test_create_scheduled_meeting_invites_and_notifies(demo, alice):
    dtok, du = demo
    atok, au = alice
    when = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    body = {"name": "TEST_scheduled_meet", "scheduled_at": when, "invitee_ids": [au["user_id"]]}
    r = requests.post(f"{API}/meetings", json=body, headers=_h(dtok), timeout=15)
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["room_id"].startswith("room_")
    assert m["scheduled_at"] is not None
    assert au["user_id"] in m.get("invitees", [])
    # alice should get a meeting notification
    time.sleep(1)
    rn = requests.get(f"{API}/notifications", headers=_h(atok), timeout=15)
    assert rn.status_code == 200
    payload = rn.json()
    notes = payload.get("notifications", payload) if isinstance(payload, dict) else payload
    assert any(n.get("type") == "meeting" and m["room_id"] in (n.get("link") or "") for n in notes), notes[:3]
    # store for other tests
    with open("/tmp/_meet_room_id", "w") as f:
        f.write(m["room_id"])


def _room():
    with open("/tmp/_meet_room_id") as f:
        return f.read().strip()


def test_upcoming_lists_meeting_for_host_and_invitee(demo, alice):
    dtok, _ = demo
    atok, _ = alice
    for tok in (dtok, atok):
        r = requests.get(f"{API}/meetings/upcoming", headers=_h(tok), timeout=15)
        assert r.status_code == 200
        items = r.json()
        assert any(x["room_id"] == _room() for x in items), [x.get("room_id") for x in items]


def test_ics_endpoint_returns_valid_vcalendar(demo):
    dtok, _ = demo
    r = requests.get(f"{API}/meetings/{_room()}/ics", headers=_h(dtok), timeout=15)
    assert r.status_code == 200
    assert "text/calendar" in r.headers.get("content-type", "")
    body = r.text
    assert body.startswith("BEGIN:VCALENDAR")
    assert "BEGIN:VEVENT" in body and "END:VEVENT" in body
    assert "END:VCALENDAR" in body.strip().split("\r\n")[-1]
    assert f"UID:{_room()}@stitches" in body


# ---------------- admin SMTP config ----------------
def test_smtp_config_admin_gating_and_roundtrip(admin, demo):
    atok, _ = admin
    dtok, _ = demo
    # non-admin 403
    r = requests.get(f"{API}/admin/smtp-config", headers=_h(dtok), timeout=15)
    assert r.status_code == 403

    # admin GET default
    r = requests.get(f"{API}/admin/smtp-config", headers=_h(atok), timeout=15)
    assert r.status_code == 200
    data = r.json()
    for k in ("enabled", "host", "port", "username", "from_address", "has_password"):
        assert k in data
    # password never in plaintext
    assert "password" not in data

    # PUT enabled with values
    put = {"enabled": True, "host": "smtp.example.com", "port": 587,
           "username": "u@example.com", "from_address": "u@example.com", "password": "TEST_pw_123"}
    r = requests.put(f"{API}/admin/smtp-config", json=put, headers=_h(atok), timeout=15)
    assert r.status_code == 200 and r.json().get("ok") is True

    r = requests.get(f"{API}/admin/smtp-config", headers=_h(atok), timeout=15)
    d = r.json()
    assert d["enabled"] is True
    assert d["host"] == "smtp.example.com"
    assert d["port"] == 587
    assert d["username"] == "u@example.com"
    assert d["has_password"] is True

    # CLEANUP: disable + blank
    r = requests.put(f"{API}/admin/smtp-config",
                     json={"enabled": False, "host": "", "port": 587,
                           "username": "", "from_address": "", "password": ""},
                     headers=_h(atok), timeout=15)
    assert r.status_code == 200
    r = requests.get(f"{API}/admin/smtp-config", headers=_h(atok), timeout=15)
    d = r.json()
    assert d["enabled"] is False
    assert d["host"] == ""
