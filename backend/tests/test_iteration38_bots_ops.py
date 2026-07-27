"""
Iteration 38 backend tests:
- Bots (create, list, ingest with bot token, disable/rotate/delete, per-user isolation)
- Ops-alerts per-event toggles (save/get round-trip; test with no URL -> 400)
- Regression: auth, super-admin gating
"""
import os
import pytest
import requests
from dotenv import dotenv_values

fe_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or fe_env.get("REACT_APP_BACKEND_URL")).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}
DEMO = {"email": "demo@stitches.app", "password": "Demo@123"}


def _login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login failed {creds['email']}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_tok():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def demo_tok():
    return _login(DEMO)


# ---------- Regression: auth ----------
class TestAuth:
    def test_admin_login(self, admin_tok):
        assert admin_tok
        r = requests.get(f"{API}/auth/me", headers=_h(admin_tok))
        assert r.status_code == 200
        assert r.json()["email"].lower() == ADMIN["email"]

    def test_demo_login(self, demo_tok):
        assert demo_tok


# ---------- Super admin gating ----------
class TestSuperAdminGating:
    def test_whoami_admin_true(self, admin_tok):
        r = requests.get(f"{API}/admin/superadmin/whoami", headers=_h(admin_tok))
        assert r.status_code == 200
        assert r.json()["is_super_admin"] is True

    def test_db_overview_admin(self, admin_tok):
        r = requests.get(f"{API}/admin/db/overview", headers=_h(admin_tok))
        assert r.status_code == 200
        assert "collections" in r.json()

    def test_db_overview_demo_forbidden(self, demo_tok):
        r = requests.get(f"{API}/admin/db/overview", headers=_h(demo_tok))
        assert r.status_code in (401, 403)


