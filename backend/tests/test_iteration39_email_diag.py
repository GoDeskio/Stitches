"""
Iteration 39: verify email diagnostics fix + regression sanity for iteration 38 features.
Focus:
  - /api/admin/test-email detail LEADS with the active provider label (e.g. "Mailgun (active) failed:...")
  - /api/admin/setup-status email item detail reflects the ACTIVE selected provider (e.g. "Mailgun (active)")
"""
import os
import requests
from pathlib import Path
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL")
            or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}
DEMO = {"email": "demo@stitches.app", "password": "Demo@123"}
ALICE = {"email": "alice@stitches.app", "password": "Alice@123"}
BOB = {"email": "bob@stitches.app", "password": "Bob@123"}


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=20)
    assert r.status_code == 200, f"Login failed for {creds['email']}: {r.status_code} {r.text[:300]}"
    tok = r.json().get("token")
    assert tok, f"No token in login response for {creds['email']}"
    return tok


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------------------- Auth & who-am-i ----------------------
class TestAuth:
    def test_admin_login(self):
        tok = _login(ADMIN)
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(tok), timeout=15)
        assert me.status_code == 200
        assert me.json().get("email") == ADMIN["email"]
        assert me.json().get("role") == "admin"

    def test_demo_login(self):
        tok = _login(DEMO)
        me = requests.get(f"{BASE_URL}/api/auth/me", headers=_h(tok), timeout=15)
        assert me.status_code == 200
        assert me.json().get("email") == DEMO["email"]

    def test_alice_bob_login(self):
        for creds in (ALICE, BOB):
            _login(creds)


# ---------------------- Email diagnostics (primary focus) ----------------------
class TestEmailDiagnostics:
    """Configure provider=mailgun with an invalid key, then verify diagnostics."""

    @classmethod
    def setup_class(cls):
        cls.admin_tok = _login(ADMIN)
        # Snapshot current provider config so we restore after the class.
        r = requests.get(f"{BASE_URL}/api/admin/email-provider", headers=_h(cls.admin_tok), timeout=15)
        cls.orig_provider = r.json() if r.status_code == 200 else None
        r2 = requests.get(f"{BASE_URL}/api/admin/mailgun-config", headers=_h(cls.admin_tok), timeout=15)
        cls.orig_mailgun = r2.json() if r2.status_code == 200 else None

        # Set provider=mailgun
        rp = requests.put(f"{BASE_URL}/api/admin/email-provider",
                          headers=_h(cls.admin_tok),
                          json={"provider": "mailgun",
                                "sender": (cls.orig_provider or {}).get("sender") or "admin@stitches.app",
                                "resend_fallback": False},
                          timeout=15)
        assert rp.status_code in (200, 201), f"Could not set provider=mailgun: {rp.status_code} {rp.text[:200]}"

        # Set mailgun creds to a syntactically-valid but invalid key
        rm = requests.put(f"{BASE_URL}/api/admin/mailgun-config",
                          headers=_h(cls.admin_tok),
                          json={"domain": "invalid.stitches.test",
                                "api_key": "key-TEST_iter39_invalid_diag_key",
                                "region": "us",
                                "sender": "admin@invalid.stitches.test"},
                          timeout=15)
        assert rm.status_code in (200, 201), f"Could not configure invalid Mailgun: {rm.status_code} {rm.text[:200]}"

    @classmethod
    def teardown_class(cls):
        # Best-effort restore
        try:
            if cls.orig_provider:
                requests.put(f"{BASE_URL}/api/admin/email-provider",
                             headers=_h(cls.admin_tok),
                             json={k: cls.orig_provider.get(k) for k in ("provider", "sender", "resend_fallback")
                                   if cls.orig_provider.get(k) is not None},
                             timeout=15)
        except Exception:
            pass

    def test_setup_status_shows_active_mailgun(self):
        r = requests.get(f"{BASE_URL}/api/admin/setup-status", headers=_h(self.admin_tok), timeout=15)
        assert r.status_code == 200, r.text[:300]
        items = r.json().get("items", [])
        email_item = next((i for i in items if i.get("key") == "email"), None)
        assert email_item, f"No email item in setup-status: {items}"
        detail = email_item.get("detail", "")
        assert "Mailgun" in detail and "active" in detail.lower(), (
            f"Expected email detail to include 'Mailgun (active)', got: {detail!r}"
        )

    def test_test_email_detail_leads_with_active_provider(self):
        r = requests.post(f"{BASE_URL}/api/admin/test-email",
                          headers=_h(self.admin_tok),
                          json={"to": "diag_test@stitches.app"},
                          timeout=60)
        assert r.status_code == 200, r.text[:400]
        body = r.json()
        # Expected to FAIL (invalid Mailgun key) per the review note
        assert body.get("ok") is False, f"Expected ok=False with invalid Mailgun key, got: {body}"
        detail = body.get("detail", "")
        # Must LEAD with Mailgun (active) failed: ...
        assert detail.startswith("Mailgun (active) failed:"), (
            f"Expected detail to start with 'Mailgun (active) failed:' - got: {detail!r}"
        )
        # And any fallback (e.g. SMTP) if listed, must come AFTER the primary
        if " | " in detail:
            head, *_rest = detail.split(" | ")
            assert head.startswith("Mailgun (active) failed:"), (
                f"Primary provider must be first segment. Got: {detail!r}"
            )


