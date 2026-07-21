"""Backend tests for the super-admin Storage & DB tab endpoints (iteration 37)."""
import os
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "admin@stitches.app"
ADMIN_PW = "Admin@123"
DEMO_EMAIL = "demo@stitches.app"
DEMO_PW = "Demo@123"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers():
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PW)}"}


@pytest.fixture(scope="module")
def demo_headers():
    return {"Authorization": f"Bearer {_login(DEMO_EMAIL, DEMO_PW)}"}


# ---------------- Access control ----------------
class TestAccessControl:
    def test_superadmin_whoami_true(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/superadmin/whoami", headers=admin_headers, timeout=10)
        assert r.status_code == 200
        assert r.json().get("is_super_admin") is True

    def test_non_admin_forbidden(self, demo_headers):
        # demo user is not admin at all -> require_admin blocks
        r = requests.get(f"{BASE_URL}/api/admin/db/overview", headers=demo_headers, timeout=10)
        assert r.status_code in (401, 403)


# ---------------- Ops webhook ----------------
class TestOpsWebhook:
    def test_save_and_get(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/ops-webhook",
                          json={"url": "https://hooks.slack.com/services/FAKE/QA/URL", "enabled": True, "platform": "slack"},
                          headers=admin_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["has_url"] is True
        assert r.json()["enabled"] is True

        r2 = requests.get(f"{BASE_URL}/api/admin/ops-webhook", headers=admin_headers, timeout=10)
        assert r2.status_code == 200
        assert r2.json()["has_url"] is True

    def test_send_test_returns_ok_false_for_fake(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/ops-webhook/test", json={}, headers=admin_headers, timeout=20)
        assert r.status_code == 200
        j = r.json()
        # Expected: send path works but the fake URL returns non-2xx -> ok=false with a detail string
        assert "ok" in j and "detail" in j
        assert j["ok"] is False
        assert isinstance(j["detail"], str) and len(j["detail"]) > 0

    def test_clear_webhook(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/ops-webhook",
                          json={"url": "", "enabled": False}, headers=admin_headers, timeout=10)
        assert r.status_code == 200
        assert r.json()["has_url"] is False
        assert r.json()["enabled"] is False


# ---------------- DB overview + browse ----------------
class TestDbOverview:
    def test_overview_has_users_protected(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/db/overview", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert "collections" in j
        users_row = next((c for c in j["collections"] if c["name"] == "users"), None)
        assert users_row is not None
        assert users_row.get("protected") is True

    def test_browse_qa_throwaway_has_3_docs(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/db/collections/qa_throwaway/docs", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["total"] == 3
        assert len(j["docs"]) == 3


# ---------------- Backups ----------------
class TestBackups:
    def test_backup_now(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/db/backup", headers=admin_headers, timeout=90)
        assert r.status_code == 200, r.text
        j = r.json()
        assert j.get("ok") is True and j.get("stamp")
        # verify it appears in list
        rl = requests.get(f"{BASE_URL}/api/admin/db/backups", headers=admin_headers, timeout=10)
        assert rl.status_code == 200
        stamps = [b["stamp"] for b in rl.json().get("backups", [])]
        assert j["stamp"] in stamps


# ---------------- Storage overview + orphan delete ----------------
class TestStorage:
    def test_overview_has_orphan(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/storage/overview", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        j = r.json()
        orphans = [u for u in j.get("by_user", []) if u.get("orphan")]
        assert any(o["owner_id"] == "qa-fake-user-zzz" for o in orphans), f"expected orphan owner not found. by_user={j.get('by_user')}"
        # remember count for post-delete verification
        TestStorage._before = j["total_count"]

    def test_delete_orphans_removes_seed(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/storage/delete-orphans", headers=admin_headers, timeout=20)
        assert r.status_code == 200
        assert r.json().get("deleted", 0) >= 1

        r2 = requests.get(f"{BASE_URL}/api/admin/storage/overview", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        after = r2.json()["total_count"]
        assert after == TestStorage._before - 1
        # orphan owner row should be gone
        assert not any(u.get("owner_id") == "qa-fake-user-zzz" for u in r2.json().get("by_user", []))


# ---------------- Purge throwaway collection ----------------
class TestPurgeThrowaway:
    def test_purge_qa_throwaway(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/db/collections/qa_throwaway/purge", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        j = r.json()
        assert j["deleted"] == 3

        # After purge, either the collection no longer appears OR shows count 0
        r2 = requests.get(f"{BASE_URL}/api/admin/db/overview", headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        row = next((c for c in r2.json()["collections"] if c["name"] == "qa_throwaway"), None)
        assert row is None or row["count"] == 0


# ---------------- Audit trail ----------------
class TestAudit:
    def test_audit_trail_lists_recent(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/audit/destructive", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        entries = r.json().get("entries", [])
        actions = {e["action"] for e in entries}
        # We just performed these:
        assert "db_backup" in actions
        assert "db_purge" in actions
        assert "storage_delete_orphans" in actions
        # actor info present
        for e in entries[:5]:
            assert "actor_name" in e
            assert "created_at" in e
