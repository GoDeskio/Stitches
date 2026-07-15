"""Regression tests after backend refactor split (server.py -> core.py + routers/*)."""
import os, io, uuid, asyncio, json
import pytest
import requests
import websockets

BASE = "https://stitches-connect.preview.emergentagent.com"
API = f"{BASE}/api"

CREDS = {
    "admin": ("admin@stitches.app", "Admin@123"),
    "demo":  ("demo@stitches.app", "Demo@123"),
    "alice": ("alice@stitches.app", "Alice@123"),
    "bob":   ("bob@stitches.app", "Bob@123"),
}

def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login {email} -> {r.status_code}: {r.text}"
    d = r.json()
    return d.get("access_token") or d.get("token")

@pytest.fixture(scope="module")
def tokens():
    return {k: _login(*v) for k, v in CREDS.items()}

def h(t): return {"Authorization": f"Bearer {t}"}


class TestAuth:
    def test_all_four_logins(self, tokens):
        assert set(tokens.keys()) == {"admin","demo","alice","bob"}

    def test_me(self, tokens):
        r = requests.get(f"{API}/auth/me", headers=h(tokens["alice"]))
        assert r.status_code == 200
        assert r.json()["email"] == "alice@stitches.app"

    def test_register_disabled_403(self, tokens):
        email = f"regr_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Pass@123", "name": "R"})
        assert r.status_code in (200, 201), r.text
        tok = _login(email, "Pass@123")
        me = requests.get(f"{API}/auth/me", headers=h(tok)).json()
        uid = me.get("user_id") or me.get("id")
        assert uid
        r = requests.put(f"{API}/admin/users/{uid}", headers=h(tokens["admin"]), json={"is_active": False})
        assert r.status_code == 200, r.text
        r = requests.post(f"{API}/auth/login", json={"email": email, "password": "Pass@123"})
        assert r.status_code == 403


class TestUsersFriendsDMs:
    def test_friends_returns_200(self, tokens):
        """Regression: is_online moved to core.py - /friends must not NameError."""
        r = requests.get(f"{API}/friends", headers=h(tokens["alice"]))
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_dms_returns_200(self, tokens):
        r = requests.get(f"{API}/dms", headers=h(tokens["alice"]))
        assert r.status_code == 200, r.text

    def test_presence_ping(self, tokens):
        r = requests.post(f"{API}/presence/ping", headers=h(tokens["alice"]))
        assert r.status_code == 200

    def test_profile_update(self, tokens):
        r = requests.put(f"{API}/users/me", headers=h(tokens["bob"]), json={"bio": "regr bio"})
        assert r.status_code == 200
        r = requests.get(f"{API}/auth/me", headers=h(tokens["bob"]))
        assert r.json().get("bio") == "regr bio"

    def test_notes_crud(self, tokens):
        r = requests.post(f"{API}/notes", headers=h(tokens["alice"]),
                          json={"title": "TEST_note", "content": "hi"})
        assert r.status_code in (200,201), r.text
        d = r.json()
        nid = d.get("note_id") or d.get("id")
        assert nid
        r = requests.get(f"{API}/notes", headers=h(tokens["alice"]))
        assert r.status_code == 200
        r = requests.delete(f"{API}/notes/{nid}", headers=h(tokens["alice"]))
        assert r.status_code in (200,204)


class TestMessaging:
    def test_workspace_channel_message(self, tokens):
        t = tokens["alice"]
        r = requests.post(f"{API}/workspaces", headers=h(t), json={"name": "TEST_ws"})
        assert r.status_code == 200, r.text
        wid = r.json()["workspace_id"]
        r = requests.post(f"{API}/channels", headers=h(t),
                          json={"workspace_id": wid, "name": "test-ch"})
        assert r.status_code == 200, r.text
        cid = r.json()["channel_id"]
        r = requests.post(f"{API}/messages", headers=h(t),
                          json={"channel_id": cid, "text": "hello world"})
        assert r.status_code == 200, r.text
        mid = r.json()["message_id"]
        # reaction
        r = requests.post(f"{API}/messages/{mid}/react", headers=h(t),
                          json={"emoji": "\U0001f44d"})
        assert r.status_code == 200, r.text
        # thread reply
        r = requests.post(f"{API}/messages", headers=h(t),
                          json={"channel_id": cid, "text": "in thread", "parent_id": mid})
        assert r.status_code == 200, r.text
        # unreads
        r = requests.get(f"{API}/unreads", headers=h(tokens["bob"]))
        assert r.status_code == 200

    def test_websocket_realtime(self, tokens):
        """Regression: ws endpoint stayed in thin server.py."""
        t = tokens["alice"]
        wid = requests.post(f"{API}/workspaces", headers=h(t), json={"name": "TEST_ws_ws"}).json()["workspace_id"]
        cid = requests.post(f"{API}/channels", headers=h(t), json={"workspace_id": wid, "name": "wsc"}).json()["channel_id"]
        ws_url = BASE.replace("https://", "wss://") + f"/api/ws/{cid}?token={t}"
        async def run():
            try:
                async with websockets.connect(ws_url, open_timeout=15, close_timeout=5) as ws:
                    await asyncio.sleep(0.5)
                    requests.post(f"{API}/messages", headers=h(t), json={"channel_id": cid, "text": "ws hi"})
                    msg = await asyncio.wait_for(ws.recv(), timeout=8)
                    return msg
            except Exception as e:
                return f"WS_ERR:{e}"
        result = asyncio.new_event_loop().run_until_complete(run())
        assert result and not str(result).startswith("WS_ERR"), f"WebSocket failed: {result}"


