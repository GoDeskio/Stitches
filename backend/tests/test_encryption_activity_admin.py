"""Tests for encryption at rest, user activity log isolation, admin search-by-user, regression."""
import os
import time
import uuid
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
API = f"{BASE}/api"

CREDS = {
    "admin": ("admin@stitches.app", "Admin@123"),
    "demo": ("demo@stitches.app", "Demo@123"),
    "alice": ("alice@stitches.app", "Alice@123"),
    "bob": ("bob@stitches.app", "Bob@123"),
}


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"], r.json()["user"]


def _h(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(*v) for k, v in CREDS.items()}


# ---------------- REGRESSION: all four users can log in ----------------
class TestLoginRegression:
    @pytest.mark.parametrize("who", list(CREDS.keys()))
    def test_login_ok(self, who):
        tok, u = _login(*CREDS[who])
        assert isinstance(tok, str) and len(tok) > 10
        assert u["email"] == CREDS[who][0]


# ---------------- Integrations: catalog still has 6 ----------------
class TestIntegrationCatalog:
    def test_catalog_six(self, tokens):
        t, _ = tokens["demo"]
        r = requests.get(f"{API}/integrations/catalog", headers=_h(t))
        assert r.status_code == 200
        cat = r.json()
        assert len(cat) == 6, f"expected 6 connectors, got {len(cat)}: {[c['type'] for c in cat]}"


# ---------------- ENCRYPTION: masking + no plaintext leak + at-rest ----------------
class TestEncryption:
    created_ids = []

    def test_create_masks_and_no_config_returned(self, tokens):
        t, _ = tokens["demo"]
        payload = {
            "type": "n8n",
            "name": f"TEST_enc_{uuid.uuid4().hex[:6]}",
            "config": {"webhook_url": "https://httpbin.org/post", "token": "PLAINTEXT_TOKEN_ABC123"},
        }
        r = requests.post(f"{API}/integrations", json=payload, headers=_h(t))
        assert r.status_code == 200, r.text
        body = r.json()
        # No raw config in create response
        assert "config" not in body, f"raw config leaked in create response: {body}"
        assert "PLAINTEXT_TOKEN_ABC123" not in r.text
        TestEncryption.created_ids.append(body["integration_id"])

    def test_list_returns_masked_and_no_raw_config(self, tokens):
        t, _ = tokens["demo"]
        r = requests.get(f"{API}/integrations", headers=_h(t))
        assert r.status_code == 200
        items = r.json()
        assert len(items) > 0
        for it in items:
            assert "config" not in it, "raw config must not be present in list response"
            assert "config_masked" in it
            for k, v in it["config_masked"].items():
                if k in {"api_key", "token", "access_key", "secret_key", "access_token", "password"} and v:
                    assert v == "••••••", f"secret field {k} not masked: {v}"
        # ensure no plaintext of our token leaked
        assert "PLAINTEXT_TOKEN_ABC123" not in r.text

    def test_at_rest_encrypted_in_mongo(self, tokens):
        # Direct DB inspection
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "test_database")
        # Backend env may differ; try to load from backend/.env
        try:
            with open("/app/backend/.env") as f:
                for line in f:
                    if line.startswith("MONGO_URL="):
                        mongo_url = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if line.startswith("DB_NAME="):
                        db_name = line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

        async def _check():
            cli = AsyncIOMotorClient(mongo_url)
            db = cli[db_name]
            iid = TestEncryption.created_ids[0]
            doc = await db.integrations.find_one({"integration_id": iid})
            assert doc is not None
            cfg = doc.get("config", {})
            # token must NOT equal plaintext, must be Fernet-encrypted (gAAAAA prefix)
            tok_val = cfg.get("token", "")
            assert tok_val != "PLAINTEXT_TOKEN_ABC123", "plaintext token found in Mongo!"
            assert isinstance(tok_val, str) and tok_val.startswith("gAAAAA"), f"expected Fernet ciphertext, got: {tok_val[:20]}"
            cli.close()

        asyncio.run(_check())

    def test_n8n_run_still_works_after_encryption(self, tokens):
        t, _ = tokens["demo"]
        iid = TestEncryption.created_ids[0]
        r = requests.post(f"{API}/integrations/{iid}/run",
                          json={"action": "run", "params": {"hello": "world"}}, headers=_h(t), timeout=30)
        assert r.status_code == 200, f"n8n run failed after encryption: {r.status_code} {r.text}"
        data = r.json()
        # Should include the httpbin echo -> status 200
        assert data.get("status") == 200 or data.get("ok") is True, f"unexpected run response: {data}"

    def test_storage_bad_creds_graceful(self, tokens):
        t, _ = tokens["demo"]
        payload = {
            "type": "s3",
            "name": f"TEST_enc_s3_{uuid.uuid4().hex[:5]}",
            "config": {"provider": "aws", "region": "us-east-1", "bucket": "does-not-exist-xyz",
                       "access_key": "AKIAFAKE", "secret_key": "SECRETFAKE"},
        }
        r = requests.post(f"{API}/integrations", json=payload, headers=_h(t))
        assert r.status_code == 200, r.text
        iid = r.json()["integration_id"]
        TestEncryption.created_ids.append(iid)
        # No plaintext in create response
        assert "SECRETFAKE" not in r.text
        r2 = requests.get(f"{API}/integrations/{iid}/files", headers=_h(t), timeout=30)
        assert r2.status_code == 400, f"expected 400 graceful, got {r2.status_code}: {r2.text}"

    def test_cleanup(self, tokens):
        t, _ = tokens["demo"]
        for iid in TestEncryption.created_ids:
            requests.delete(f"{API}/integrations/{iid}", headers=_h(t))


