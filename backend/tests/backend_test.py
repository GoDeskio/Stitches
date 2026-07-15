"""Backend test suite for Stitches app."""
import os
import io
import uuid
import time
import json
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # fallback from frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@stitches.app"
ADMIN_PASSWORD = "Admin@123"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def user_token():
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test@1234", "name": "Test User"})
    assert r.status_code == 200, r.text
    return r.json()["token"], email


def H(token):
    return {"Authorization": f"Bearer {token}"}


# --- Auth ---
class TestAuth:
    def test_admin_login(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 20

    def test_me_admin(self, admin_token):
        r = requests.get(f"{API}/auth/me", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["email"] == ADMIN_EMAIL
        assert r.json()["role"] == "admin"

    def test_register_and_login(self):
        email = f"test_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Test@1234", "name": "Test"})
        assert r.status_code == 200
        assert "token" in r.json()
        # login
        r2 = requests.post(f"{API}/auth/login", json={"email": email, "password": "Test@1234"})
        assert r2.status_code == 200

    def test_invalid_login(self):
        r = requests.post(f"{API}/auth/login", json={"email": "nope@x.com", "password": "bad"})
        assert r.status_code == 401


# --- Dashboard ---
class TestDashboard:
    def test_stats(self, admin_token):
        r = requests.get(f"{API}/dashboard/stats", headers=H(admin_token))
        assert r.status_code == 200
        d = r.json()
        for k in ["workspaces", "projects", "assets", "integrations", "messages", "recent_projects"]:
            assert k in d


# --- Workspaces / Channels / Messages ---
class TestMessaging:
    def test_workspace_channels_messages(self, user_token):
        token, _ = user_token
        r = requests.post(f"{API}/workspaces", json={"name": "TEST_ws"}, headers=H(token))
        assert r.status_code == 200
        ws_id = r.json()["workspace_id"]

        r = requests.get(f"{API}/workspaces/{ws_id}/channels", headers=H(token))
        assert r.status_code == 200
        channels = r.json()
        names = [c["name"] for c in channels]
        assert "general" in names and "random" in names

        # create new channel
        r = requests.post(f"{API}/channels", json={"workspace_id": ws_id, "name": "TEST_ch"}, headers=H(token))
        assert r.status_code == 200
        ch_id = r.json()["channel_id"]

        # send message
        r = requests.post(f"{API}/messages", json={"channel_id": ch_id, "text": "hello"}, headers=H(token))
        assert r.status_code == 200
        assert r.json()["text"] == "hello"

        # fetch
        r = requests.get(f"{API}/channels/{ch_id}/messages", headers=H(token))
        assert r.status_code == 200 and len(r.json()) >= 1


# --- Projects ---
class TestProjects:
    def test_project_crud(self, user_token):
        token, _ = user_token
        r = requests.post(f"{API}/projects", json={"name": "TEST_proj", "status": "active"}, headers=H(token))
        assert r.status_code == 200
        pid = r.json()["project_id"]

        r = requests.get(f"{API}/projects", headers=H(token))
        assert r.status_code == 200
        assert any(p["project_id"] == pid for p in r.json())

        r = requests.put(f"{API}/projects/{pid}", json={"status": "paused"}, headers=H(token))
        assert r.status_code == 200
        assert r.json()["status"] == "paused"

        r = requests.delete(f"{API}/projects/{pid}", headers=H(token))
        assert r.status_code == 200


# --- Integrations ---
class TestIntegrations:
    def test_catalog(self, user_token):
        token, _ = user_token
        r = requests.get(f"{API}/integrations/catalog", headers=H(token))
        assert r.status_code == 200
        types = [i["type"] for i in r.json()]
        for t in ["n8n", "cloud_storage", "llm", "mcp"]:
            assert t in types

    def test_create_delete(self, user_token):
        token, _ = user_token
        r = requests.post(f"{API}/integrations",
                          json={"type": "n8n", "name": "TEST_n8n",
                                "config": {"base_url": "https://x.com", "api_key": "k"}},
                          headers=H(token))
        assert r.status_code == 200
        iid = r.json()["integration_id"]

        r = requests.get(f"{API}/integrations", headers=H(token))
        assert r.status_code == 200
        assert any(i["integration_id"] == iid for i in r.json())

        r = requests.delete(f"{API}/integrations/{iid}", headers=H(token))
        assert r.status_code == 200


# --- Assets ---
class TestAssets:
    def test_upload_list_download_delete(self, user_token):
        token, _ = user_token
        files = {"file": ("test.txt", io.BytesIO(b"hello world"), "text/plain")}
        r = requests.post(f"{API}/assets/upload", files=files, headers=H(token))
        assert r.status_code == 200, r.text
        aid = r.json()["asset_id"]

        r = requests.get(f"{API}/assets", headers=H(token))
        assert r.status_code == 200
        assert any(a["asset_id"] == aid for a in r.json())

        r = requests.get(f"{API}/assets/{aid}/download", headers=H(token))
        assert r.status_code == 200
        assert r.content == b"hello world"

        r = requests.post(f"{API}/assets/{aid}/share", headers=H(token))
        assert r.status_code == 200

        r = requests.delete(f"{API}/assets/{aid}", headers=H(token))
        assert r.status_code == 200


# --- Profile ---
class TestProfile:
    def test_update_profile(self, user_token):
        token, _ = user_token
        r = requests.put(f"{API}/users/me", json={"bio": "TEST bio", "ui_scale": 1.1}, headers=H(token))
        assert r.status_code == 200
        assert r.json()["bio"] == "TEST bio"
        r = requests.get(f"{API}/auth/me", headers=H(token))
        assert r.json()["bio"] == "TEST bio"


# --- AI SSE ---
class TestAI:
    def test_ai_stream(self, user_token):
        token, _ = user_token
        r = requests.post(f"{API}/ai/chat",
                          json={"message": "Say hi in 3 words", "model": "gpt-5.4", "provider": "openai"},
                          headers=H(token), stream=True, timeout=60)
        assert r.status_code == 200
        chunks = []
        got_delta = False
        for line in r.iter_lines():
            if not line:
                continue
            s = line.decode() if isinstance(line, bytes) else line
            if s.startswith("data: "):
                payload = json.loads(s[6:])
                if "delta" in payload:
                    got_delta = True
                    chunks.append(payload["delta"])
                if payload.get("done"):
                    break
        assert got_delta, "no delta streamed"


# --- Admin ---
class TestAdmin:
    def test_admin_stats(self, admin_token):
        r = requests.get(f"{API}/admin/stats", headers=H(admin_token))
        assert r.status_code == 200
        d = r.json()
        assert "total_users" in d and "recent_users" in d

    def test_admin_forbidden_for_user(self, user_token):
        token, _ = user_token
        r = requests.get(f"{API}/admin/stats", headers=H(token))
        assert r.status_code == 403
