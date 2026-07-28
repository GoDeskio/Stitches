"""
Backend tests for Bot Directory extensions:
- category on create/patch/clone
- sparkline 14-day activity
- /api/bots/directory returns activity + categories, NO token
- /api/bots/featured ranking + shape (NO token)
- ingest increments today's daily bucket
"""
import os
import re
import uuid
import time
import pytest
import requests
from pathlib import Path
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ALICE = {"email": "alice@stitches.app", "password": "Alice@123"}
ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login {creds['email']} failed: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def _get_channel(token):
    ws = requests.get(f"{BASE_URL}/api/workspaces", headers=_hdr(token), timeout=15).json()
    assert ws, "no workspaces"
    chs = requests.get(f"{BASE_URL}/api/workspaces/{ws[0]['workspace_id']}/channels", headers=_hdr(token), timeout=15).json()
    assert chs, "no channels"
    return chs[0]["channel_id"]


@pytest.fixture(scope="module")
def alice_token():
    return _login(ALICE)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


@pytest.fixture(scope="module")
def created_bots():
    ids = []  # (token, bot_id)
    yield ids
    for tok, bid in ids:
        try:
            requests.delete(f"{BASE_URL}/api/bots/{bid}", headers=_hdr(tok), timeout=10)
        except Exception:
            pass