# ---------------- USER ACTIVITY LOG ----------------
class TestActivity:
    def test_me_returns_own_only(self, tokens):
        t_alice, u_alice = tokens["alice"]
        t_bob, u_bob = tokens["bob"]

        # Alice performs a unique action -> create a note
        note_title = f"TEST_activity_{uuid.uuid4().hex[:6]}"
        r = requests.post(f"{API}/notes", json={"title": note_title, "body": "x"}, headers=_h(t_alice))
        assert r.status_code == 200, r.text
        note_id = r.json().get("note_id")

        time.sleep(0.5)

        r = requests.get(f"{API}/activity/me", headers=_h(t_alice))
        assert r.status_code == 200
        alice_logs = r.json()
        assert isinstance(alice_logs, list)
        assert len(alice_logs) > 0
        # All entries must belong to Alice
        for e in alice_logs:
            assert e.get("user_id") == u_alice["user_id"], f"Alice's activity contains other user: {e}"

        # Bob should not see Alice's entries
        r = requests.get(f"{API}/activity/me", headers=_h(t_bob))
        assert r.status_code == 200
        bob_logs = r.json()
        for e in bob_logs:
            assert e.get("user_id") == u_bob["user_id"], f"Bob's activity contains other user: {e}"

        # Cleanup
        if note_id:
            requests.delete(f"{API}/notes/{note_id}", headers=_h(t_alice))


# ---------------- ADMIN search-by-user (uses existing /admin/users + /admin/users/{id}/activity) ----------------
class TestAdminUserActivity:
    def test_admin_lists_users_and_pulls_activity(self, tokens):
        t_admin, _ = tokens["admin"]
        r = requests.get(f"{API}/admin/users", headers=_h(t_admin))
        assert r.status_code == 200
        users = r.json()
        assert isinstance(users, list) and len(users) >= 4
        # find alice
        alice = next((u for u in users if u["email"] == "alice@stitches.app"), None)
        assert alice, "alice not in admin users list"
        r = requests.get(f"{API}/admin/users/{alice['user_id']}/activity", headers=_h(t_admin))
        assert r.status_code == 200
        logs = r.json()
        assert isinstance(logs, list)
        for e in logs:
            assert e.get("user_id") == alice["user_id"]

    def test_non_admin_cannot_pull_others_activity(self, tokens):
        t_demo, _ = tokens["demo"]
        t_admin, _ = tokens["admin"]
        users = requests.get(f"{API}/admin/users", headers=_h(t_admin)).json()
        alice = next(u for u in users if u["email"] == "alice@stitches.app")
        r = requests.get(f"{API}/admin/users/{alice['user_id']}/activity", headers=_h(t_demo))
        assert r.status_code in (401, 403), f"non-admin got {r.status_code}"
