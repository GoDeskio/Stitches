"""
Backend tests for iteration 42:
- Rich card ingest & render payload
- Bot Health Alerts (scan-health endpoint, idempotency, re-arm)
- Regression: plain-text ingest, empty ingest 400
"""
import os
import uuid
import time
import asyncio
import pytest
import requests
from datetime import datetime, timezone, timedelta
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ALICE = {"email": "alice@stitches.app", "password": "Alice@123"}
ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}
BOB   = {"email": "bob@stitches.app",   "password": "Bob@123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"login {creds['email']}: {r.status_code} {r.text[:200]}"
    return r.json()["token"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


def _get_channel(token):
    ws = requests.get(f"{BASE_URL}/api/workspaces", headers=_hdr(token), timeout=15).json()
    assert ws, "no workspaces"
    chs = requests.get(f"{BASE_URL}/api/workspaces/{ws[0]['workspace_id']}/channels", headers=_hdr(token), timeout=15).json()
    assert chs, "no channels"
    return chs[0]["channel_id"], ws[0]["workspace_id"]


@pytest.fixture(scope="module")
def alice_token(): return _login(ALICE)


@pytest.fixture(scope="module")
def admin_token(): return _login(ADMIN)


@pytest.fixture(scope="module")
def bob_token():   return _login(BOB)


@pytest.fixture(scope="module")
def created_bots():
    ids = []  # (owner_token, bot_id)
    yield ids
    for tok, bid in ids:
        try:
            requests.delete(f"{BASE_URL}/api/bots/{bid}", headers=_hdr(tok), timeout=10)
        except Exception:
            pass


def _make_bot(token, category="general", shared=False):
    ch, _ = _get_channel(token)
    name = f"TEST_iter42_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{BASE_URL}/api/bots", headers=_hdr(token),
                      json={"name": name, "target_channel_id": ch, "category": category, "shared": shared}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json(), ch


# ---------- Rich Card ----------
class TestRichCardIngest:
    def test_card_only_ingest_creates_message_with_card(self, alice_token, created_bots):
        b, ch = _make_bot(alice_token)
        created_bots.append((alice_token, b["bot_id"]))
        card = {
            "title": "Build #421",
            "status": "success",
            "fields": [{"label": "Branch", "value": "main"}, {"label": "Duration", "value": "3m 12s"}],
            "link": "https://ci.example.com/build/421",
        }
        r = requests.post(f"{BASE_URL}/api/bots/ingest",
                          headers={"Authorization": f"Bearer {b['token']}", "Content-Type": "application/json"},
                          json={"card": card}, timeout=15)
        assert r.status_code == 200, r.text
        mid = r.json()["message_id"]

        # verify persisted via channel messages
        msgs = requests.get(f"{BASE_URL}/api/channels/{ch}/messages", headers=_hdr(alice_token), timeout=15).json()
        m = next((x for x in msgs if x["message_id"] == mid), None)
        assert m is not None, "created card message missing from channel"
        assert m.get("card"), f"card field missing in stored message: {m}"
        assert m["card"]["title"] == "Build #421"
        assert m["card"]["status"] == "success"
        assert m["card"]["link"].startswith("https://ci.example.com")
        assert len(m["card"]["fields"]) == 2
        assert m["card"]["fields"][0]["label"] == "Branch"
        assert m["card"]["fields"][0]["value"] == "main"

    def test_text_plus_card_both_persist(self, alice_token, created_bots):
        b, ch = _make_bot(alice_token)
        created_bots.append((alice_token, b["bot_id"]))
        card = {"title": "Alert!", "status": "error", "fields": [{"label": "Service", "value": "api"}]}
        r = requests.post(f"{BASE_URL}/api/bots/ingest",
                          headers={"Authorization": f"Bearer {b['token']}", "Content-Type": "application/json"},
                          json={"text": "See details", "card": card}, timeout=15)
        assert r.status_code == 200
        mid = r.json()["message_id"]
        msgs = requests.get(f"{BASE_URL}/api/channels/{ch}/messages", headers=_hdr(alice_token), timeout=15).json()
        m = next(x for x in msgs if x["message_id"] == mid)
        assert m["text"] == "See details"
        assert m["card"]["status"] == "error"

    def test_neither_text_nor_card_returns_400(self, alice_token, created_bots):
        b, _ = _make_bot(alice_token)
        created_bots.append((alice_token, b["bot_id"]))
        r = requests.post(f"{BASE_URL}/api/bots/ingest",
                          headers={"Authorization": f"Bearer {b['token']}", "Content-Type": "application/json"},
                          json={}, timeout=15)
        assert r.status_code == 400, r.text

    def test_invalid_status_falls_back_to_info(self, alice_token, created_bots):
        b, ch = _make_bot(alice_token)
        created_bots.append((alice_token, b["bot_id"]))
        r = requests.post(f"{BASE_URL}/api/bots/ingest",
                          headers={"Authorization": f"Bearer {b['token']}", "Content-Type": "application/json"},
                          json={"card": {"title": "Ping", "status": "bogus"}}, timeout=15)
        assert r.status_code == 200
        mid = r.json()["message_id"]
        msgs = requests.get(f"{BASE_URL}/api/channels/{ch}/messages", headers=_hdr(alice_token), timeout=15).json()
        m = next(x for x in msgs if x["message_id"] == mid)
        assert m["card"]["status"] == "info"

    def test_plain_text_ingest_regression(self, alice_token, created_bots):
        b, ch = _make_bot(alice_token)
        created_bots.append((alice_token, b["bot_id"]))
        r = requests.post(f"{BASE_URL}/api/bots/ingest",
                          headers={"Authorization": f"Bearer {b['token']}", "Content-Type": "application/json"},
                          json={"text": "hello from bot"}, timeout=15)
        assert r.status_code == 200
        mid = r.json()["message_id"]
        msgs = requests.get(f"{BASE_URL}/api/channels/{ch}/messages", headers=_hdr(alice_token), timeout=15).json()
        m = next(x for x in msgs if x["message_id"] == mid)
        assert m["text"] == "hello from bot"
        assert m.get("card") in (None, {}), f"unexpected card on plain-text msg: {m.get('card')}"


# ---------- Bot Health Alerts ----------
class TestBotHealthScan:
    def test_non_admin_blocked(self, alice_token):
        r = requests.post(f"{BASE_URL}/api/admin/bots/scan-health", headers=_hdr(alice_token), timeout=15)
        assert r.status_code in (401, 403), f"non-admin should be blocked, got {r.status_code}"

    def test_admin_scan_returns_shape(self, admin_token):
        r = requests.post(f"{BASE_URL}/api/admin/bots/scan-health", headers=_hdr(admin_token), timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert "alerted" in data and isinstance(data["alerted"], int)

    def test_health_alert_flow_end_to_end(self, alice_token, admin_token, created_bots):
        # Create a fresh bot (owned by alice)
        b, _ = _make_bot(alice_token)
        created_bots.append((alice_token, b["bot_id"]))
        bot_id = b["bot_id"]

        # Backdate created_at & clear last_used_at in Mongo so it's stale
        from pymongo import MongoClient
        mc = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        dbname = dotenv_values("/app/backend/.env").get("DB_NAME") or "test_database"
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        res = mc[dbname].bots.update_one({"bot_id": bot_id},
                                         {"$set": {"created_at": old},
                                          "$unset": {"last_used_at": "", "stale_alerted": ""}})
        assert res.matched_count == 1, "test bot not found in mongo"

        def _notifs(tok):
            j = requests.get(f"{BASE_URL}/api/notifications", headers=_hdr(tok), timeout=15).json()
            return j.get("notifications", j) if isinstance(j, dict) else j
        # Note pre-existing bot notifications so we can find the new one
        before = _notifs(alice_token)
        before_bot_ids = {n["notification_id"] for n in before if n.get("type") == "bot"}

        # Admin runs scan-health
        r = requests.post(f"{BASE_URL}/api/admin/bots/scan-health", headers=_hdr(admin_token), timeout=15)
        assert r.status_code == 200
        assert r.json()["alerted"] >= 1

        # Alice sees new bot notification
        after = _notifs(alice_token)
        new_bot_notifs = [n for n in after if n.get("type") == "bot" and n["notification_id"] not in before_bot_ids]
        assert new_bot_notifs, "expected a new 'bot' notification for owner alice"
        n = new_bot_notifs[0]
        assert "quiet" in (n.get("title", "") + n.get("body", "")).lower()

        # Idempotency — second scan does not re-alert this bot
        before2 = _notifs(alice_token)
        n_bot_before2 = sum(1 for x in before2 if x.get("type") == "bot")
        requests.post(f"{BASE_URL}/api/admin/bots/scan-health", headers=_hdr(admin_token), timeout=15)
        after2 = _notifs(alice_token)
        # Same bot shouldn't produce another notif — total bot notifs should match unless *other* stale bots exist
        # We check that our specific bot did not re-trigger by ensuring the count did not go up by >= 1 for our bot
        # (since bot notifs don't carry bot_id, we use total count as a proxy; this may pass even if unrelated bots go stale.
        # More robust: confirm stale_alerted flag persists on our bot)
        bdoc = mc[dbname].bots.find_one({"bot_id": bot_id})
        assert bdoc.get("stale_alerted") is True, "stale_alerted flag should be set after alert"

        # Re-arm: ingest a message and confirm stale_alerted clears
        ing = requests.post(f"{BASE_URL}/api/bots/ingest",
                            headers={"Authorization": f"Bearer {b['token']}", "Content-Type": "application/json"},
                            json={"text": "back online"}, timeout=15)
        assert ing.status_code == 200
        bdoc2 = mc[dbname].bots.find_one({"bot_id": bot_id})
        assert bdoc2.get("stale_alerted") is False, "stale_alerted should clear after ingest"

        mc.close()
