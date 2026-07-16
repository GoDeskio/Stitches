"""Iteration 27 tests: services refactor regression + admin automation activity."""
import os
import time
import pytest
import requests

def _load_backend_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")

BASE = _load_backend_url().rstrip("/")
API = f"{BASE}/api"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@stitches.app", "password": "Admin@123"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def demo_token():
    r = requests.post(f"{API}/auth/login", json={"email": "demo@stitches.app", "password": "Demo@123"}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def H(t):
    return {"Authorization": f"Bearer {t}"}


# ---- Regression: refactored routers still function ----
class TestUserSmtp:
    def test_get_put_delete(self, demo_token):
        r = requests.get(f"{API}/me/smtp-config", headers=H(demo_token), timeout=10)
        assert r.status_code == 200
        payload = {"enabled": False, "host": "smtp.test", "port": 587, "username": "u@test", "password": "p", "from_address": "u@test"}
        r = requests.put(f"{API}/me/smtp-config", headers=H(demo_token), json=payload, timeout=10)
        assert r.status_code == 200, r.text
        r = requests.get(f"{API}/me/smtp-config", headers=H(demo_token), timeout=10)
        assert r.status_code == 200 and r.json().get("host") == "smtp.test"
        r = requests.delete(f"{API}/me/smtp-config", headers=H(demo_token), timeout=10)
        assert r.status_code == 200


class TestAdminConfigs:
    def test_smtp(self, admin_token):
        r = requests.get(f"{API}/admin/smtp-config", headers=H(admin_token), timeout=10)
        assert r.status_code == 200
        r = requests.put(f"{API}/admin/smtp-config", headers=H(admin_token),
                         json={"enabled": False, "host": "smtp.a", "port": 587, "username": "a", "password": "b", "from_address": "a@a"}, timeout=10)
        assert r.status_code == 200
        r = requests.delete(f"{API}/admin/smtp-config", headers=H(admin_token), timeout=10)
        assert r.status_code == 200

    def test_sfu(self, admin_token):
        r = requests.get(f"{API}/admin/sfu-config", headers=H(admin_token), timeout=10)
        assert r.status_code == 200
        r = requests.put(f"{API}/admin/sfu-config", headers=H(admin_token),
                         json={"enabled": False, "url": "wss://x", "api_key": "k", "api_secret": "s"}, timeout=10)
        assert r.status_code == 200
        r = requests.delete(f"{API}/admin/sfu-config", headers=H(admin_token), timeout=10)
        assert r.status_code == 200

    def test_rtc(self, admin_token):
        r = requests.get(f"{API}/admin/rtc-config", headers=H(admin_token), timeout=10)
        assert r.status_code == 200
        r = requests.put(f"{API}/admin/rtc-config", headers=H(admin_token),
                         json={"stun_urls": ["stun:stun.l.google.com:19302"], "turn_url": "", "turn_username": "", "turn_password": ""}, timeout=10)
        assert r.status_code == 200
        r = requests.delete(f"{API}/admin/rtc-config", headers=H(admin_token), timeout=10)
        assert r.status_code == 200


class TestRtcConfigPublic:
    def test_get(self, demo_token):
        r = requests.get(f"{API}/rtc/config", headers=H(demo_token), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "iceServers" in data
        assert "sfu" in data


class TestMeetings:
    def test_create_weekly_upcoming_and_ics(self, demo_token):
        from datetime import datetime, timezone, timedelta
        scheduled = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
        payload = {"name": "TEST_iter27_weekly", "scheduled_at": scheduled,
                   "recurrence": "weekly", "invitee_ids": []}
        r = requests.post(f"{API}/meetings", headers=H(demo_token), json=payload, timeout=15)
        assert r.status_code == 200, r.text
        m = r.json()
        room = m.get("room_id")
        assert room

        r = requests.get(f"{API}/meetings/upcoming", headers=H(demo_token), timeout=10)
        assert r.status_code == 200
        occurrences = [x for x in r.json() if x.get("room_id") == room]
        assert len(occurrences) >= 2, f"expected >=2 weekly occurrences, got {len(occurrences)}"

        r = requests.get(f"{API}/meetings/{room}/ics", headers=H(demo_token), timeout=10)
        assert r.status_code == 200
        assert "text/calendar" in r.headers.get("content-type", "")
        assert "RRULE:FREQ=WEEKLY" in r.text


# ---- New: admin automation activity ----
class TestAdminIntegrationRuns:
    def test_forbidden_for_non_admin(self, demo_token):
        r = requests.get(f"{API}/admin/integration-runs", headers=H(demo_token), timeout=10)
        assert r.status_code == 403

    def test_admin_can_list(self, admin_token):
        r = requests.get(f"{API}/admin/integration-runs", headers=H(admin_token), timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert "runs" in data and "total" in data and "ok_count" in data and "fail_count" in data
        assert data["total"] == data["ok_count"] + data["fail_count"]

    def test_seed_n8n_run_then_visible_to_admin(self, admin_token, demo_token):
        # 1. demo creates n8n integration
        payload = {"type": "n8n", "name": "TEST_iter27_n8n", "auth_method": "webhook",
                   "config": {"webhook_url": "https://httpbin.org/post"}}
        r = requests.post(f"{API}/integrations", headers=H(demo_token), json=payload, timeout=15)
        assert r.status_code == 200, r.text
        iid = r.json()["integration_id"]
        try:
            # 2. run it
            r = requests.post(f"{API}/integrations/{iid}/run", headers=H(demo_token),
                              json={"payload": {"hello": "world"}}, timeout=30)
            # ok or fail (httpbin can be flaky) both record a run
            assert r.status_code in (200, 502), r.text
            time.sleep(1)

            # 3. admin list should include a run for this integration with owner_name='Demo User'
            r = requests.get(f"{API}/admin/integration-runs", headers=H(admin_token), timeout=10)
            assert r.status_code == 200
            runs = r.json()["runs"]
            match = [x for x in runs if x.get("integration_id") == iid]
            assert match, "seeded run should be visible to admin"
            row = match[0]
            assert row.get("integration_name") == "TEST_iter27_n8n"
            assert row.get("integration_type") == "n8n"
            assert row.get("owner_name") == "Demo User"
            assert row.get("kind") == "run"

            # 4. filters
            r = requests.get(f"{API}/admin/integration-runs?kind=run", headers=H(admin_token), timeout=10)
            assert r.status_code == 200
            assert all(x.get("kind") == "run" for x in r.json()["runs"])

            r = requests.get(f"{API}/admin/integration-runs?kind=mcp_call", headers=H(admin_token), timeout=10)
            assert r.status_code == 200
            assert all(x.get("kind") == "mcp_call" for x in r.json()["runs"])

            r = requests.get(f"{API}/admin/integration-runs?ok=true", headers=H(admin_token), timeout=10)
            assert r.status_code == 200
            assert all(x.get("ok") is True for x in r.json()["runs"])

            r = requests.get(f"{API}/admin/integration-runs?ok=false", headers=H(admin_token), timeout=10)
            assert r.status_code == 200
            assert all(x.get("ok") is False for x in r.json()["runs"])
        finally:
            requests.delete(f"{API}/integrations/{iid}", headers=H(demo_token), timeout=10)