class TestProjects:
    def test_project_kanban_membership(self, tokens):
        t_alice = tokens["alice"]; t_bob = tokens["bob"]
        r = requests.post(f"{API}/projects", headers=h(t_alice), json={"name": "TEST_proj"})
        assert r.status_code == 200, r.text
        pid = r.json()["project_id"]
        # non-member bob -> 403
        r = requests.get(f"{API}/projects/{pid}/tasks", headers=h(t_bob))
        assert r.status_code == 403, f"expected 403 (membership gate), got {r.status_code}"
        # create task
        r = requests.post(f"{API}/projects/{pid}/tasks", headers=h(t_alice),
                          json={"title": "TEST_task", "status": "todo"})
        assert r.status_code == 200, r.text
        d = r.json()
        tid = d.get("task_id") or d.get("id")
        assert tid
        # move status
        r = requests.put(f"{API}/tasks/{tid}", headers=h(t_alice), json={"status": "in_progress"})
        assert r.status_code == 200
        requests.delete(f"{API}/tasks/{tid}", headers=h(t_alice))
        requests.delete(f"{API}/projects/{pid}", headers=h(t_alice))


class TestAssets:
    def test_upload_list_download(self, tokens):
        t = tokens["alice"]
        files = {"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")}
        r = requests.post(f"{API}/assets/upload", headers=h(t), files=files)
        assert r.status_code == 200, r.text
        aid = r.json()["asset_id"]
        r = requests.get(f"{API}/assets", headers=h(t))
        assert r.status_code == 200
        r = requests.get(f"{API}/assets/{aid}/download", headers=h(t), allow_redirects=True)
        assert r.status_code == 200
        requests.delete(f"{API}/assets/{aid}", headers=h(t))


class TestIntegrations:
    def test_catalog_8_connectors(self, tokens):
        r = requests.get(f"{API}/integrations/catalog", headers=h(tokens["alice"]))
        assert r.status_code == 200
        cat = r.json()
        types = {c["type"] for c in cat}
        assert {"n8n","email","custom","aws_s3","dropbox","google_drive","llm","mcp"}.issubset(types)

    def test_custom_connect_test(self, tokens):
        t = tokens["alice"]
        r = requests.post(f"{API}/integrations", headers=h(t), json={
            "type": "custom", "name": "TEST_httpbin", "auth_method": "basic",
            "config": {"base_url": "https://httpbin.org/basic-auth/user/pass",
                       "username": "user", "password": "pass"}
        })
        assert r.status_code == 200, r.text
        d = r.json()
        iid = d.get("integration_id") or d.get("id")
        assert iid
        lst = requests.get(f"{API}/integrations", headers=h(t)).json()
        it = [x for x in lst if (x.get("integration_id") or x.get("id")) == iid][0]
        cm = it.get("config_masked") or it.get("config") or {}
        assert cm.get("password") in ("\u2022\u2022\u2022\u2022\u2022\u2022", "******", None) or "pass" not in str(cm.get("password",""))
        r = requests.post(f"{API}/integrations/{iid}/test", headers=h(t))
        assert r.status_code == 200
        assert r.json().get("ok") is True
        r = requests.get(f"{API}/admin/integrations", headers=h(tokens["admin"]))
        assert r.status_code == 200
        requests.delete(f"{API}/integrations/{iid}", headers=h(t))


class TestAI:
    def test_ai_stream(self, tokens):
        r = requests.post(f"{API}/ai/chat", headers=h(tokens["alice"]),
                          json={"message": "Say hi in one word"}, stream=True, timeout=45)
        assert r.status_code == 200
        got = b""
        for chunk in r.iter_content(1024):
            got += chunk
            if len(got) > 20: break
        assert len(got) > 0


class TestActivityAdmin:
    def test_activity_me(self, tokens):
        r = requests.get(f"{API}/activity/me", headers=h(tokens["alice"]))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_admin_users_list(self, tokens):
        r = requests.get(f"{API}/admin/users", headers=h(tokens["admin"]))
        assert r.status_code == 200
        assert len(r.json()) >= 4

    def test_admin_monitoring(self, tokens):
        r = requests.get(f"{API}/admin/monitoring", headers=h(tokens["admin"]))
        assert r.status_code == 200
