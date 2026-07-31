"""Iteration 55 — background webhook retries + Ops overview widget."""
import os
import time
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN_EMAIL = "admin@stitches.app"
ADMIN_PASS = "Admin@123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def hdr(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# --- Ops overview endpoint ---
class TestOpsOverview:
    def test_ops_overview_shape(self, hdr):
        r = requests.get(f"{BASE_URL}/api/admin/deploy/ops-overview", headers=hdr, timeout=15)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        for k in ["overall", "open_incidents", "subscribers", "status_public",
                  "generated_at", "recent_deliveries", "next_maintenance"]:
            assert k in data, f"missing key {k}"
        assert data["overall"] in ("operational", "degraded", "outage")
        assert isinstance(data["open_incidents"], int)
        assert isinstance(data["subscribers"], int)
        assert isinstance(data["status_public"], bool)
        assert isinstance(data["recent_deliveries"], list)


# --- Background retries ---
class TestBackgroundRetries:
    def _set_channels(self, hdr, webhook_url):
        payload = {
            "email_enabled": True,
            "slack_webhook": "", "slack_mode": "all",
            "webhook_url": webhook_url, "webhook_mode": "all",
            "discord_webhook": "", "discord_mode": "all",
            "whatsapp_webhook": "", "whatsapp_mode": "all",
        }
        r = requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=hdr, json=payload, timeout=15)
        assert r.status_code == 200, r.text[:300]

    def test_send_test_alert_returns_fast_on_failing_webhook(self, hdr):
        self._set_channels(hdr, "https://httpbin.org/status/500")
        t0 = time.monotonic()
        r = requests.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test", headers=hdr, timeout=10)
        elapsed = time.monotonic() - t0
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("ok") is True
        assert body.get("queued") is True, f"expected queued:true, got {body}"
        assert elapsed < 2.0, f"expected fast return, took {elapsed:.2f}s"
        # Wait for background retries (3 attempts, backoff [1,3] => ~4-6s)
        time.sleep(8)
        d = requests.get(f"{BASE_URL}/api/admin/deploy/alert-channels/deliveries", headers=hdr, timeout=15).json()
        webhooks = d.get("deliveries", {}).get("webhook", [])
        assert webhooks, "no webhook deliveries recorded"
        latest = webhooks[0]
        assert latest.get("attempts") == 3, f"expected 3 attempts, got {latest}"
        assert latest.get("ok") is False, f"expected ok=false, got {latest}"
        assert latest.get("status") == 500, f"expected status=500, got {latest}"

    def test_successful_send_logs_one_attempt(self, hdr):
        self._set_channels(hdr, "https://httpbin.org/post")
        t0 = time.monotonic()
        r = requests.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test", headers=hdr, timeout=10)
        elapsed = time.monotonic() - t0
        assert r.status_code == 200
        assert r.json().get("queued") is True
        assert elapsed < 2.0, f"expected fast return, took {elapsed:.2f}s"
        time.sleep(4)
        d = requests.get(f"{BASE_URL}/api/admin/deploy/alert-channels/deliveries", headers=hdr, timeout=15).json()
        webhooks = d.get("deliveries", {}).get("webhook", [])
        assert webhooks, "no webhook deliveries recorded"
        latest = webhooks[0]
        assert latest.get("attempts") == 1, f"expected 1 attempt, got {latest}"
        assert latest.get("ok") is True, f"expected ok=true, got {latest}"


# --- Regression: per-channel Test still returns immediate result ---
class TestPerChannelSync:
    def test_test_one_returns_immediate_result_success(self, hdr):
        r = requests.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test-one",
                          headers=hdr, json={"channel": "webhook", "url": "https://httpbin.org/post"}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        assert r.json().get("status") == 200

    def test_test_one_returns_immediate_result_fail(self, hdr):
        r = requests.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test-one",
                          headers=hdr, json={"channel": "webhook", "url": "https://httpbin.org/status/500"}, timeout=15)
        # test-one is sync — a 5xx becomes 502 or an ok:false
        assert r.status_code in (200, 502)


# --- Cleanup ---
def test_zzz_cleanup(hdr):
    payload = {
        "email_enabled": True,
        "slack_webhook": "", "slack_mode": "all",
        "webhook_url": "", "webhook_mode": "all",
        "discord_webhook": "", "discord_mode": "all",
        "whatsapp_webhook": "", "whatsapp_mode": "all",
    }
    r = requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=hdr, json=payload, timeout=15)
    assert r.status_code == 200
