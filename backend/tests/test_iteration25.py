"""Backend tests for iteration 25: per-user SMTP, admin config clear endpoints, and recurring meetings."""
import os
import pytest
import requests
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def demo_token():
    return _login("demo@stitches.app", "Demo@123")


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@stitches.app", "Admin@123")


@pytest.fixture(scope="module")
def demo_headers(demo_token):
    return {"Authorization": f"Bearer {demo_token}"}


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ---------------- Per-user SMTP ----------------
class TestMySmtpConfig:
    def test_get_initial(self, demo_headers):
        r = requests.get(f"{API}/me/smtp-config", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("enabled", "host", "port", "username", "from_address", "has_password"):
            assert k in d, f"missing {k}"

    def test_put_and_get_has_password(self, demo_headers):
        payload = {"enabled": True, "host": "smtp.test.example", "port": 587,
                   "username": "TEST_user@example.com", "password": "s3cretP@ss",
                   "from_address": "TEST_user@example.com"}
        r = requests.put(f"{API}/me/smtp-config", headers=demo_headers, json=payload, timeout=15)
        assert r.status_code == 200 and r.json().get("ok") is True

        g = requests.get(f"{API}/me/smtp-config", headers=demo_headers, timeout=15).json()
        assert g["host"] == "smtp.test.example"
        assert g["username"] == "TEST_user@example.com"
        assert g["has_password"] is True
        assert g["enabled"] is True

    def test_delete_clears(self, demo_headers):
        r = requests.delete(f"{API}/me/smtp-config", headers=demo_headers, timeout=15)
        assert r.status_code == 200 and r.json().get("ok") is True
        g = requests.get(f"{API}/me/smtp-config", headers=demo_headers, timeout=15).json()
        assert g["host"] == ""
        assert g["has_password"] is False


# ---------------- Admin clear endpoints ----------------
class TestAdminClearConfigs:
    def test_smtp_clear(self, admin_headers):
        # Seed a value then clear
        requests.put(f"{API}/admin/smtp-config", headers=admin_headers,
                     json={"enabled": True, "host": "smtp.seed", "port": 587,
                           "username": "seed@x", "password": "seedpw", "from_address": "seed@x"}, timeout=15)
        r = requests.delete(f"{API}/admin/smtp-config", headers=admin_headers, timeout=15)
        assert r.status_code == 200 and r.json().get("ok") is True
        g = requests.get(f"{API}/admin/smtp-config", headers=admin_headers, timeout=15).json()
        assert g["host"] in ("", None) or g["host"] == os.environ.get("SMTP_HOST", "")
        assert g["has_password"] is False

    def test_sfu_clear(self, admin_headers):
        requests.put(f"{API}/admin/sfu-config", headers=admin_headers,
                     json={"enabled": True, "url": "wss://seed", "api_key": "k", "api_secret": "s"}, timeout=15)
        r = requests.delete(f"{API}/admin/sfu-config", headers=admin_headers, timeout=15)
        assert r.status_code == 200 and r.json().get("ok") is True
        g = requests.get(f"{API}/admin/sfu-config", headers=admin_headers, timeout=15).json()
        assert g["has_secret"] is False
        assert g["url"] in ("", None) or g["url"] == os.environ.get("LIVEKIT_URL", "")

    def test_rtc_clear(self, admin_headers):
        requests.put(f"{API}/admin/rtc-config", headers=admin_headers,
                     json={"urls": "turn:seed:3478", "username": "u", "credential": "c"}, timeout=15)
        r = requests.delete(f"{API}/admin/rtc-config", headers=admin_headers, timeout=15)
        assert r.status_code == 200 and r.json().get("ok") is True
        g = requests.get(f"{API}/admin/rtc-config", headers=admin_headers, timeout=15).json()
        assert g["has_credential"] is False
        assert g["urls"] in ("", None) or g["urls"] == os.environ.get("TURN_URLS", "")


# ---------------- Recurring meetings ----------------
class TestRecurringMeetings:
    def test_weekly_expansion(self, demo_headers):
        when = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        r = requests.post(f"{API}/meetings", headers=demo_headers,
                          json={"name": "TEST_weekly_meet", "invitee_ids": [],
                                "scheduled_at": when, "recurrence": "weekly"}, timeout=15)
        assert r.status_code == 200, r.text
        m = r.json()
        assert m["recurrence"] == "weekly"
        room_id = m["room_id"]

        up = requests.get(f"{API}/meetings/upcoming", headers=demo_headers, timeout=15).json()
        occ = [x for x in up if x["room_id"] == room_id]
        assert len(occ) >= 2, f"expected multiple weekly occurrences, got {len(occ)}"
        for o in occ:
            assert o["recurrence"] == "weekly"
        # Confirm ~7-day intervals
        times = sorted([datetime.fromisoformat(o["scheduled_at"]) for o in occ])
        deltas = [(times[i + 1] - times[i]).days for i in range(len(times) - 1)]
        assert all(d == 7 for d in deltas), f"expected 7-day intervals, got {deltas}"

    def test_none_recurrence_once(self, demo_headers):
        when = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
        r = requests.post(f"{API}/meetings", headers=demo_headers,
                          json={"name": "TEST_once_meet", "invitee_ids": [],
                                "scheduled_at": when, "recurrence": "none"}, timeout=15)
        assert r.status_code == 200, r.text
        room_id = r.json()["room_id"]
        up = requests.get(f"{API}/meetings/upcoming", headers=demo_headers, timeout=15).json()
        occ = [x for x in up if x["room_id"] == room_id]
        assert len(occ) == 1, f"expected single occurrence, got {len(occ)}"
        assert occ[0]["recurrence"] == "none"