# ---------------------- Regression: super-admin gating on storage / DB ----------------------
class TestSuperAdminGating:
    def test_admin_can_access_db_and_storage_overview(self):
        tok = _login(ADMIN)
        r1 = requests.get(f"{BASE_URL}/api/admin/db/overview", headers=_h(tok), timeout=20)
        assert r1.status_code == 200, r1.text[:200]
        assert "collections" in r1.json() or "counts" in r1.json() or isinstance(r1.json(), dict)
        r2 = requests.get(f"{BASE_URL}/api/admin/storage/overview", headers=_h(tok), timeout=20)
        assert r2.status_code == 200, r2.text[:200]

    def test_demo_blocked(self):
        tok = _login(DEMO)
        r1 = requests.get(f"{BASE_URL}/api/admin/db/overview", headers=_h(tok), timeout=15)
        assert r1.status_code in (401, 403), f"Demo should be blocked, got {r1.status_code}"
        r2 = requests.get(f"{BASE_URL}/api/admin/storage/overview", headers=_h(tok), timeout=15)
        assert r2.status_code in (401, 403), f"Demo should be blocked, got {r2.status_code}"


# ---------------------- Regression: meetings + RTC ----------------------
class TestMeetings:
    def test_rtc_config_has_ice_servers(self):
        tok = _login(DEMO)
        r = requests.get(f"{BASE_URL}/api/rtc/config", headers=_h(tok), timeout=15)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert "iceServers" in body and isinstance(body["iceServers"], list) and len(body["iceServers"]) > 0

    def test_sfu_token_returns_400_when_disabled(self):
        tok = _login(DEMO)
        # Create an instant meeting to get a room
        cr = requests.post(f"{BASE_URL}/api/meetings", headers=_h(tok), json={"name": "TEST_iter39_mtg"}, timeout=20)
        assert cr.status_code in (200, 201), cr.text[:300]
        room = cr.json().get("room_id") or cr.json().get("room") or cr.json().get("id")
        r = requests.post(f"{BASE_URL}/api/rtc/sfu-token",
                          headers=_h(tok),
                          json={"room": room or "test-room"},
                          timeout=15)
        assert r.status_code == 400, f"Expected 400 while LiveKit disabled, got {r.status_code}: {r.text[:200]}"


# ---------------------- Regression: bots ingest still works ----------------------
class TestBotsRegression:
    _created_bot_id = None
    _token = None

    def test_create_bot_and_ingest(self):
        tok = _login(ADMIN)
        # find a channel to post to
        ws = requests.get(f"{BASE_URL}/api/workspaces", headers=_h(tok), timeout=15)
        assert ws.status_code == 200
        wss = ws.json()
        assert wss, "No workspaces returned"
        ws_id = wss[0].get("workspace_id") or wss[0].get("id")
        ch = requests.get(f"{BASE_URL}/api/workspaces/{ws_id}/channels", headers=_h(tok), timeout=15)
        assert ch.status_code == 200
        chans = ch.json()
        assert chans, "No channels"
        ch_id = chans[0].get("channel_id") or chans[0].get("id")

        cr = requests.post(f"{BASE_URL}/api/bots",
                           headers=_h(tok),
                           json={"name": "TEST_iter39_bot", "target_channel_id": ch_id},
                           timeout=15)
        assert cr.status_code in (200, 201), cr.text[:300]
        body = cr.json()
        TestBotsRegression._created_bot_id = body.get("bot_id") or body.get("id")
        TestBotsRegression._token = body.get("token")
        assert TestBotsRegression._token and TestBotsRegression._token.startswith("stbot_")

        ing = requests.post(f"{BASE_URL}/api/bots/ingest",
                            headers={"Authorization": f"Bearer {TestBotsRegression._token}",
                                     "Content-Type": "application/json"},
                            json={"text": "TEST_iter39 bot hello"},
                            timeout=15)
        assert ing.status_code == 200, ing.text[:300]
        assert ing.json().get("message_id")

    def test_cleanup_bot(self):
        if not TestBotsRegression._created_bot_id:
            return
        tok = _login(ADMIN)
        requests.delete(f"{BASE_URL}/api/bots/{TestBotsRegression._created_bot_id}",
                        headers=_h(tok), timeout=15)
