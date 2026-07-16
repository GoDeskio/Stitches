"""Iteration 26 regression tests: refactor router split + N8N run history + MCP tools."""
import os
import pytest
import requests

def _read_env():
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip()
    except Exception:
        return None
    return None

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or _read_env() or "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL missing"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def demo_headers():
    return {"Authorization": f"Bearer {_login('demo@stitches.app', 'Demo@123')}"}


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login('admin@stitches.app', 'Admin@123')}"}


# ---------- Refactor regression: smtp_config router ----------
class TestSmtpConfig:
    def test_me_smtp_get(self, demo_headers):
        r = requests.get(f"{BASE_URL}/api/me/smtp-config", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        for k in ("enabled", "host", "port", "username", "from_address", "has_password"):
            assert k in r.json()

    def test_me_smtp_put_and_delete(self, demo_headers):
        put = requests.put(f"{BASE_URL}/api/me/smtp-config", headers=demo_headers, json={
            "enabled": False, "host": "smtp.example.com", "port": 587,
            "username": "u@example.com", "password": "TEST_pw", "from_address": "u@example.com"}, timeout=15)
        assert put.status_code == 200 and put.json().get("ok")
        get = requests.get(f"{BASE_URL}/api/me/smtp-config", headers=demo_headers, timeout=15).json()
        assert get["host"] == "smtp.example.com" and get["has_password"] is True
        d = requests.delete(f"{BASE_URL}/api/me/smtp-config", headers=demo_headers, timeout=15)
        assert d.status_code == 200

    def test_admin_smtp_crud(self, admin_headers):
        assert requests.get(f"{BASE_URL}/api/admin/smtp-config", headers=admin_headers, timeout=15).status_code == 200
        assert requests.put(f"{BASE_URL}/api/admin/smtp-config", headers=admin_headers, json={
            "enabled": False, "host": "smtp.test.com", "port": 587,
            "username": "a@x.com", "password": "pw", "from_address": "a@x.com"}, timeout=15).status_code == 200
        get = requests.get(f"{BASE_URL}/api/admin/smtp-config", headers=admin_headers, timeout=15).json()
        assert get["host"] == "smtp.test.com"
        assert requests.delete(f"{BASE_URL}/api/admin/smtp-config", headers=admin_headers, timeout=15).status_code == 200


# ---------- Refactor regression: sfu_config router ----------
class TestSfuConfig:
    def test_admin_sfu_crud(self, admin_headers):
        assert requests.get(f"{BASE_URL}/api/admin/sfu-config", headers=admin_headers, timeout=15).status_code == 200
        r = requests.put(f"{BASE_URL}/api/admin/sfu-config", headers=admin_headers, json={
            "enabled": False, "url": "wss://livekit.test", "api_key": "k", "api_secret": "s"}, timeout=15)
        assert r.status_code == 200
        get = requests.get(f"{BASE_URL}/api/admin/sfu-config", headers=admin_headers, timeout=15).json()
        assert get["url"] == "wss://livekit.test" and get["has_secret"] is True
        assert requests.delete(f"{BASE_URL}/api/admin/sfu-config", headers=admin_headers, timeout=15).status_code == 200


# ---------- Refactor regression: rtc_config router ----------
class TestRtcConfig:
    def test_admin_rtc_crud(self, admin_headers):
        assert requests.get(f"{BASE_URL}/api/admin/rtc-config", headers=admin_headers, timeout=15).status_code == 200
        r = requests.put(f"{BASE_URL}/api/admin/rtc-config", headers=admin_headers, json={
            "urls": "turn:turn.test:3478", "username": "u", "credential": "c"}, timeout=15)
        assert r.status_code == 200
        get = requests.get(f"{BASE_URL}/api/admin/rtc-config", headers=admin_headers, timeout=15).json()
        assert get["urls"].startswith("turn:")
        assert requests.delete(f"{BASE_URL}/api/admin/rtc-config", headers=admin_headers, timeout=15).status_code == 200

    def test_rtc_config_public(self, demo_headers):
        r = requests.get(f"{BASE_URL}/api/rtc/config", headers=demo_headers, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert isinstance(j.get("iceServers"), list) and len(j["iceServers"]) >= 1
        assert "sfu" in j and "enabled" in j["sfu"]


# ---------- Refactor regression: meetings router ----------
class TestMeetings:
    def test_meeting_none(self, demo_headers):
        r = requests.post(f"{BASE_URL}/api/meetings", headers=demo_headers, json={
            "name": "TEST_iter26_none"}, timeout=15)
        assert r.status_code == 200
        m = r.json()
        assert m["room_id"].startswith("room_") and m["recurrence"] == "none"
        # GET
        g = requests.get(f"{BASE_URL}/api/meetings/{m['room_id']}", headers=demo_headers, timeout=15)
        assert g.status_code == 200 and g.json()["room_id"] == m["room_id"]
        # ICS
        ics = requests.get(f"{BASE_URL}/api/meetings/{m['room_id']}/ics", headers=demo_headers, timeout=15)
        assert ics.status_code == 200
        assert "text/calendar" in ics.headers.get("content-type", "")
        assert "BEGIN:VCALENDAR" in ics.text
        assert "RRULE" not in ics.text  # non-recurring

    def test_meeting_weekly_expansion_and_ics_rrule(self, demo_headers):
        from datetime import datetime, timezone, timedelta
        start = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(microsecond=0).isoformat()
        r = requests.post(f"{BASE_URL}/api/meetings", headers=demo_headers, json={
            "name": "TEST_iter26_weekly", "scheduled_at": start, "recurrence": "weekly"}, timeout=15)
        assert r.status_code == 200
        rid = r.json()["room_id"]
        ics = requests.get(f"{BASE_URL}/api/meetings/{rid}/ics", headers=demo_headers, timeout=15)
        assert ics.status_code == 200 and "RRULE:FREQ=WEEKLY" in ics.text
        up = requests.get(f"{BASE_URL}/api/meetings/upcoming", headers=demo_headers, timeout=15)
        assert up.status_code == 200
        weekly_occ = [x for x in up.json() if x.get("room_id") == rid]
        assert len(weekly_occ) >= 2, f"expected >=2 weekly occurrences, got {len(weekly_occ)}"

    def test_meeting_daily(self, demo_headers):
        from datetime import datetime, timezone, timedelta
        start = (datetime.now(timezone.utc) + timedelta(hours=2)).replace(microsecond=0).isoformat()
        r = requests.post(f"{BASE_URL}/api/meetings", headers=demo_headers, json={
            "name": "TEST_iter26_daily", "scheduled_at": start, "recurrence": "daily"}, timeout=15)
        assert r.status_code == 200 and r.json()["recurrence"] == "daily"
        ics = requests.get(f"{BASE_URL}/api/meetings/{r.json()['room_id']}/ics", headers=demo_headers, timeout=15)
        assert "RRULE:FREQ=DAILY" in ics.text

    def test_admin_meetings(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/meetings", headers=admin_headers, timeout=15)
        assert r.status_code == 200 and isinstance(r.json(), list)
        if r.json():
            rid = r.json()[0]["room_id"]
            end = requests.post(f"{BASE_URL}/api/admin/meetings/{rid}/end", headers=admin_headers, timeout=15)
            assert end.status_code == 200 and end.json().get("ok") is True


# ---------- NEW: N8N run history ----------
class TestN8NRunHistory:
    def test_n8n_run_and_history(self, demo_headers):
        # Create integration via API
        c = requests.post(f"{BASE_URL}/api/integrations", headers=demo_headers, json={
            "type": "n8n", "name": "TEST_iter26_n8n", "auth_method": "url",
            "config": {"webhook_url": "https://httpbin.org/post"}}, timeout=30)
        assert c.status_code == 200, c.text
        iid = c.json()["integration_id"]
        try:
            run = requests.post(f"{BASE_URL}/api/integrations/{iid}/run", headers=demo_headers,
                                json={"payload": {"hello": "world"}}, timeout=30)
            assert run.status_code == 200
            body = run.json()
            assert body["ok"] is True and body["status_code"] == 200
            hist = requests.get(f"{BASE_URL}/api/integrations/{iid}/runs", headers=demo_headers, timeout=15)
            assert hist.status_code == 200
            items = hist.json()
            assert isinstance(items, list) and len(items) >= 1
            assert items[0]["ok"] is True and items[0]["kind"] == "run"
        finally:
            requests.delete(f"{BASE_URL}/api/integrations/{iid}", headers=demo_headers, timeout=15)
            after = requests.get(f"{BASE_URL}/api/integrations/{iid}/runs", headers=demo_headers, timeout=15)
            assert after.status_code == 404


# ---------- NEW: MCP tools graceful ----------
class TestMcpTools:
    def test_mcp_tools_graceful_on_non_mcp(self, demo_headers):
        c = requests.post(f"{BASE_URL}/api/integrations", headers=demo_headers, json={
            "type": "mcp", "name": "TEST_iter26_mcp", "auth_method": "token",
            "config": {"server_url": "https://httpbin.org/status/200"}}, timeout=30)
        assert c.status_code == 200, c.text
        iid = c.json()["integration_id"]
        try:
            r = requests.get(f"{BASE_URL}/api/integrations/{iid}/mcp/tools", headers=demo_headers, timeout=30)
            # graceful: must not be 500
            assert r.status_code != 500, f"crashed: {r.text}"
            # ideally 200 with empty tools
            if r.status_code == 200:
                assert r.json().get("tools") == []
            else:
                assert r.status_code in (400, 502)
        finally:
            requests.delete(f"{BASE_URL}/api/integrations/{iid}", headers=demo_headers, timeout=15)
