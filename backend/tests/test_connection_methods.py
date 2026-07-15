"""Iteration 13: multi-method connection wizard (email, custom, n8n basic-auth) tests."""
import os
import uuid
import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"

ALICE = {"email": "alice@stitches.app", "password": "Alice@123"}
BOB = {"email": "bob@stitches.app", "password": "Bob@123"}
ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}
DEMO = {"email": "demo@stitches.app", "password": "Demo@123"}


def login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, f"{creds['email']}: {r.status_code} {r.text}"
    return r.json()["token"]


def auth(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture(scope="module")
def alice_token():
    return login(ALICE)


created_ids = []


@pytest.fixture(scope="module", autouse=True)
def cleanup(alice_token):
    yield
    for iid in created_ids:
        try:
            requests.delete(f"{API}/integrations/{iid}", headers=auth(alice_token))
        except Exception:
            pass


# ---------- SEED LOGINS ----------
class TestSeedLogins:
    def test_all_four_logins(self):
        for c in (ADMIN, DEMO, ALICE, BOB):
            r = requests.post(f"{API}/auth/login", json=c, timeout=15)
            assert r.status_code == 200, f"{c['email']} login failed"
            assert "token" in r.json()


# ---------- CATALOG ----------
class TestCatalog:
    def test_catalog_has_eight_connectors_with_methods(self, alice_token):
        r = requests.get(f"{API}/integrations/catalog", headers=auth(alice_token))
        assert r.status_code == 200
        cat = r.json()
        types = {c["type"] for c in cat}
        expected = {"n8n", "email", "custom", "aws_s3", "dropbox", "google_drive", "llm", "mcp"}
        assert expected.issubset(types), f"missing: {expected - types}"
        assert len(cat) == 8

        by_type = {c["type"]: c for c in cat}
        # n8n methods url + basic
        n8n_methods = [m["id"] for m in by_type["n8n"]["methods"]]
        assert set(n8n_methods) == {"url", "basic"}
        # custom methods basic + api_key
        custom_methods = [m["id"] for m in by_type["custom"]["methods"]]
        assert set(custom_methods) == {"basic", "api_key"}
        # email methods
        email_methods = [m["id"] for m in by_type["email"]["methods"]]
        assert set(email_methods) == {"password"}

        # each method must have fields with label; check help/placeholder metadata exists somewhere
        for c in cat:
            for m in c["methods"]:
                assert "label" in m
                assert isinstance(m["fields"], list) and len(m["fields"]) > 0
                for f in m["fields"]:
                    assert "label" in f and "key" in f

        # sanity: some fields have help / placeholder
        assert any(f.get("help") for m in by_type["email"]["methods"] for f in m["fields"])
        assert any(f.get("placeholder") for m in by_type["custom"]["methods"] for f in m["fields"])


# ---------- CUSTOM APP basic-auth ----------
class TestCustomApp:
    def test_connect_custom_basic_and_masking(self, alice_token):
        payload = {
            "type": "custom",
            "name": "TEST_custom_basic",
            "auth_method": "basic",
            "config": {"base_url": "https://httpbin.org/basic-auth/user/pass",
                       "username": "user", "password": "pass"}
        }
        r = requests.post(f"{API}/integrations", json=payload, headers=auth(alice_token))
        assert r.status_code == 200, r.text
        iid = r.json()["integration_id"]
        created_ids.append(iid)

        # list should mask password but not base_url/username
        r2 = requests.get(f"{API}/integrations", headers=auth(alice_token))
        assert r2.status_code == 200
        item = next(it for it in r2.json() if it["integration_id"] == iid)
        assert "config" not in item
        cm = item["config_masked"]
        assert cm["password"] == "••••••"
        assert cm["base_url"] == "https://httpbin.org/basic-auth/user/pass"
        assert cm["username"] == "user"
        assert item.get("auth_method") == "basic"

        # test action
        rt = requests.post(f"{API}/integrations/{iid}/test", headers=auth(alice_token), timeout=30)
        assert rt.status_code == 200, rt.text
        d = rt.json()
        assert d.get("ok") is True, f"expected ok:true, got {d}"
        assert "200" in str(d.get("message", ""))

    def test_custom_api_key_method(self, alice_token):
        r = requests.post(f"{API}/integrations", json={
            "type": "custom", "name": "TEST_custom_apikey", "auth_method": "api_key",
            "config": {"base_url": "https://httpbin.org/bearer", "api_key": "TESTTOKEN"}
        }, headers=auth(alice_token))
        assert r.status_code == 200
        iid = r.json()["integration_id"]
        created_ids.append(iid)
        rt = requests.post(f"{API}/integrations/{iid}/test", headers=auth(alice_token), timeout=30)
        assert rt.status_code == 200
        # httpbin.org/bearer accepts any bearer → ok:true
        assert "ok" in rt.json()


# ---------- EMAIL ----------
class TestEmail:
    def test_email_connect_and_test_graceful(self, alice_token):
        r = requests.post(f"{API}/integrations", json={
            "type": "email", "name": "TEST_email", "auth_method": "password",
            "config": {"imap_host": "imap.gmail.com", "email": "nobody@example.com",
                       "password": "not-a-real-pw"}
        }, headers=auth(alice_token))
        assert r.status_code == 200, r.text
        iid = r.json()["integration_id"]
        created_ids.append(iid)

        # Masking regression: password must be masked
        r2 = requests.get(f"{API}/integrations", headers=auth(alice_token))
        item = next(it for it in r2.json() if it["integration_id"] == iid)
        assert item["config_masked"]["password"] == "••••••"
        assert item["config_masked"]["email"] == "nobody@example.com"

        # Test should return ok:false gracefully, NOT 500
        rt = requests.post(f"{API}/integrations/{iid}/test", headers=auth(alice_token), timeout=45)
        assert rt.status_code == 200, f"Email test crashed: {rt.status_code} {rt.text}"
        d = rt.json()
        assert d.get("ok") is False
        assert "message" in d


# ---------- N8N ----------
class TestN8N:
    def test_n8n_basic_auth_run(self, alice_token):
        r = requests.post(f"{API}/integrations", json={
            "type": "n8n", "name": "TEST_n8n_basic", "auth_method": "basic",
            "config": {"webhook_url": "https://httpbin.org/post",
                       "basic_user": "user", "basic_pass": "pass"}
        }, headers=auth(alice_token))
        assert r.status_code == 200
        iid = r.json()["integration_id"]
        created_ids.append(iid)

        # basic_pass must be masked
        r2 = requests.get(f"{API}/integrations", headers=auth(alice_token))
        item = next(it for it in r2.json() if it["integration_id"] == iid)
        assert item["config_masked"]["basic_pass"] == "••••••"
        assert item["config_masked"]["basic_user"] == "user"

        rr = requests.post(f"{API}/integrations/{iid}/run", json={"payload": {"x": 1}},
                           headers=auth(alice_token), timeout=45)
        assert rr.status_code == 200, rr.text
        d = rr.json()
        assert d.get("status_code") == 200
        assert d.get("ok") is True
        # httpbin echoes auth header
        assert "Basic" in d.get("response", "") or "authorization" in d.get("response", "").lower()

    def test_n8n_url_only_still_works(self, alice_token):
        r = requests.post(f"{API}/integrations", json={
            "type": "n8n", "name": "TEST_n8n_url", "auth_method": "url",
            "config": {"webhook_url": "https://httpbin.org/post"}
        }, headers=auth(alice_token))
        assert r.status_code == 200
        iid = r.json()["integration_id"]
        created_ids.append(iid)
        rr = requests.post(f"{API}/integrations/{iid}/run", json={"payload": {}},
                           headers=auth(alice_token), timeout=45)
        assert rr.status_code == 200
        assert rr.json().get("status_code") == 200


# ---------- ENCRYPTION regression via direct Mongo ----------
class TestEncryptionAtRest:
    def test_secret_fields_encrypted_in_db(self, alice_token):
        # Create a custom integration then read raw doc from mongo
        r = requests.post(f"{API}/integrations", json={
            "type": "custom", "name": "TEST_enc_check", "auth_method": "basic",
            "config": {"base_url": "https://example.com", "username": "u", "password": "supersecret123"}
        }, headers=auth(alice_token))
        assert r.status_code == 200
        iid = r.json()["integration_id"]
        created_ids.append(iid)

        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")

        async def _check():
            client = AsyncIOMotorClient(mongo_url)
            doc = await client[db_name].integrations.find_one({"integration_id": iid})
            client.close()
            return doc

        doc = asyncio.get_event_loop().run_until_complete(_check())
        assert doc is not None
        raw_pw = doc["config"]["password"]
        assert isinstance(raw_pw, str) and raw_pw.startswith("gAAAAA"), f"password not encrypted: {raw_pw[:20]}"
        # All string values are Fernet-encrypted at rest (implementation encrypts all strings)
        assert doc["config"]["username"].startswith("gAAAAA")
        assert doc.get("auth_method") == "basic"


# ---------- REGRESSION: existing single-method connectors ----------
class TestRegressionConnectors:
    def test_aws_s3_test_graceful(self, alice_token):
        r = requests.post(f"{API}/integrations", json={
            "type": "aws_s3", "name": "TEST_s3_reg",
            "config": {"access_key": "AKIAFAKE", "secret_key": "s", "region": "us-east-1",
                       "bucket": "nonexistent-xyz-abc-123"}
        }, headers=auth(alice_token))
        assert r.status_code == 200
        iid = r.json()["integration_id"]; created_ids.append(iid)
        rt = requests.post(f"{API}/integrations/{iid}/test", headers=auth(alice_token), timeout=30)
        assert rt.status_code == 200
        assert rt.json().get("ok") is False

    def test_dropbox_test_graceful(self, alice_token):
        r = requests.post(f"{API}/integrations", json={
            "type": "dropbox", "name": "TEST_dbx_reg", "config": {"access_token": "fake"}
        }, headers=auth(alice_token))
        iid = r.json()["integration_id"]; created_ids.append(iid)
        rt = requests.post(f"{API}/integrations/{iid}/test", headers=auth(alice_token), timeout=30)
        assert rt.status_code == 200
        assert rt.json().get("ok") is False

    def test_llm_test_ok(self, alice_token):
        r = requests.post(f"{API}/integrations", json={
            "type": "llm", "name": "TEST_llm_reg",
            "config": {"provider": "openai", "api_key": "sk-fake", "model": "gpt-4o"}
        }, headers=auth(alice_token))
        iid = r.json()["integration_id"]; created_ids.append(iid)
        rt = requests.post(f"{API}/integrations/{iid}/test", headers=auth(alice_token))
        assert rt.status_code == 200
        assert rt.json().get("ok") is True

    def test_mcp_test_graceful(self, alice_token):
        r = requests.post(f"{API}/integrations", json={
            "type": "mcp", "name": "TEST_mcp_reg",
            "config": {"server_url": "https://httpbin.org/status/200", "token": "x"}
        }, headers=auth(alice_token))
        iid = r.json()["integration_id"]; created_ids.append(iid)
        rt = requests.post(f"{API}/integrations/{iid}/test", headers=auth(alice_token), timeout=30)
        assert rt.status_code == 200
        assert "ok" in rt.json()
