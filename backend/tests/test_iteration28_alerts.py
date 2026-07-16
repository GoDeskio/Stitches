"""Iteration 28: Automation failure alerts (backend)."""
import os
import time
import pytest
import requests

def _load_url():
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if not v:
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        v = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    assert v, "REACT_APP_BACKEND_URL missing"
    return v.rstrip("/")


BASE_URL = _load_url()

ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}
DEMO = {"email": "demo@stitches.app", "password": "Demo@123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def demo_token():
    return _login(DEMO)


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


# ---- config endpoints ----

def test_admin_get_alerts(admin_token):
    r = requests.get(f"{BASE_URL}/api/admin/automation-alerts", headers=_hdr(admin_token))
    assert r.status_code == 200
    d = r.json()
    for k in ("enabled", "threshold", "email", "webhook_url"):
        assert k in d
    assert isinstance(d["threshold"], int)


def test_non_admin_forbidden_get(demo_token):
    r = requests.get(f"{BASE_URL}/api/admin/automation-alerts", headers=_hdr(demo_token))
    assert r.status_code == 403


def test_non_admin_forbidden_put(demo_token):
    r = requests.put(f"{BASE_URL}/api/admin/automation-alerts",
                     json={"enabled": True, "threshold": 2}, headers=_hdr(demo_token))
    assert r.status_code == 403


def test_put_and_threshold_clamp(admin_token):
    # Clamp high
    r = requests.put(f"{BASE_URL}/api/admin/automation-alerts",
                     json={"enabled": True, "threshold": 999, "email": "", "webhook_url": ""},
                     headers=_hdr(admin_token))
    assert r.status_code == 200
    g = requests.get(f"{BASE_URL}/api/admin/automation-alerts", headers=_hdr(admin_token)).json()
    assert g["threshold"] == 20
    assert g["enabled"] is True
    # Clamp low (use -1: truthy, forces min clamp)
    requests.put(f"{BASE_URL}/api/admin/automation-alerts",
                 json={"enabled": True, "threshold": -1}, headers=_hdr(admin_token))
    g = requests.get(f"{BASE_URL}/api/admin/automation-alerts", headers=_hdr(admin_token)).json()
    assert g["threshold"] == 1


# ---- end-to-end ----

def test_end_to_end_alert_once_per_streak(admin_token, demo_token):
    # Configure alerts, threshold=2
    r = requests.put(f"{BASE_URL}/api/admin/automation-alerts",
                     json={"enabled": True, "threshold": 2, "email": "",
                           "webhook_url": "https://httpbin.org/post"},
                     headers=_hdr(admin_token))
    assert r.status_code == 200

    # Snapshot admin's existing automation notification IDs
    n = requests.get(f"{BASE_URL}/api/notifications", headers=_hdr(admin_token)).json()
    pre_ids = {x["notification_id"] for x in n["notifications"] if x.get("type") == "automation"}

    # Demo creates a failing N8N integration
    c = requests.post(f"{BASE_URL}/api/integrations", headers=_hdr(demo_token),
                      json={"type": "n8n", "name": "TEST_iter28_fail",
                            "auth_method": "url",
                            "config": {"webhook_url": "https://httpbin.org/status/500"}})
    assert c.status_code == 200, c.text
    integration_id = c.json()["integration_id"]

    try:
        # Run 1 – should fail (network 500 or 502), no alert yet (streak=1)
        r1 = requests.post(f"{BASE_URL}/api/integrations/{integration_id}/run",
                           headers=_hdr(demo_token), json={"payload": {}}, timeout=60)
        assert r1.status_code in (200, 502)
        if r1.status_code == 200:
            assert r1.json()["ok"] is False

        # Run 2 – should fail; alert fires (threshold=2)
        r2 = requests.post(f"{BASE_URL}/api/integrations/{integration_id}/run",
                           headers=_hdr(demo_token), json={"payload": {}}, timeout=60)
        assert r2.status_code in (200, 502)
        if r2.status_code == 200:
            assert r2.json()["ok"] is False

        time.sleep(1.5)  # allow webhook + notif creation

        n2 = requests.get(f"{BASE_URL}/api/notifications", headers=_hdr(admin_token)).json()
        auto = [x for x in n2["notifications"] if x.get("type") == "automation"
                and x["notification_id"] not in pre_ids]
        assert len(auto) == 1, f"expected exactly 1 new automation notification, got {len(auto)}: {auto}"
        assert "TEST_iter28_fail" in auto[0]["title"]

        # Run 3 – another failure; should NOT create a duplicate
        r3 = requests.post(f"{BASE_URL}/api/integrations/{integration_id}/run",
                           headers=_hdr(demo_token), json={"payload": {}}, timeout=60)
        assert r3.status_code in (200, 502)
        if r3.status_code == 200:
            assert r3.json()["ok"] is False
        time.sleep(1.5)

        n3 = requests.get(f"{BASE_URL}/api/notifications", headers=_hdr(admin_token)).json()
        auto3 = [x for x in n3["notifications"] if x.get("type") == "automation"
                 and x["notification_id"] not in pre_ids]
        assert len(auto3) == 1, f"duplicate alert fired on 3rd failure: got {len(auto3)}"

        # Cleanup notifications (call teardown even on failure)
        for a in auto3:
            requests.delete(f"{BASE_URL}/api/notifications/{a['notification_id']}",
                            headers=_hdr(admin_token))  # may 404, ignore
    finally:
        # Cleanup: delete integration + reset alert settings
        requests.delete(f"{BASE_URL}/api/integrations/{integration_id}", headers=_hdr(demo_token))
        # Delete created automation notifications from Mongo via API best-effort
        n_final = requests.get(f"{BASE_URL}/api/notifications", headers=_hdr(admin_token)).json()
        for x in n_final["notifications"]:
            if x.get("type") == "automation" and x["notification_id"] not in pre_ids:
                requests.delete(f"{BASE_URL}/api/notifications/{x['notification_id']}",
                                headers=_hdr(admin_token))
        # Reset alert settings
        requests.put(f"{BASE_URL}/api/admin/automation-alerts",
                     json={"enabled": False, "threshold": 3, "email": "", "webhook_url": ""},
                     headers=_hdr(admin_token))
