"""Iteration 43: Deployment Center + AI Memory + Bot callback health trend."""
import os
import re
import io
import json
import zipfile
import time
from pathlib import Path

import pytest
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": "admin@stitches.app", "password": "Admin@123"}, timeout=30)
    if r.status_code != 200:
        pytest.fail(f"admin login failed: {r.status_code} {r.text[:200]}")
    return r.json()["token"]


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ---------------- Deployment Center ----------------
class TestDeploymentCenter:
    def test_catalog(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/deploy/catalog", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert "catalog" in data
        assert len(data["catalog"]) == 15
        for c in data["catalog"]:
            assert {"id", "name", "category", "repo", "required", "provided", "description"}.issubset(c.keys())
        # required flags exist for coturn/livekit/traefik
        req_ids = {c["id"] for c in data["catalog"] if c["required"]}
        assert {"coturn", "livekit", "traefik"}.issubset(req_ids)
        # provided flag present for redundant services
        provided_ids = {c["id"] for c in data["catalog"] if c["provided"]}
        assert {"minio", "keycloak", "postgres", "synapse", "element-web"}.issubset(provided_ids)
        assert isinstance(data["selected"], list)

    def test_config_save(self, admin_headers):
        r = requests.put(f"{BASE_URL}/api/admin/deploy/config", headers=admin_headers, json={
            "domain": "example.com",
            "public_ip": "203.0.113.10",
            "selected": ["coturn", "livekit", "traefik", "prometheus", "grafana"],
            "github_token": "ghp_TEST_dummy_token_1234567890"
        }, timeout=30)
        assert r.status_code == 200
        assert r.json().get("ok") is True

        # verify persisted + has_github_token
        cat = requests.get(f"{BASE_URL}/api/admin/deploy/catalog", headers=admin_headers, timeout=30).json()
        assert cat["domain"] == "example.com"
        assert cat["public_ip"] == "203.0.113.10"
        assert cat["has_github_token"] is True

    def test_generate_bundle(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/deploy/generate", headers=admin_headers,
                          json={"regenerate": True}, timeout=60)
        assert r.status_code == 200
        data = r.json()
        assert "files" in data and "paste" in data
        names = {f["name"] for f in data["files"]}
        expected = {"clone-repos.sh", ".env", "coturn/turnserver.conf",
                    "livekit/livekit.yaml", "compose.yml", "firewall.sh",
                    "install.sh", "DEPLOY.md"}
        assert expected.issubset(names), f"missing files: {expected - names}"
        # every file has content
        for f in data["files"]:
            assert isinstance(f.get("content"), str) and len(f["content"]) > 0
        paste = data["paste"]
        for k in ("turn_urls", "turn_username", "turn_credential",
                  "livekit_url", "livekit_api_key", "livekit_api_secret"):
            assert paste.get(k), f"paste missing {k}"
        assert paste["turn_urls"] == "turn:example.com:3478"
        assert paste["livekit_url"] == "wss://livekit.example.com"
        # capture for regeneration test
        pytest.first_paste = paste

    def test_regenerate_produces_fresh_secrets(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/deploy/generate", headers=admin_headers,
                          json={"regenerate": True}, timeout=60)
        assert r.status_code == 200
        new_paste = r.json()["paste"]
        old = getattr(pytest, "first_paste", {})
        assert new_paste["turn_credential"] != old.get("turn_credential")
        assert new_paste["livekit_api_secret"] != old.get("livekit_api_secret")

    def test_download_zip(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/deploy/download", headers=admin_headers, timeout=60)
        assert r.status_code == 200
        assert r.headers.get("content-type", "").startswith("application/zip")
        buf = io.BytesIO(r.content)
        with zipfile.ZipFile(buf) as z:
            names = z.namelist()
            assert any("install.sh" in n for n in names)
            assert any("compose.yml" in n for n in names)
            assert any("clone-repos.sh" in n for n in names)
            assert any("DEPLOY.md" in n for n in names)

    def test_apply_calls_wires_meetings(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/deploy/apply-calls", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        assert data.get("ok") is True
        assert "turn:" in data.get("turn_urls", "")

        rtc = requests.get(f"{BASE_URL}/api/admin/rtc-config", headers=admin_headers, timeout=30).json()
        assert rtc.get("urls")
        assert rtc.get("has_credential") is True

        sfu = requests.get(f"{BASE_URL}/api/admin/sfu-config", headers=admin_headers, timeout=30).json()
        assert "livekit" in (sfu.get("url") or "").lower()
        assert sfu.get("api_key")

    def test_non_admin_blocked(self):
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": "demo@stitches.app", "password": "Demo@123"}, timeout=30)
        if r.status_code != 200:
            pytest.skip("demo user not seeded")
        tok = r.json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        r2 = requests.get(f"{BASE_URL}/api/admin/deploy/catalog", headers=h, timeout=30)
        assert r2.status_code in (401, 403)


# ---------------- AI Memory ----------------
class TestAiMemory:
    added_mem_ids = []

    def test_get_config(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/ai-memory/config", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        for k in ("user_enabled", "workspace_enabled", "retention_days", "max_items", "counts"):
            assert k in data
        assert isinstance(data["counts"], dict)
        assert "user" in data["counts"] and "workspace" in data["counts"]

    def test_put_config(self, admin_headers):
        r = requests.put(f"{BASE_URL}/api/admin/ai-memory/config", headers=admin_headers,
                         json={"user_enabled": True, "workspace_enabled": True,
                               "retention_days": 60, "max_items": 150}, timeout=30)
        assert r.status_code == 200
        cfg = requests.get(f"{BASE_URL}/api/admin/ai-memory/config", headers=admin_headers, timeout=30).json()
        assert cfg["user_enabled"] is True
        assert cfg["workspace_enabled"] is True
        assert cfg["retention_days"] == 60
        assert cfg["max_items"] == 150

    def test_add_memory_user_scope(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/ai-memory", headers=admin_headers,
                          json={"scope": "user", "content": "TEST_ user prefers dark mode"}, timeout=30)
        assert r.status_code == 200
        mem = r.json()
        assert mem["scope"] == "user"
        assert mem["content"] == "TEST_ user prefers dark mode"
        assert mem.get("mem_id", "").startswith("mem_")
        TestAiMemory.added_mem_ids.append(mem["mem_id"])

    def test_add_memory_workspace_scope(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/ai-memory", headers=admin_headers,
                          json={"scope": "workspace", "content": "TEST_ team ships Thursdays"}, timeout=30)
        assert r.status_code == 200
        mem = r.json()
        assert mem["scope"] == "workspace"
        assert mem["owner_id"] == "__workspace__"
        TestAiMemory.added_mem_ids.append(mem["mem_id"])

    def test_list_filter_by_scope(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/ai-memory/list?scope=user", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert isinstance(items, list)
        assert all(m["scope"] == "user" for m in items)

    def test_list_search_q(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/ai-memory/list?q=TEST_", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        items = r.json()
        assert any("TEST_" in (m["content"] or "") for m in items)

    def test_add_empty_content_rejected(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/admin/ai-memory", headers=admin_headers,
                          json={"scope": "user", "content": "   "}, timeout=30)
        assert r.status_code == 400

    def test_delete_one(self, admin_headers):
        if not TestAiMemory.added_mem_ids:
            pytest.skip("nothing to delete")
        mid = TestAiMemory.added_mem_ids.pop(0)
        r = requests.delete(f"{BASE_URL}/api/admin/ai-memory/{mid}", headers=admin_headers, timeout=30)
        assert r.status_code == 200

    def test_clear_scope(self, admin_headers):
        # add throwaway
        requests.post(f"{BASE_URL}/api/admin/ai-memory", headers=admin_headers,
                      json={"scope": "workspace", "content": "TEST_ clearme"}, timeout=30)
        r = requests.delete(f"{BASE_URL}/api/admin/ai-memory?scope=workspace",
                            headers=admin_headers, timeout=30)
        assert r.status_code == 200
        assert r.json().get("ok") is True
        remaining = requests.get(f"{BASE_URL}/api/admin/ai-memory/list?scope=workspace",
                                 headers=admin_headers, timeout=30).json()
        assert remaining == []
        TestAiMemory.added_mem_ids = [m for m in TestAiMemory.added_mem_ids]  # nothing needed

    def test_ai_chat_streams_with_memory(self, admin_headers):
        # add a memory then chat
        requests.post(f"{BASE_URL}/api/admin/ai-memory", headers=admin_headers,
                      json={"scope": "user", "content": "TEST_ admin loves brevity"}, timeout=30)
        r = requests.post(f"{BASE_URL}/api/ai/chat", headers=admin_headers,
                          json={"message": "Say hi in five words", "provider": "openai", "model": "gpt-5.4-mini"},
                          stream=True, timeout=60)
        assert r.status_code == 200
        assert "text/event-stream" in r.headers.get("content-type", "")
        chunks = []
        start = time.time()
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                chunks.append(line[6:])
                if '"done": true' in line or time.time() - start > 30:
                    break
        assert any("conversation_id" in c for c in chunks)

    @classmethod
    def teardown_class(cls):
        # cleanup
        r = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"email": "admin@stitches.app", "password": "Admin@123"}, timeout=30)
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        # nuke all TEST_ memories
        items = requests.get(f"{BASE_URL}/api/admin/ai-memory/list?q=TEST_", headers=h, timeout=30).json()
        for m in items:
            requests.delete(f"{BASE_URL}/api/admin/ai-memory/{m['mem_id']}", headers=h, timeout=30)


# ---------------- Bot callback health trend ----------------
class TestBotCallbackTrend:
    def test_list_bots_safe_with_empty(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/bots", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        data = r.json()
        bots = data.get("bots", data) if isinstance(data, dict) else data
        assert isinstance(bots, list)
        for b in bots:
            ch = b.get("callback_health")
            if ch is not None:
                # if present, must include trend as list (may be empty)
                assert "trend" in ch
                assert isinstance(ch["trend"], list)
                # each entry should be numeric
                for v in ch["trend"]:
                    assert isinstance(v, (int, float))
