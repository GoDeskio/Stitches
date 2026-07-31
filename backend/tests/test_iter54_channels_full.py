"""Iteration 54 — Full end-to-end QA for alert channels: URLs+modes, test-one, deliveries, retry-backoff."""
import os, time
import pytest, requests
from dotenv import dotenv_values

env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module", autouse=True)
def cleanup(admin_client):
    yield
    # Cleanup: clear channels + modes
    admin_client.put(f"{BASE_URL}/api/admin/deploy/alert-channels", json={
        "slack_webhook": "", "discord_webhook": "", "whatsapp_webhook": "", "webhook_url": "",
        "slack_mode": "all", "discord_mode": "all", "whatsapp_mode": "all", "webhook_mode": "all",
    })


class TestChannelsPersistence:
    def test_save_and_reload(self, admin_client):
        payload = {
            "slack_webhook": "https://httpbin.org/post",
            "discord_webhook": "https://httpbin.org/anything",
            "whatsapp_webhook": "https://httpbin.org/post",
            "webhook_url": "https://httpbin.org/post",
            "slack_mode": "incidents", "discord_mode": "maintenance",
            "whatsapp_mode": "outages", "webhook_mode": "all",
        }
        r = admin_client.put(f"{BASE_URL}/api/admin/deploy/alert-channels", json=payload)
        assert r.status_code == 200
        g = admin_client.get(f"{BASE_URL}/api/admin/deploy/alert-channels").json()
        for k, v in payload.items():
            assert g[k] == v, f"{k}: {g.get(k)} != {v}"


class TestTestOne:
    def test_success_200(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test-one",
                              json={"channel": "slack", "url": "https://httpbin.org/post"})
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is True and j["status"] == 200

    def test_failure_418(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test-one",
                              json={"channel": "discord", "url": "https://httpbin.org/status/418"})
        assert r.status_code == 200
        j = r.json()
        assert j["ok"] is False and j["status"] == 418

    def test_empty_url_400(self, admin_client):
        # First clear the channel URLs to make sure fallback lookup also returns empty
        admin_client.put(f"{BASE_URL}/api/admin/deploy/alert-channels", json={
            "slack_webhook": "", "discord_webhook": "", "whatsapp_webhook": "", "webhook_url": "",
        })
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test-one",
                              json={"channel": "webhook", "url": ""})
        assert r.status_code == 400

    def test_unreachable_502(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test-one",
                              json={"channel": "webhook", "url": "https://nonexistent-host-xyz-stitches.invalid/x"})
        assert r.status_code == 502


class TestDeliveryLog:
    def test_deliveries_grouped(self, admin_client):
        # Produce entries
        admin_client.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test-one",
                          json={"channel": "slack", "url": "https://httpbin.org/post"})
        admin_client.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test-one",
                          json={"channel": "discord", "url": "https://httpbin.org/status/418"})
        r = admin_client.get(f"{BASE_URL}/api/admin/deploy/alert-channels/deliveries")
        assert r.status_code == 200
        d = r.json()["deliveries"]
        assert "slack" in d and "discord" in d
        # each row has status, ok, attempts, at
        for row in d["slack"] + d["discord"]:
            assert "status" in row and "ok" in row and "attempts" in row and "at" in row
        # slack has an ok=True 200, discord has ok=False 418
        assert any(r["ok"] and r["status"] == 200 for r in d["slack"])
        assert any((not r["ok"]) and r["status"] == 418 for r in d["discord"])


class TestRetryBackoff:
    def test_retry_attempts_3_on_500(self, admin_client):
        # Configure webhook to 500 URL, mode=all
        admin_client.put(f"{BASE_URL}/api/admin/deploy/alert-channels", json={
            "slack_webhook": "", "discord_webhook": "", "whatsapp_webhook": "",
            "webhook_url": "https://httpbin.org/status/500",
            "slack_mode": "all", "discord_mode": "all", "whatsapp_mode": "all", "webhook_mode": "all",
        })
        t0 = time.time()
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test", timeout=30)
        elapsed = time.time() - t0
        assert r.status_code == 200
        # Backoff should be ~4s (1s + 3s) minimum
        assert elapsed >= 3.5, f"Retry backoff was too fast: {elapsed:.1f}s"
        # Fetch deliveries and confirm webhook attempts==3 ok==false
        time.sleep(0.5)
        d = admin_client.get(f"{BASE_URL}/api/admin/deploy/alert-channels/deliveries").json()["deliveries"]
        assert "webhook" in d
        latest = d["webhook"][0]
        assert latest["ok"] is False
        assert latest["attempts"] == 3, f"Expected 3 attempts, got {latest['attempts']}"

    def test_success_attempts_1(self, admin_client):
        admin_client.put(f"{BASE_URL}/api/admin/deploy/alert-channels", json={
            "slack_webhook": "", "discord_webhook": "", "whatsapp_webhook": "",
            "webhook_url": "https://httpbin.org/post",
            "webhook_mode": "all",
        })
        admin_client.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test", timeout=30)
        time.sleep(0.5)
        d = admin_client.get(f"{BASE_URL}/api/admin/deploy/alert-channels/deliveries").json()["deliveries"]
        latest = d["webhook"][0]
        assert latest["ok"] is True
        assert latest["attempts"] == 1


class TestRouting:
    def test_maintenance_only_receives_maintenance(self, admin_client):
        # discord=maintenance -> a degraded incident should NOT hit discord.
        # We use unique URLs to detect which fired.
        admin_client.put(f"{BASE_URL}/api/admin/deploy/alert-channels", json={
            "slack_webhook": "",
            "discord_webhook": "https://httpbin.org/status/201",
            "whatsapp_webhook": "https://httpbin.org/status/202",
            "webhook_url": "https://httpbin.org/status/203",
            "discord_mode": "maintenance", "whatsapp_mode": "outages", "webhook_mode": "all",
            "slack_mode": "all",
        })
        # Clear old deliveries by producing a fresh incident
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/status-incidents", json={
            "title": "TEST_iter54 degraded", "component": "api", "severity": "degraded",
            "impact": "degraded", "text": "routing test",
        })
        assert r.status_code in (200, 201)
        inc_id = r.json().get("id") or r.json().get("incident", {}).get("id")
        time.sleep(2)
        d = admin_client.get(f"{BASE_URL}/api/admin/deploy/alert-channels/deliveries").json()["deliveries"]
        # webhook should have a recent entry (203 => ok False but still recorded)
        assert "webhook" in d and d["webhook"][0]["status"] == 203
        # discord should NOT have any entry with status 201 recently for incident event
        discord_incident = [r for r in d.get("discord", []) if r.get("event", "").startswith("incident.")]
        assert not any(r["status"] == 201 for r in discord_incident), "discord fired despite maintenance mode"
        # whatsapp with outages should also NOT receive degraded
        whatsapp_incident = [r for r in d.get("whatsapp", []) if r.get("event", "").startswith("incident.")]
        assert not any(r["status"] == 202 for r in whatsapp_incident), "whatsapp fired despite outages mode on degraded"
        # cleanup
        if inc_id:
            admin_client.post(f"{BASE_URL}/api/admin/deploy/status-incidents/{inc_id}/update",
                              json={"resolve": True, "text": "TEST cleanup"})
