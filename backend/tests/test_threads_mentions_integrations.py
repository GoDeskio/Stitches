"""Tests for threads, mentions, and integrations features (iteration 10)."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stitches-connect.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"

ALICE = {"email": "alice@stitches.app", "password": "Alice@123"}
BOB = {"email": "bob@stitches.app", "password": "Bob@123"}
ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}


def login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text}"
    return r.json()["token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def alice_token():
    return login(ALICE)


@pytest.fixture(scope="module")
def bob_token():
    return login(BOB)


@pytest.fixture(scope="module")
def admin_token():
    return login(ADMIN)


@pytest.fixture(scope="module")
def shared_channel(alice_token, bob_token):
    """Alice creates workspace, adds Bob, returns (workspace_id, channel_id, bob_user_id, bob_name)"""
    # get bob info
    bob_me = requests.get(f"{API}/auth/me", headers=auth(bob_token)).json()

    ws_name = f"TEST_ws_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/workspaces", json={"name": ws_name}, headers=auth(alice_token))
    assert r.status_code == 200
    ws = r.json()
    ws_id = ws["workspace_id"]

    # invite bob
    r = requests.post(f"{API}/workspaces/{ws_id}/invite", json={"email": BOB["email"]}, headers=auth(alice_token))
    assert r.status_code == 200

    # list channels (created auto: general, random)
    r = requests.get(f"{API}/workspaces/{ws_id}/channels", headers=auth(alice_token))
    channels = r.json()
    assert len(channels) >= 1
    ch_id = channels[0]["channel_id"]

    yield {"ws_id": ws_id, "ch_id": ch_id, "bob_user_id": bob_me["user_id"], "bob_name": bob_me["name"]}

    # cleanup: delete workspace's messages and workspace itself is not exposed; leave. (No delete endpoint exposed)


# ---------- THREADS ----------
class TestThreads:
    def test_post_top_level_message(self, alice_token, shared_channel):
        r = requests.post(f"{API}/messages",
                          json={"channel_id": shared_channel["ch_id"], "text": "TEST parent message"},
                          headers=auth(alice_token))
        assert r.status_code == 200
        data = r.json()
        assert data["text"] == "TEST parent message"
        assert data.get("parent_id") is None
        shared_channel["parent_id"] = data["message_id"]

    def test_post_reply_with_parent_id(self, alice_token, shared_channel):
        parent_id = shared_channel["parent_id"]
        r = requests.post(f"{API}/messages",
                          json={"channel_id": shared_channel["ch_id"], "text": "TEST reply in thread", "parent_id": parent_id},
                          headers=auth(alice_token))
        assert r.status_code == 200
        data = r.json()
        assert data["parent_id"] == parent_id

    def test_fetch_messages_returns_thread(self, alice_token, shared_channel):
        r = requests.get(f"{API}/channels/{shared_channel['ch_id']}/messages", headers=auth(alice_token))
        assert r.status_code == 200
        msgs = r.json()
        parents = [m for m in msgs if not m.get("parent_id")]
        replies = [m for m in msgs if m.get("parent_id") == shared_channel["parent_id"]]
        assert len(parents) >= 1
        assert len(replies) >= 1


# ---------- MENTIONS ----------
class TestMentions:
    def test_alice_mentions_bob_creates_notification(self, alice_token, bob_token, shared_channel):
        # Bob's current notifs baseline
        r0 = requests.get(f"{API}/notifications", headers=auth(bob_token))
        base_unread = r0.json().get("unread", 0)

        bob_uid = shared_channel["bob_user_id"]
        bob_name = shared_channel["bob_name"]
        text = f"Hey @{bob_name} TEST mention!"
        r = requests.post(f"{API}/messages",
                          json={"channel_id": shared_channel["ch_id"], "text": text, "mentions": [bob_uid]},
                          headers=auth(alice_token))
        assert r.status_code == 200
        assert r.json().get("mentions") == [bob_uid]

        # Bob should have a mention notification
        time.sleep(0.5)
        r = requests.get(f"{API}/notifications", headers=auth(bob_token))
        assert r.status_code == 200
        notifs = r.json().get("notifications", [])
        mention_notifs = [n for n in notifs if n.get("type") == "mention"]
        assert len(mention_notifs) >= 1, f"Expected mention notif for Bob. Got: {notifs[:3]}"
        assert r.json().get("unread", 0) > base_unread

    def test_self_mention_no_notification(self, alice_token, shared_channel):
        alice_me = requests.get(f"{API}/auth/me", headers=auth(alice_token)).json()
        r0 = requests.get(f"{API}/notifications", headers=auth(alice_token))
        base_mentions = sum(1 for n in r0.json().get("notifications", []) if n.get("type") == "mention")
        r = requests.post(f"{API}/messages",
                          json={"channel_id": shared_channel["ch_id"], "text": f"Talking to @{alice_me['name']}",
                                "mentions": [alice_me["user_id"]]},
                          headers=auth(alice_token))
        assert r.status_code == 200
        r1 = requests.get(f"{API}/notifications", headers=auth(alice_token))
        after = sum(1 for n in r1.json().get("notifications", []) if n.get("type") == "mention")
        assert after == base_mentions


# ---------- INTEGRATIONS ----------
class TestIntegrationsCatalog:
    def test_catalog_has_six_types(self, alice_token):
        r = requests.get(f"{API}/integrations/catalog", headers=auth(alice_token))
        assert r.status_code == 200
        cat = r.json()
        types = {c["type"] for c in cat}
        assert {"n8n", "aws_s3", "dropbox", "google_drive", "llm", "mcp"}.issubset(types)
        for c in cat:
            assert "actions" in c
            assert isinstance(c["fields"], list)


@pytest.fixture(scope="module")
def n8n_integration(alice_token):
    r = requests.post(f"{API}/integrations",
                      json={"type": "n8n", "name": "TEST_n8n",
                            "config": {"webhook_url": "https://httpbin.org/post"}},
                      headers=auth(alice_token))
    assert r.status_code == 200
    iid = r.json()["integration_id"]
    yield iid
    requests.delete(f"{API}/integrations/{iid}", headers=auth(alice_token))


@pytest.fixture(scope="module")
def s3_integration(alice_token):
    r = requests.post(f"{API}/integrations",
                      json={"type": "aws_s3", "name": "TEST_s3",
                            "config": {"access_key": "AKIAFAKE", "secret_key": "fakesecret",
                                       "region": "us-east-1", "bucket": "fakebucket-nonexistent-xyz"}},
                      headers=auth(alice_token))
    assert r.status_code == 200
    iid = r.json()["integration_id"]
    yield iid
    requests.delete(f"{API}/integrations/{iid}", headers=auth(alice_token))


@pytest.fixture(scope="module")
def dropbox_integration(alice_token):
    r = requests.post(f"{API}/integrations",
                      json={"type": "dropbox", "name": "TEST_dropbox",
                            "config": {"access_token": "fake-dropbox-token"}},
                      headers=auth(alice_token))
    assert r.status_code == 200
    iid = r.json()["integration_id"]
    yield iid
    requests.delete(f"{API}/integrations/{iid}", headers=auth(alice_token))


@pytest.fixture(scope="module")
def gdrive_integration(alice_token):
    r = requests.post(f"{API}/integrations",
                      json={"type": "google_drive", "name": "TEST_gdrive",
                            "config": {"access_token": "fake-gdrive-token"}},
                      headers=auth(alice_token))
    assert r.status_code == 200
    iid = r.json()["integration_id"]
    yield iid
    requests.delete(f"{API}/integrations/{iid}", headers=auth(alice_token))


@pytest.fixture(scope="module")
def llm_integration(alice_token):
    r = requests.post(f"{API}/integrations",
                      json={"type": "llm", "name": "TEST_llm",
                            "config": {"provider": "openai", "api_key": "sk-fake", "model": "gpt-5.4"}},
                      headers=auth(alice_token))
    assert r.status_code == 200
    iid = r.json()["integration_id"]
    yield iid
    requests.delete(f"{API}/integrations/{iid}", headers=auth(alice_token))


class TestIntegrationsList:
    def test_list_masks_secrets(self, alice_token, n8n_integration, s3_integration):
        r = requests.get(f"{API}/integrations", headers=auth(alice_token))
        assert r.status_code == 200
        items = r.json()
        for it in items:
            # config must be removed and config_masked present
            assert "config" not in it
            assert "config_masked" in it
            assert "actions" in it
        s3 = next(it for it in items if it["integration_id"] == s3_integration)
        # secret should be masked
        assert s3["config_masked"].get("secret_key") == "••••••"
        assert s3["config_masked"].get("access_key") == "••••••"
        # non-sensitive kept
        assert s3["config_masked"].get("bucket") == "fakebucket-nonexistent-xyz"


class TestIntegrationRun:
    def test_n8n_run_reachable(self, alice_token, n8n_integration):
        r = requests.post(f"{API}/integrations/{n8n_integration}/run",
                          json={"payload": {"hello": "world"}}, headers=auth(alice_token), timeout=45)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ok" in data and "status_code" in data
        assert data["status_code"] == 200
        assert data["ok"] is True

    def test_run_non_n8n_rejected(self, alice_token, s3_integration):
        r = requests.post(f"{API}/integrations/{s3_integration}/run",
                          json={"payload": {}}, headers=auth(alice_token))
        assert r.status_code == 400


class TestIntegrationFiles:
    def test_s3_files_bad_creds_returns_400(self, alice_token, s3_integration):
        r = requests.get(f"{API}/integrations/{s3_integration}/files", headers=auth(alice_token), timeout=30)
        assert r.status_code == 400
        assert "detail" in r.json()

    def test_dropbox_files_bad_creds_returns_400(self, alice_token, dropbox_integration):
        r = requests.get(f"{API}/integrations/{dropbox_integration}/files", headers=auth(alice_token), timeout=30)
        assert r.status_code == 400
        assert "detail" in r.json()

    def test_gdrive_files_bad_creds_returns_400(self, alice_token, gdrive_integration):
        r = requests.get(f"{API}/integrations/{gdrive_integration}/files", headers=auth(alice_token), timeout=30)
        assert r.status_code == 400
        assert "detail" in r.json()

    def test_n8n_files_not_supported(self, alice_token, n8n_integration):
        r = requests.get(f"{API}/integrations/{n8n_integration}/files", headers=auth(alice_token))
        assert r.status_code == 400


class TestIntegrationTest:
    def test_n8n_test_endpoint(self, alice_token, n8n_integration):
        r = requests.post(f"{API}/integrations/{n8n_integration}/test", headers=auth(alice_token))
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is True

    def test_llm_test_endpoint(self, alice_token, llm_integration):
        r = requests.post(f"{API}/integrations/{llm_integration}/test", headers=auth(alice_token))
        assert r.status_code == 200
        assert "ok" in r.json()

    def test_s3_test_bad_creds_graceful(self, alice_token, s3_integration):
        r = requests.post(f"{API}/integrations/{s3_integration}/test", headers=auth(alice_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is False
        assert "message" in d

    def test_dropbox_test_bad_creds_graceful(self, alice_token, dropbox_integration):
        r = requests.post(f"{API}/integrations/{dropbox_integration}/test", headers=auth(alice_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is False

    def test_gdrive_test_bad_creds_graceful(self, alice_token, gdrive_integration):
        r = requests.post(f"{API}/integrations/{gdrive_integration}/test", headers=auth(alice_token), timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d.get("ok") is False


class TestAdminIntegrations:
    def test_admin_lists_all_integrations(self, admin_token, n8n_integration, s3_integration):
        r = requests.get(f"{API}/admin/integrations", headers=auth(admin_token))
        assert r.status_code == 200
        items = r.json()
        ids = {it["integration_id"] for it in items}
        assert n8n_integration in ids
        assert s3_integration in ids
        # Must include owner_name, must NOT include config
        for it in items:
            assert "owner_name" in it
            assert "config" not in it

    def test_non_admin_forbidden(self, alice_token):
        r = requests.get(f"{API}/admin/integrations", headers=auth(alice_token))
        assert r.status_code == 403


# ---------- REGRESSION ----------
class TestRegression:
    def test_normal_message_and_reaction(self, alice_token, shared_channel):
        r = requests.post(f"{API}/messages",
                          json={"channel_id": shared_channel["ch_id"], "text": "TEST regression msg"},
                          headers=auth(alice_token))
        assert r.status_code == 200
        mid = r.json()["message_id"]
        r2 = requests.post(f"{API}/messages/{mid}/react", json={"emoji": "🎉"}, headers=auth(alice_token))
        assert r2.status_code == 200
        assert "🎉" in r2.json()["reactions"]

    def test_unreads_endpoint(self, alice_token):
        r = requests.get(f"{API}/unreads", headers=auth(alice_token))
        assert r.status_code == 200
        assert "channels" in r.json()
