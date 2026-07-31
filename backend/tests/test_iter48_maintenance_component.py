"""Iteration 48: Scheduled Maintenance + Component History endpoints."""
import os
from datetime import datetime, timezone, timedelta

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
ADMIN_EMAIL = "admin@stitches.app"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def admin_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:300]}"
    token = r.json().get("token")
    assert token, "no token"
    s.headers.update({"Authorization": f"Bearer {token}"})
    return s


@pytest.fixture(scope="module", autouse=True)
def ensure_status_enabled(admin_client):
    admin_client.put(f"{BASE_URL}/api/admin/deploy/status-page", json={"enabled": True})
    yield


class TestMaintenanceCRUD:
    created_ids = []

    def test_list_maintenance(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/deploy/maintenance")
        assert r.status_code == 200
        d = r.json()
        assert "maintenance" in d and "groups" in d
        keys = {g["key"] for g in d["groups"]}
        assert {"platform", "ai", "calls", "email"} <= keys

    def test_create_maintenance_valid(self, admin_client):
        start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=2, hours=2)).isoformat()
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/maintenance", json={
            "title": "TEST_iter48 upgrade",
            "message": "TEST maintenance msg",
            "group_keys": ["email"],
            "starts_at": start,
            "ends_at": end,
            "notify_lead_min": 30,
        })
        assert r.status_code == 200, r.text
        mid = r.json()["maint_id"]
        assert mid.startswith("mnt_")
        TestMaintenanceCRUD.created_ids.append(mid)

        # Verify it appears in list
        r2 = admin_client.get(f"{BASE_URL}/api/admin/deploy/maintenance")
        items = r2.json()["maintenance"]
        m = next((x for x in items if x["maint_id"] == mid), None)
        assert m is not None
        assert m["title"] == "TEST_iter48 upgrade"
        assert m["state"] == "scheduled"
        assert "email" in m["group_keys"]

    def test_create_maintenance_bad_times(self, admin_client):
        start = (datetime.now(timezone.utc) + timedelta(days=1, hours=2)).isoformat()
        end = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/maintenance", json={
            "title": "TEST_iter48 bad", "message": "x", "group_keys": [],
            "starts_at": start, "ends_at": end, "notify_lead_min": 60,
        })
        assert r.status_code == 400
        assert "after" in r.json().get("detail", "").lower()

    def test_create_maintenance_missing_times(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/maintenance", json={"title": "x"})
        assert r.status_code == 400

    def test_public_maintenance_visible(self, admin_client):
        r = requests.get(f"{BASE_URL}/api/status/public")
        assert r.status_code == 200
        d = r.json()
        assert d.get("enabled") is True
        assert "maintenance" in d
        found = [m for m in d["maintenance"] if m["title"] == "TEST_iter48 upgrade"]
        assert found, f"scheduled maintenance not on public page: {d['maintenance']}"
        m = found[0]
        assert m["state"] in ("scheduled", "in_progress")
        assert "Email delivery" in m.get("components", [])

    def test_delete_maintenance(self, admin_client):
        for mid in list(TestMaintenanceCRUD.created_ids):
            r = admin_client.delete(f"{BASE_URL}/api/admin/deploy/maintenance/{mid}")
            assert r.status_code == 200
        # Verify removed
        r = admin_client.get(f"{BASE_URL}/api/admin/deploy/maintenance")
        remaining = {m["maint_id"] for m in r.json()["maintenance"]}
        for mid in TestMaintenanceCRUD.created_ids:
            assert mid not in remaining
        TestMaintenanceCRUD.created_ids.clear()


class TestComponentHistory:
    def test_valid_component(self):
        for key in ["platform", "ai", "calls", "email"]:
            r = requests.get(f"{BASE_URL}/api/status/public/component/{key}")
            assert r.status_code == 200, f"{key}: {r.status_code} {r.text[:200]}"
            d = r.json()
            assert d.get("enabled") is True
            assert d["key"] == key
            assert d["label"]
            assert d["status"] in ("ok", "warn", "fail")
            assert set(d["windows"].keys()) == {"24h", "7d", "90d"}
            for w in ("24h", "7d", "90d"):
                assert 0 <= d["windows"][w]["pct"] <= 100
            assert isinstance(d["daily"], list)
            assert isinstance(d["incidents"], list)

    def test_invalid_component_404(self):
        r = requests.get(f"{BASE_URL}/api/status/public/component/does-not-exist")
        assert r.status_code == 404
