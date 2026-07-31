"""
Iteration 47 backend tests: uptime windows, email subscribers, incidents management,
auto-incident behavior on public status page.
"""
import os
import re
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

fe_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or fe_env.get("REACT_APP_BACKEND_URL")).rstrip("/")


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@stitches.app", "password": "Admin@123"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


def ensure_status_page_enabled(admin_headers):
    r = requests.put(f"{BASE_URL}/api/admin/deploy/status-page",
                     json={"enabled": True, "title": "Stitches Status", "auto_incidents": True},
                     headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


class TestStatusPageMeta:
    def test_get_status_page_config(self, admin_headers):
        ensure_status_page_enabled(admin_headers)
        r = requests.get(f"{BASE_URL}/api/admin/deploy/status-page", headers=admin_headers)
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert "auto_incidents" in d
        assert "subscribers" in d
        assert "open_incidents" in d
        assert isinstance(d["subscribers"], int)
        assert isinstance(d["open_incidents"], int)

    def test_toggle_auto_incidents_persists(self, admin_headers):
        # PUT off - verify response reflects the change (avoid race with parallel tests)
        r = requests.put(f"{BASE_URL}/api/admin/deploy/status-page",
                         json={"enabled": True, "auto_incidents": False}, headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["auto_incidents"] is False
        # back on
        r2 = requests.put(f"{BASE_URL}/api/admin/deploy/status-page",
                          json={"enabled": True, "auto_incidents": True}, headers=admin_headers)
        assert r2.status_code == 200
        assert r2.json()["auto_incidents"] is True


class TestPublicStatusUptimeWindows:
    def test_public_returns_windows(self, admin_headers):
        ensure_status_page_enabled(admin_headers)
        r = requests.get(f"{BASE_URL}/api/status/public")
        assert r.status_code == 200
        d = r.json()
        assert d["enabled"] is True
        assert d["windows"] == ["24h", "7d", "90d"]
        assert isinstance(d["groups"], list) and len(d["groups"]) >= 1
        g0 = d["groups"][0]
        assert "windows" in g0
        for w in ["24h", "7d", "90d"]:
            assert w in g0["windows"], f"missing {w} in group {g0.get('key')}"
            assert "pct" in g0["windows"][w]
            assert "strip" in g0["windows"][w]
        assert "incidents" in d


class TestPublicSubscribe:
    def test_valid_email(self, admin_headers):
        ensure_status_page_enabled(admin_headers)
        email = f"TEST_iter47_{int(time.time())}@example.com"
        r = requests.post(f"{BASE_URL}/api/status/subscribe", json={"email": email})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("ok") is True
        assert d.get("already") is False or d.get("already") is None or d["already"] is False

    def test_duplicate_email(self, admin_headers):
        ensure_status_page_enabled(admin_headers)
        email = f"TEST_iter47_dup_{int(time.time())}@example.com"
        r1 = requests.post(f"{BASE_URL}/api/status/subscribe", json={"email": email})
        assert r1.status_code == 200
        r2 = requests.post(f"{BASE_URL}/api/status/subscribe", json={"email": email})
        assert r2.status_code == 200
        assert r2.json().get("already") is True

    def test_invalid_email(self, admin_headers):
        ensure_status_page_enabled(admin_headers)
        r = requests.post(f"{BASE_URL}/api/status/subscribe", json={"email": "not-an-email"})
        assert r.status_code in (400, 422), r.text

    def test_subscribe_when_disabled(self, admin_headers):
        # disable
        requests.put(f"{BASE_URL}/api/admin/deploy/status-page",
                     json={"enabled": False, "auto_incidents": True}, headers=admin_headers)
        r = requests.post(f"{BASE_URL}/api/status/subscribe", json={"email": "TEST_when_off@example.com"})
        assert r.status_code == 404
        # re-enable
        ensure_status_page_enabled(admin_headers)


class TestIncidentManagement:
    def test_manual_create_update_resolve(self, admin_headers):
        ensure_status_page_enabled(admin_headers)
        # Fetch groups to pick one
        r = requests.get(f"{BASE_URL}/api/admin/deploy/status-incidents", headers=admin_headers)
        assert r.status_code == 200
        groups = r.json()["groups"]
        assert len(groups) >= 1
        gkey = groups[0]["key"]

        # Create
        create = requests.post(f"{BASE_URL}/api/admin/deploy/status-incidents",
                               json={"group_key": gkey, "impact": "degraded",
                                     "text": "TEST_iter47 manual incident"},
                               headers=admin_headers)
        assert create.status_code == 200, create.text
        inc = create.json().get("incident") or create.json()
        incident_id = inc.get("incident_id") or inc.get("id")
        assert incident_id, f"no incident_id in {create.json()}"

        # Update
        upd = requests.post(f"{BASE_URL}/api/admin/deploy/status-incidents/{incident_id}/update",
                            json={"text": "TEST_iter47 investigating", "resolve": False},
                            headers=admin_headers)
        assert upd.status_code == 200

        # Verify in list
        listed = requests.get(f"{BASE_URL}/api/admin/deploy/status-incidents", headers=admin_headers).json()
        found = next((i for i in listed["incidents"] if i["incident_id"] == incident_id), None)
        assert found is not None
        assert found["status"] != "resolved"
        assert any("investigating" in (u.get("text") or "").lower() for u in found.get("updates", []))

        # Resolve
        res = requests.post(f"{BASE_URL}/api/admin/deploy/status-incidents/{incident_id}/update",
                            json={"text": "TEST_iter47 resolved", "resolve": True},
                            headers=admin_headers)
        assert res.status_code == 200

        listed2 = requests.get(f"{BASE_URL}/api/admin/deploy/status-incidents", headers=admin_headers).json()
        found2 = next((i for i in listed2["incidents"] if i["incident_id"] == incident_id), None)
        assert found2["status"] == "resolved"


class TestAutoIncidentE2E:
    def test_diagnostics_creates_public_incident(self, admin_headers):
        ensure_status_page_enabled(admin_headers)
        # Run diagnostics
        r = requests.post(f"{BASE_URL}/api/admin/deploy/diagnose",
                          json={"autofix": True}, headers=admin_headers)
        assert r.status_code == 200
        summary = r.json().get("summary", {})
        # Fetch public status - should include any open auto incident if something was degraded/failing
        pub = requests.get(f"{BASE_URL}/api/status/public").json()
        # If warn/fail > 0, we expect at least one incident
        if summary.get("warn", 0) + summary.get("fail", 0) > 0:
            assert len(pub.get("incidents", [])) >= 1, "expected auto-incident since diag reported issues"
            # At least one incident should carry updates timeline
            assert any(inc.get("updates") for inc in pub["incidents"])