# ---------- Ops-alerts per-event toggles ----------
class TestOpsWebhookEvents:
    def test_events_roundtrip(self, admin_tok):
        # Save with all three event toggles + min_level + quiet
        payload = {
            "events": {"update": False, "payment": True, "destructive": False},
            "min_level": "warn",
            "quiet_enabled": True,
            "quiet_start": 21, "quiet_end": 6, "tz_offset": 0,
        }
        r = requests.post(f"{API}/admin/ops-webhook", headers=_h(admin_tok), json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["events"]["update"] is False
        assert data["events"]["payment"] is True
        assert data["events"]["destructive"] is False
        assert data["min_level"] == "warn"
        assert data["quiet_enabled"] is True

        # GET verifies persistence
        r2 = requests.get(f"{API}/admin/ops-webhook", headers=_h(admin_tok))
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["events"]["update"] is False
        assert d2["events"]["payment"] is True
        assert d2["events"]["destructive"] is False

        # Restore defaults
        requests.post(f"{API}/admin/ops-webhook", headers=_h(admin_tok), json={
            "events": {"update": True, "payment": True, "destructive": True},
            "min_level": "info", "quiet_enabled": False,
        })

    def test_test_endpoint_no_url_returns_400(self, admin_tok):
        # Ensure url is empty first
        requests.post(f"{API}/admin/ops-webhook", headers=_h(admin_tok), json={"url": "", "enabled": False})
        r = requests.post(f"{API}/admin/ops-webhook/test", headers=_h(admin_tok), json={})
        assert r.status_code == 400
        detail = r.json().get("detail", "")
        assert "webhook" in detail.lower() or "url" in detail.lower()


# ---------- Bots ----------
@pytest.fixture(scope="module")
def admin_channel(admin_tok):
    """Pick first workspace + first channel for admin."""
    ws = requests.get(f"{API}/workspaces", headers=_h(admin_tok)).json()
    assert ws, "admin has no workspaces"
    wsid = ws[0]["workspace_id"]
    chs = requests.get(f"{API}/workspaces/{wsid}/channels", headers=_h(admin_tok)).json()
    assert chs, "admin has no channels"
    return {"workspace_id": wsid, "channel_id": chs[0]["channel_id"], "channel_name": chs[0]["name"]}


@pytest.fixture(scope="module")
def demo_channel(demo_tok):
    ws = requests.get(f"{API}/workspaces", headers=_h(demo_tok)).json()
    if not ws:
        pytest.skip("demo has no workspaces")
    wsid = ws[0]["workspace_id"]
    chs = requests.get(f"{API}/workspaces/{wsid}/channels", headers=_h(demo_tok)).json()
    if not chs:
        pytest.skip("demo has no channels")
    return {"workspace_id": wsid, "channel_id": chs[0]["channel_id"]}


class TestBots:
    created_bot_ids = []

    def test_create_bot(self, admin_tok, admin_channel):
        payload = {"name": "TEST_qa_bot", "target_channel_id": admin_channel["channel_id"]}
        r = requests.post(f"{API}/bots", headers=_h(admin_tok), json=payload)
        assert r.status_code == 200, r.text
        b = r.json()
        assert b["name"] == "TEST_qa_bot"
        assert b["enabled"] is True
        assert b["token"].startswith("stbot_")
        assert b["target_channel_id"] == admin_channel["channel_id"]
        assert b["message_count"] == 0
        TestBots.created_bot_ids.append(b["bot_id"])
        TestBots.token = b["token"]
        TestBots.bot_id = b["bot_id"]

    def test_list_bots_shows_created(self, admin_tok):
        r = requests.get(f"{API}/bots", headers=_h(admin_tok))
        assert r.status_code == 200
        ids = [b["bot_id"] for b in r.json()["bots"]]
        assert TestBots.bot_id in ids

    def test_ingest_no_token_401(self):
        r = requests.post(f"{API}/bots/ingest", json={"text": "hi"})
        assert r.status_code == 401

    def test_ingest_bad_token_401(self):
        r = requests.post(f"{API}/bots/ingest",
                          headers={"Authorization": "Bearer stbot_wrong_xxx", "Content-Type": "application/json"},
                          json={"text": "hi"})
        assert r.status_code == 401

    def test_ingest_success_and_message_persists(self, admin_tok, admin_channel):
        # Ingest via bot token
        r = requests.post(f"{API}/bots/ingest",
                          headers={"Authorization": f"Bearer {TestBots.token}", "Content-Type": "application/json"},
                          json={"text": "TEST_bot_hello", "sender_name": "CI"})
        assert r.status_code == 200, r.text
        assert r.json()["ok"] is True
        mid = r.json()["message_id"]
        assert mid

        # message_count increments
        bots = requests.get(f"{API}/bots", headers=_h(admin_tok)).json()["bots"]
        me = [b for b in bots if b["bot_id"] == TestBots.bot_id][0]
        assert me["message_count"] >= 1

        # message appears in channel
        msgs = requests.get(f"{API}/channels/{admin_channel['channel_id']}/messages",
                            headers=_h(admin_tok)).json()
        texts = [m.get("text", "") for m in (msgs if isinstance(msgs, list) else msgs.get("messages", []))]
        assert any("TEST_bot_hello" in t for t in texts), f"message not found in channel; got {texts[:5]}"

    def test_disable_bot_ingest_403(self, admin_tok):
        r = requests.patch(f"{API}/bots/{TestBots.bot_id}", headers=_h(admin_tok), json={"enabled": False})
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        r2 = requests.post(f"{API}/bots/ingest",
                           headers={"Authorization": f"Bearer {TestBots.token}", "Content-Type": "application/json"},
                           json={"text": "should fail"})
        assert r2.status_code == 403
        # Re-enable
        requests.patch(f"{API}/bots/{TestBots.bot_id}", headers=_h(admin_tok), json={"enabled": True})

    def test_rotate_invalidates_old_token(self, admin_tok):
        old_token = TestBots.token
        r = requests.post(f"{API}/bots/{TestBots.bot_id}/rotate", headers=_h(admin_tok))
        assert r.status_code == 200
        new_token = r.json()["token"]
        assert new_token and new_token != old_token
        TestBots.token = new_token
        # Old token now 401
        r_old = requests.post(f"{API}/bots/ingest",
                              headers={"Authorization": f"Bearer {old_token}", "Content-Type": "application/json"},
                              json={"text": "old"})
        assert r_old.status_code == 401
        # New token still works
        r_new = requests.post(f"{API}/bots/ingest",
                              headers={"Authorization": f"Bearer {new_token}", "Content-Type": "application/json"},
                              json={"text": "TEST_after_rotate"})
        assert r_new.status_code == 200

    def test_bots_are_per_user(self, demo_tok):
        # demo user shouldn't see admin's bot
        r = requests.get(f"{API}/bots", headers=_h(demo_tok))
        assert r.status_code == 200
        ids = [b["bot_id"] for b in r.json()["bots"]]
        assert TestBots.bot_id not in ids

    def test_delete_bot(self, admin_tok):
        r = requests.delete(f"{API}/bots/{TestBots.bot_id}", headers=_h(admin_tok))
        assert r.status_code == 200
        assert r.json()["ok"] is True
        # Not in list
        r2 = requests.get(f"{API}/bots", headers=_h(admin_tok))
        ids = [b["bot_id"] for b in r2.json()["bots"]]
        assert TestBots.bot_id not in ids
        # Token invalid post-delete
        r3 = requests.post(f"{API}/bots/ingest",
                           headers={"Authorization": f"Bearer {TestBots.token}", "Content-Type": "application/json"},
                           json={"text": "x"})
        assert r3.status_code == 401


# ---------- Regression: messaging ----------
class TestMessagingRegression:
    def test_send_message(self, admin_tok, admin_channel):
        r = requests.post(f"{API}/messages",
                          headers=_h(admin_tok),
                          json={"channel_id": admin_channel["channel_id"], "text": "TEST_regression_msg"})
        assert r.status_code in (200, 201), r.text

    def test_projects_list(self, admin_tok):
        r = requests.get(f"{API}/projects", headers=_h(admin_tok))
        assert r.status_code == 200


# ---------- Cleanup ----------
@pytest.fixture(scope="module", autouse=True)
def _cleanup(admin_tok):
    yield
    # Delete any leftover TEST_ bots for admin
    try:
        bots = requests.get(f"{API}/bots", headers=_h(admin_tok)).json().get("bots", [])
        for b in bots:
            if b.get("name", "").startswith("TEST_"):
                requests.delete(f"{API}/bots/{b['bot_id']}", headers=_h(admin_tok))
    except Exception:
        pass
