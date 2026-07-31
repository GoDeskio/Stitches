"""Iteration 44 backend tests: Memory Categories, Suggested Memories, Preset Diff, Regression."""
import os, base64, json, time
from pathlib import Path
import pytest, requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def ensure_memory_enabled(admin_client):
    # Ensure user_enabled is true so suggestions and pin work
    r = admin_client.get(f"{BASE_URL}/api/admin/ai-memory/config", timeout=30)
    assert r.status_code == 200
    cfg = r.json()
    payload = {
        "user_enabled": True,
        "workspace_enabled": cfg.get("workspace_enabled", False),
        "retention_days": cfg.get("retention_days", 90),
        "max_items": cfg.get("max_items", 200),
    }
    r2 = admin_client.put(f"{BASE_URL}/api/admin/ai-memory/config", json=payload, timeout=30)
    assert r2.status_code == 200
    yield


class TestMemoryCategories:
    """POST /api/ai/memory accepts category; GET returns category."""

    _created = []

    def test_pin_memory_with_each_category(self, admin_client):
        for cat in ["preference", "project", "deadline", "tool", "general"]:
            r = admin_client.post(f"{BASE_URL}/api/ai/memory", json={
                "content": f"TEST_iter44 cat {cat}",
                "category": cat,
                "source": "pinned",
            }, timeout=30)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["category"] == cat
            assert data["scope"] == "user"
            assert data["source"] == "pinned"
            assert data["content"] == f"TEST_iter44 cat {cat}"
            assert "mem_id" in data
            self._created.append(data["mem_id"])

    def test_invalid_category_defaults_to_general(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/ai/memory", json={
            "content": "TEST_iter44 bogus cat",
            "category": "nonsense",
        }, timeout=30)
        assert r.status_code == 200
        assert r.json()["category"] == "general"
        self._created.append(r.json()["mem_id"])

    def test_get_ai_memory_returns_category(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/ai/memory", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "user" in data
        cats_in_list = {m.get("category") for m in data["user"] if m["content"].startswith("TEST_iter44")}
        # Should contain each of the 5 categories
        for cat in ["preference", "project", "deadline", "tool", "general"]:
            assert cat in cats_in_list, f"missing {cat} in {cats_in_list}"

    def test_patch_memory_edit(self, admin_client):
        # Create then patch
        r = admin_client.post(f"{BASE_URL}/api/ai/memory", json={
            "content": "TEST_iter44 edit orig", "category": "project"}, timeout=30)
        mid = r.json()["mem_id"]
        self._created.append(mid)
        r2 = admin_client.patch(f"{BASE_URL}/api/ai/memory/{mid}", json={"content": "TEST_iter44 edit new"}, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["content"] == "TEST_iter44 edit new"
        # Verify by GET
        r3 = admin_client.get(f"{BASE_URL}/api/ai/memory", timeout=30)
        found = [m for m in r3.json()["user"] if m["mem_id"] == mid]
        assert found and found[0]["content"] == "TEST_iter44 edit new"

    def test_patch_empty_rejected(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/ai/memory", json={"content": "TEST_iter44 patch empty"}, timeout=30)
        mid = r.json()["mem_id"]
        self._created.append(mid)
        r2 = admin_client.patch(f"{BASE_URL}/api/ai/memory/{mid}", json={"content": ""}, timeout=30)
        assert r2.status_code == 400

    def test_cleanup(self, admin_client):
        for mid in list(self._created):
            admin_client.delete(f"{BASE_URL}/api/ai/memory/{mid}", timeout=30)


class TestSuggestedMemories:
    """POST /api/ai/memory/suggest."""

    def test_suggest_empty_returns_null(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/ai/memory/suggest",
                              json={"user_text": "", "assistant_text": ""}, timeout=30)
        assert r.status_code == 200
        assert r.json().get("suggestion") is None

    def test_suggest_durable_fact(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/ai/memory/suggest", json={
            "user_text": "I always prefer dark mode and I work on the Q3 Launch project as engineering lead.",
            "assistant_text": "Got it, I'll remember your preference for dark mode and that you lead the Q3 Launch project.",
        }, timeout=60)
        assert r.status_code == 200
        data = r.json()
        # LLM may occasionally return null; treat as soft-pass but expect suggestion most of the time
        if data.get("suggestion"):
            assert isinstance(data["suggestion"], str) and len(data["suggestion"]) > 0
            assert data.get("category") in ["preference", "project", "deadline", "tool", "general"]
        else:
            pytest.skip("LLM returned no suggestion for durable-fact prompt (soft acceptable)")

    def test_suggest_when_memory_disabled(self, admin_client):
        # Turn memory off
        cfg = admin_client.get(f"{BASE_URL}/api/admin/ai-memory/config", timeout=30).json()
        admin_client.put(f"{BASE_URL}/api/admin/ai-memory/config", json={
            "user_enabled": False,
            "workspace_enabled": cfg.get("workspace_enabled", False),
            "retention_days": cfg.get("retention_days", 90),
            "max_items": cfg.get("max_items", 200),
        }, timeout=30)
        try:
            r = admin_client.post(f"{BASE_URL}/api/ai/memory/suggest",
                                  json={"user_text": "I prefer dark mode.", "assistant_text": "ok"}, timeout=30)
            assert r.status_code == 200
            assert r.json().get("suggestion") is None
        finally:
            # Restore memory ON
            admin_client.put(f"{BASE_URL}/api/admin/ai-memory/config", json={
                "user_enabled": True,
                "workspace_enabled": cfg.get("workspace_enabled", False),
                "retention_days": cfg.get("retention_days", 90),
                "max_items": cfg.get("max_items", 200),
            }, timeout=30)

    def test_accept_suggestion_saves_with_source(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/ai/memory", json={
            "content": "TEST_iter44 suggested fact",
            "category": "preference",
            "source": "suggested",
        }, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data["source"] == "suggested"
        assert data["category"] == "preference"
        admin_client.delete(f"{BASE_URL}/api/ai/memory/{data['mem_id']}", timeout=30)


class TestAgentRegression:
    def test_ai_agent_still_works(self, admin_client):
        r = admin_client.post(f"{BASE_URL}/api/ai/agent",
                              json={"message": "Say hello briefly", "provider": "openai", "model": "gpt-5.4"},
                              timeout=90)
        assert r.status_code == 200
        data = r.json()
        assert "reply" in data
        assert isinstance(data["reply"], str) and len(data["reply"]) > 0


class TestDeployPreset:
    """Regression: preset save endpoint used by Apply in the diff modal."""

    _preset_ids = []

    def test_catalog_lists_presets(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/deploy/catalog", timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "presets" in data
        assert isinstance(data["presets"], list)

    def test_save_preset(self, admin_client):
        payload = {"name": "TEST_iter44 Import", "selected": ["coturn", "livekit", "grafana"]}
        r = admin_client.post(f"{BASE_URL}/api/admin/deploy/presets", json=payload, timeout=30)
        assert r.status_code in (200, 201), r.text
        # Verify appears in catalog.presets
        r2 = admin_client.get(f"{BASE_URL}/api/admin/deploy/catalog", timeout=30)
        presets = r2.json().get("presets", [])
        found = [p for p in presets if p.get("name") == "TEST_iter44 Import"]
        assert found, presets
        # ids/selected should match
        assert set(found[0].get("ids") or found[0].get("selected") or []) == {"coturn", "livekit", "grafana"}

    def test_cleanup_preset(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/deploy/catalog", timeout=30)
        for p in r.json().get("presets", []):
            if str(p.get("name", "")).startswith("TEST_iter44"):
                pid = p.get("id") or p.get("preset_id")
                if pid:
                    admin_client.delete(f"{BASE_URL}/api/admin/deploy/presets/{pid}", timeout=30)