class TestBotCategoryAndSparkline:
    def test_create_bot_with_category_and_shared(self, alice_token, created_bots):
        ch = _get_channel(alice_token)
        name = f"TEST_ci_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/bots", headers=_hdr(alice_token),
                          json={"name": name, "target_channel_id": ch, "category": "ci", "shared": True}, timeout=15)
        assert r.status_code == 200, r.text
        b = r.json()
        created_bots.append((alice_token, b["bot_id"]))
        assert b["category"] == "ci"
        assert b["shared"] is True
        assert b["token"].startswith("stbot_")
        # activity present + length 14
        assert isinstance(b["activity"], list) and len(b["activity"]) == 14
        assert all(isinstance(x, int) for x in b["activity"])
        # baseline all zeros
        assert sum(b["activity"]) == 0

    def test_create_defaults_category_general(self, alice_token, created_bots):
        ch = _get_channel(alice_token)
        r = requests.post(f"{BASE_URL}/api/bots", headers=_hdr(alice_token),
                          json={"name": f"TEST_def_{uuid.uuid4().hex[:6]}", "target_channel_id": ch}, timeout=15)
        assert r.status_code == 200
        b = r.json()
        created_bots.append((alice_token, b["bot_id"]))
        assert b["category"] == "general"

    def test_patch_category_persists(self, alice_token, created_bots):
        ch = _get_channel(alice_token)
        r = requests.post(f"{BASE_URL}/api/bots", headers=_hdr(alice_token),
                          json={"name": f"TEST_patch_{uuid.uuid4().hex[:6]}", "target_channel_id": ch, "category": "general"}, timeout=15)
        b = r.json()
        created_bots.append((alice_token, b["bot_id"]))
        r2 = requests.patch(f"{BASE_URL}/api/bots/{b['bot_id']}", headers=_hdr(alice_token),
                            json={"category": "alerts"}, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["category"] == "alerts"
        # verify via listing
        lst = requests.get(f"{BASE_URL}/api/bots", headers=_hdr(alice_token), timeout=15).json()["bots"]
        got = [x for x in lst if x["bot_id"] == b["bot_id"]][0]
        assert got["category"] == "alerts"


class TestDirectoryAndFeatured:
    def test_directory_shape_no_token(self, alice_token, admin_token, created_bots):
        ch = _get_channel(alice_token)
        name = f"TEST_dir_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{BASE_URL}/api/bots", headers=_hdr(alice_token),
                          json={"name": name, "target_channel_id": ch, "category": "support", "shared": True}, timeout=15)
        b = r.json()
        created_bots.append((alice_token, b["bot_id"]))

        # admin views directory
        r2 = requests.get(f"{BASE_URL}/api/bots/directory", headers=_hdr(admin_token), timeout=15)
        assert r2.status_code == 200
        data = r2.json()
        assert "categories" in data and isinstance(data["categories"], list)
        assert "support" in data["categories"]
        found = [x for x in data["bots"] if x["bot_id"] == b["bot_id"]]
        assert found, "shared bot missing from directory"
        d = found[0]
        assert "token" not in d, f"token exposed in directory! keys={list(d.keys())}"
        assert d["category"] == "support"
        assert isinstance(d["activity"], list) and len(d["activity"]) == 14
        assert d["owner_name"]
        assert d["is_owner"] is False

    def test_ingest_updates_sparkline_last_bucket(self, alice_token, created_bots):
        ch = _get_channel(alice_token)
        r = requests.post(f"{BASE_URL}/api/bots", headers=_hdr(alice_token),
                          json={"name": f"TEST_ing_{uuid.uuid4().hex[:6]}", "target_channel_id": ch, "category": "ci", "shared": True}, timeout=15)
        b = r.json()
        created_bots.append((alice_token, b["bot_id"]))
        token = b["token"]
        # ingest twice
        for i in range(2):
            ing = requests.post(f"{BASE_URL}/api/bots/ingest",
                                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                                json={"text": f"hello {i}"}, timeout=15)
            assert ing.status_code == 200, ing.text

        # verify sparkline last bucket increased
        lst = requests.get(f"{BASE_URL}/api/bots", headers=_hdr(alice_token), timeout=15).json()["bots"]
        got = [x for x in lst if x["bot_id"] == b["bot_id"]][0]
        assert got["activity"][-1] >= 2, f"expected today's bucket >=2, got activity={got['activity']}"
        assert got["message_count"] >= 2

    def test_featured_ranking_and_no_token(self, alice_token, admin_token, created_bots):
        # create a shared enabled bot and ingest to get recent activity
        ch = _get_channel(alice_token)
        r = requests.post(f"{BASE_URL}/api/bots", headers=_hdr(alice_token),
                          json={"name": f"TEST_feat_{uuid.uuid4().hex[:6]}", "target_channel_id": ch, "category": "monitoring", "shared": True}, timeout=15)
        b = r.json()
        created_bots.append((alice_token, b["bot_id"]))
        for _ in range(3):
            requests.post(f"{BASE_URL}/api/bots/ingest",
                          headers={"Authorization": f"Bearer {b['token']}", "Content-Type": "application/json"},
                          json={"text": "ping"}, timeout=15)

        r2 = requests.get(f"{BASE_URL}/api/bots/featured", headers=_hdr(admin_token), timeout=15)
        assert r2.status_code == 200
        data = r2.json()
        assert "bots" in data
        assert len(data["bots"]) <= 6
        # find our bot
        me = [x for x in data["bots"] if x["bot_id"] == b["bot_id"]]
        assert me, f"our shared+active bot missing from featured: {[x['name'] for x in data['bots']]}"
        f = me[0]
        assert "token" not in f
        assert f["category"] == "monitoring"
        assert "recent" in f and f["recent"] >= 3
        assert isinstance(f["activity"], list) and len(f["activity"]) == 14
        assert f["owner_name"]

    def test_featured_excludes_disabled(self, alice_token, admin_token, created_bots):
        ch = _get_channel(alice_token)
        r = requests.post(f"{BASE_URL}/api/bots", headers=_hdr(alice_token),
                          json={"name": f"TEST_dis_{uuid.uuid4().hex[:6]}", "target_channel_id": ch, "category": "ops", "shared": True}, timeout=15)
        b = r.json()
        created_bots.append((alice_token, b["bot_id"]))
        # disable
        requests.patch(f"{BASE_URL}/api/bots/{b['bot_id']}", headers=_hdr(alice_token),
                       json={"enabled": False}, timeout=15)
        r2 = requests.get(f"{BASE_URL}/api/bots/featured", headers=_hdr(admin_token), timeout=15).json()
        assert not any(x["bot_id"] == b["bot_id"] for x in r2["bots"]), "disabled bot should not appear in featured"


class TestCloneInheritsCategory:
    def test_clone_inherits_category_and_fresh_token(self, alice_token, admin_token, created_bots):
        ch_a = _get_channel(alice_token)
        r = requests.post(f"{BASE_URL}/api/bots", headers=_hdr(alice_token),
                          json={"name": f"TEST_src_{uuid.uuid4().hex[:6]}", "target_channel_id": ch_a, "category": "sales", "shared": True}, timeout=15)
        src = r.json()
        created_bots.append((alice_token, src["bot_id"]))
        ch_admin = _get_channel(admin_token)
        r2 = requests.post(f"{BASE_URL}/api/bots/{src['bot_id']}/clone", headers=_hdr(admin_token),
                           json={"name": f"TEST_clone_{uuid.uuid4().hex[:6]}", "target_channel_id": ch_admin}, timeout=15)
        assert r2.status_code == 200, r2.text
        clone = r2.json()
        created_bots.append((admin_token, clone["bot_id"]))
        assert clone["category"] == "sales"
        assert clone["shared"] is False
        assert clone["token"] and clone["token"] != src["token"]
