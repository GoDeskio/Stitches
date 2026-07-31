"""Iter45 tests: Undo Forget, Memory Export, Deployment Diagnostics."""
import os
import json
import csv
import io
import uuid
import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN_EMAIL = "admin@stitches.app"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.fail(f"admin login failed: {r.status_code} {r.text[:300]}")
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def ensure_memory_enabled(admin_headers):
    # Ensure user_enabled=true before memory tests
    r = requests.put(f"{BASE_URL}/api/admin/ai-memory/config",
                     headers=admin_headers,
                     json={"user_enabled": True, "workspace_enabled": True, "retention_days": 90, "max_items": 200})
    assert r.status_code == 200, r.text
    yield


# ========== Memory Undo (bulk-delete + restore) ==========
class TestMemoryUndoForget:
    created_ids = []

    def test_seed_memories(self, admin_headers):
        for i, cat in enumerate(["preference", "project", "deadline"]):
            r = requests.post(f"{BASE_URL}/api/ai/memory", headers=admin_headers,
                              json={"content": f"TEST_iter45 undo memory {i} {uuid.uuid4().hex[:6]}",
                                    "category": cat, "source": "pinned"})
            assert r.status_code == 200, r.text
            data = r.json()
            assert data.get("mem_id")
            assert data.get("category") == cat
            self.__class__.created_ids.append(data["mem_id"])
        assert len(self.__class__.created_ids) == 3

    def test_bulk_delete_and_restore(self, admin_headers):
        ids = self.__class__.created_ids

        # Capture memory docs before delete (for restore)
        r_get = requests.get(f"{BASE_URL}/api/ai/memory", headers=admin_headers)
        assert r_get.status_code == 200
        items = r_get.json().get("user", [])
        captured = [m for m in items if m.get("mem_id") in ids]
        assert len(captured) == 3, f"expected 3 seeded memories, got {len(captured)}"

        # Bulk-delete
        r_del = requests.post(f"{BASE_URL}/api/ai/memory/bulk-delete", headers=admin_headers, json={"ids": ids})
        assert r_del.status_code == 200, r_del.text
        assert r_del.json().get("deleted") == 3

        # Verify gone
        r_get2 = requests.get(f"{BASE_URL}/api/ai/memory", headers=admin_headers)
        items2 = r_get2.json().get("user", [])
        remaining = [m for m in items2 if m.get("mem_id") in ids]
        assert remaining == []

        # Restore
        r_rest = requests.post(f"{BASE_URL}/api/ai/memory/restore", headers=admin_headers,
                               json={"memories": captured})
        assert r_rest.status_code == 200, r_rest.text
        assert r_rest.json().get("restored") == 3

        # Verify restored with same mem_ids & category
        r_get3 = requests.get(f"{BASE_URL}/api/ai/memory", headers=admin_headers)
        items3 = r_get3.json().get("user", [])
        by_id = {m["mem_id"]: m for m in items3 if m.get("mem_id") in ids}
        assert len(by_id) == 3
        for m in captured:
            assert by_id[m["mem_id"]]["content"] == m["content"]
            assert by_id[m["mem_id"]]["category"] == m["category"]

    def test_restore_idempotent(self, admin_headers):
        # Restore same set again → should not duplicate (restored == 0)
        r_get = requests.get(f"{BASE_URL}/api/ai/memory", headers=admin_headers)
        items = r_get.json().get("user", [])
        captured = [m for m in items if m.get("mem_id") in self.__class__.created_ids]
        r_rest = requests.post(f"{BASE_URL}/api/ai/memory/restore", headers=admin_headers,
                               json={"memories": captured})
        assert r_rest.status_code == 200
        assert r_rest.json().get("restored") == 0

    def test_bulk_delete_empty_returns_400(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/ai/memory/bulk-delete", headers=admin_headers, json={"ids": []})
        assert r.status_code == 400

    def test_cleanup(self, admin_headers):
        if self.__class__.created_ids:
            requests.post(f"{BASE_URL}/api/ai/memory/bulk-delete", headers=admin_headers,
                          json={"ids": self.__class__.created_ids})


# ========== Memory Export ==========
class TestMemoryExport:
    seeded_ids = []

    def test_seed(self, admin_headers):
        for cat in ["preference", "project"]:
            r = requests.post(f"{BASE_URL}/api/ai/memory", headers=admin_headers,
                              json={"content": f"TEST_iter45 export {cat} {uuid.uuid4().hex[:6]}",
                                    "category": cat, "source": "pinned"})
            assert r.status_code == 200
            self.__class__.seeded_ids.append(r.json()["mem_id"])

    def test_export_json(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/ai/memory/export?format=json", headers=admin_headers)
        assert r.status_code == 200
        assert "application/json" in r.headers.get("Content-Type", "")
        cd = r.headers.get("Content-Disposition", "")
        assert "attachment" in cd and ".json" in cd
        data = json.loads(r.text)
        assert isinstance(data, list)
        # our seeded items must be present
        mems = {m.get("mem_id") for m in data}
        for sid in self.__class__.seeded_ids:
            assert sid in mems
        # sample record shape
        sample = next(m for m in data if m.get("mem_id") == self.__class__.seeded_ids[0])
        assert "content" in sample and "category" in sample and "created_at" in sample
        assert "_id" not in sample  # objectId excluded

    def test_export_csv(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/ai/memory/export?format=csv", headers=admin_headers)
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("Content-Type", "")
        cd = r.headers.get("Content-Disposition", "")
        assert "attachment" in cd and ".csv" in cd
        reader = csv.reader(io.StringIO(r.text))
        rows = list(reader)
        assert rows[0] == ["category", "content", "source", "created_at", "edited_at"]
        # find at least one of our seeded contents in rows
        contents = [row[1] for row in rows[1:]]
        assert any("TEST_iter45 export" in c for c in contents)

    def test_cleanup(self, admin_headers):
        if self.__class__.seeded_ids:
            requests.post(f"{BASE_URL}/api/ai/memory/bulk-delete", headers=admin_headers,
                          json={"ids": self.__class__.seeded_ids})


# ========== Diagnostics ==========
class TestDiagnostics:
    def test_diagnose_requires_admin(self):
        r = requests.post(f"{BASE_URL}/api/admin/deploy/diagnose", json={"autofix": True})
        assert r.status_code in (401, 403)

    def test_diagnose_full_report(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/deploy/diagnose", headers=admin_headers, json={"autofix": True})
        assert r.status_code == 200, r.text
        report = r.json()
        # top-level shape
        assert "summary" in report and "checks" in report and "auto_fixed" in report
        s = report["summary"]
        assert set(["ok", "warn", "fail"]).issubset(s.keys())
        # every check has required fields
        ids = set()
        for c in report["checks"]:
            for k in ("id", "label", "status", "detail", "needs_admin", "fix_hint", "autofixed"):
                assert k in c, f"missing {k} in check {c}"
            assert c["status"] in ("ok", "warn", "fail")
            ids.add(c["id"])
        # Expected checks per spec (mongo, llm, email, turn, livekit, deploy secrets/target, ai memory, admin, bots, indexes)
        for expected in ["mongo", "llm", "email", "turn", "livekit", "deploysecrets", "deploytarget", "aimemory", "admin", "bots", "indexes"]:
            assert expected in ids, f"missing check id: {expected} (got {ids})"
        # mongo, llm, admin should be ok in this env
        by_id = {c["id"]: c for c in report["checks"]}
        assert by_id["mongo"]["status"] == "ok"
        assert by_id["admin"]["status"] == "ok"
        # with autofix, indexes should be ok
        assert by_id["indexes"]["status"] == "ok"

    def test_diagnose_download_markdown(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/deploy/diagnose/download", headers=admin_headers)
        assert r.status_code == 200
        assert "text/markdown" in r.headers.get("Content-Type", "")
        cd = r.headers.get("Content-Disposition", "")
        assert "attachment" in cd and ".md" in cd
        body = r.text
        assert "# Stitches Diagnostics Report" in body
        assert "## Checks" in body
        assert "Database connectivity" in body


# ========== Regression: existing memory flows still work ==========
class TestRegression:
    def test_pin_edit_recategorize_bulk_move(self, admin_headers):
        # Pin
        r = requests.post(f"{BASE_URL}/api/ai/memory", headers=admin_headers,
                          json={"content": "TEST_iter45 regression pin", "category": "general"})
        assert r.status_code == 200
        mid = r.json()["mem_id"]
        try:
            # Edit
            r_e = requests.patch(f"{BASE_URL}/api/ai/memory/{mid}", headers=admin_headers,
                                 json={"content": "TEST_iter45 regression pin edited"})
            assert r_e.status_code == 200
            # Bulk recategorize
            r_cat = requests.post(f"{BASE_URL}/api/ai/memory/bulk-category", headers=admin_headers,
                                  json={"ids": [mid], "category": "project"})
            assert r_cat.status_code == 200
            assert r_cat.json().get("updated") == 1
            assert r_cat.json().get("category") == "project"
        finally:
            requests.post(f"{BASE_URL}/api/ai/memory/bulk-delete", headers=admin_headers, json={"ids": [mid]})

    def test_deploy_catalog_still_works(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/deploy/catalog", headers=admin_headers)
        assert r.status_code == 200
        j = r.json()
        assert "items" in j or "services" in j or "presets" in j
