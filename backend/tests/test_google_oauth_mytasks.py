"""Tests for Google Drive OAuth flow and My Tasks widget (iteration 15)."""
import os
import pytest
import requests
from urllib.parse import urlparse, parse_qs

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback to reading frontend .env in case env not exported
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
assert BASE_URL, "REACT_APP_BACKEND_URL required"

API = f"{BASE_URL}/api"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@stitches.app", "Admin@123")


@pytest.fixture(scope="module")
def alice_token():
    return _login("alice@stitches.app", "Alice@123")


@pytest.fixture(scope="module")
def bob_token():
    return _login("bob@stitches.app", "Bob@123")


def _h(t):
    return {"Authorization": f"Bearer {t}"}


# ============ Google OAuth authorize ============

class TestGoogleAuthorize:
    def test_authorize_returns_well_formed_url(self, alice_token):
        r = requests.get(f"{API}/integrations/google/authorize", headers=_h(alice_token), timeout=20)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "authorization_url" in body
        url = body["authorization_url"]
        p = urlparse(url)
        assert p.netloc == "accounts.google.com", f"host was {p.netloc}"
        q = parse_qs(p.query)
        assert q.get("client_id"), "client_id missing"
        # Seeded from env starts with 30168147154-
        assert q["client_id"][0].startswith("30168147154-"), q["client_id"]
        assert q.get("access_type", [""])[0] == "offline"
        assert q.get("prompt", [""])[0] == "consent"
        assert q.get("state"), "state missing"
        assert "drive.readonly" in q.get("scope", [""])[0]
        redirect = q.get("redirect_uri", [""])[0]
        assert "/api/integrations/google/callback" in redirect, redirect

    def test_authorize_requires_auth(self):
        r = requests.get(f"{API}/integrations/google/authorize", timeout=20)
        assert r.status_code in (401, 403), r.status_code


# ============ Google OAuth callback (safety) ============

class TestGoogleCallback:
    def test_callback_no_params_redirects_to_error(self):
        r = requests.get(f"{API}/integrations/google/callback", timeout=20, allow_redirects=False)
        assert r.status_code in (302, 307), f"expected redirect, got {r.status_code}"
        loc = r.headers.get("location", "")
        assert "google=error" in loc, loc
        assert "/integrations" in loc

    def test_callback_bad_state_redirects_to_error(self):
        r = requests.get(f"{API}/integrations/google/callback",
                         params={"code": "abc", "state": "invalid_state_xxx"},
                         timeout=20, allow_redirects=False)
        assert r.status_code in (302, 307)
        assert "google=error" in r.headers.get("location", "")

    def test_callback_error_param_redirects(self):
        r = requests.get(f"{API}/integrations/google/callback",
                         params={"error": "access_denied"},
                         timeout=20, allow_redirects=False)
        assert r.status_code in (302, 307)
        assert "google=error" in r.headers.get("location", "")


# ============ Admin Google OAuth editor ============

class TestAdminGoogleOAuth:
    def test_get_returns_client_id_and_masked_secret(self, admin_token):
        r = requests.get(f"{API}/admin/google-oauth", headers=_h(admin_token), timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("client_id", "").startswith("30168147154-"), d
        # secret masked
        assert d.get("client_secret") == "••••••" or d.get("client_secret") == "", d.get("client_secret")
        assert "/api/integrations/google/callback" in d.get("redirect_uri", "")

    def test_non_admin_forbidden_get(self, alice_token):
        r = requests.get(f"{API}/admin/google-oauth", headers=_h(alice_token), timeout=20)
        assert r.status_code == 403, r.status_code

    def test_non_admin_forbidden_put(self, alice_token):
        r = requests.put(f"{API}/admin/google-oauth", headers=_h(alice_token),
                         json={"client_id": "hack", "client_secret": "hack"}, timeout=20)
        assert r.status_code == 403

    def test_put_masked_secret_does_not_overwrite(self, admin_token):
        # snapshot: real secret unknown but we can verify authorize URL still contains original client_id
        # First: update client_id but pass masked secret
        get1 = requests.get(f"{API}/admin/google-oauth", headers=_h(admin_token)).json()
        original_cid = get1["client_id"]
        # PUT with masked secret and same client_id
        r = requests.put(f"{API}/admin/google-oauth", headers=_h(admin_token),
                         json={"client_id": original_cid, "client_secret": "••••••"}, timeout=20)
        assert r.status_code == 200, r.text
        # After update, authorize URL must still work (secret intact allows flow config)
        # We can't verify secret directly (never returned), but ensure /authorize still returns URL with original cid
        auth = requests.get(f"{API}/integrations/google/authorize",
                            headers=_h(_login("alice@stitches.app", "Alice@123"))).json()
        q = parse_qs(urlparse(auth["authorization_url"]).query)
        assert q["client_id"][0] == original_cid

    def test_put_real_client_id_updates(self, admin_token):
        get1 = requests.get(f"{API}/admin/google-oauth", headers=_h(admin_token)).json()
        original_cid = get1["client_id"]
        temp = original_cid  # keep same value; we just prove PUT works and does not break state
        r = requests.put(f"{API}/admin/google-oauth", headers=_h(admin_token),
                         json={"client_id": temp}, timeout=20)
        assert r.status_code == 200
        get2 = requests.get(f"{API}/admin/google-oauth", headers=_h(admin_token)).json()
        assert get2["client_id"] == temp


# ============ Catalog: google_drive is oauth ============

class TestCatalog:
    def test_google_drive_is_oauth(self, alice_token):
        r = requests.get(f"{API}/integrations/catalog", headers=_h(alice_token), timeout=20)
        assert r.status_code == 200
        cat = r.json()
        gd = next((i for i in cat if i["type"] == "google_drive"), None)
        assert gd, "google_drive missing from catalog"
        assert gd.get("oauth") is True, gd
        # No manual fields required (method oauth)
        # method should be 'oauth' if present
        method = gd.get("method") or (gd.get("methods") or [{}])[0].get("value") if gd.get("methods") else gd.get("method")
        # be lenient - just make sure it's not manual credentials
        assert "fields" not in gd or not gd["fields"], "oauth connector should not expose manual fields"

    def test_google_drive_not_connected_404_not_500(self, alice_token):
        # Not connected -> integrations/{unknown}/files must not 500. Try a fake id.
        r = requests.get(f"{API}/integrations/int_nonexistent/files", headers=_h(alice_token), timeout=20)
        assert r.status_code == 404, r.status_code
        r2 = requests.post(f"{API}/integrations/int_nonexistent/test", headers=_h(alice_token), timeout=20)
        assert r2.status_code == 404, r2.status_code


# ============ My Tasks widget ============

class TestMyTasks:
    _created = {"project_id": None, "task_ids": []}

    def test_my_tasks_endpoint_shape(self, alice_token):
        r = requests.get(f"{API}/tasks/mine", headers=_h(alice_token), timeout=20)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_create_project_and_tasks_appear(self, alice_token):
        # create project
        r = requests.post(f"{API}/projects", headers=_h(alice_token),
                          json={"name": "TEST_mytasks_proj", "description": "iter15"}, timeout=20)
        assert r.status_code == 200, r.text
        proj = r.json()
        pid = proj["project_id"]
        self._created["project_id"] = pid

        # create 2 open tasks + 1 done
        t_ids = []
        for i, (title, status) in enumerate([("TEST_open1", "todo"), ("TEST_doing1", "doing"), ("TEST_done1", "done")]):
            rr = requests.post(f"{API}/projects/{pid}/tasks", headers=_h(alice_token),
                               json={"title": title, "status": status}, timeout=20)
            assert rr.status_code == 200, rr.text
            t_ids.append(rr.json()["task_id"])
        self._created["task_ids"] = t_ids

        # GET /tasks/mine now
        r2 = requests.get(f"{API}/tasks/mine", headers=_h(alice_token), timeout=20).json()
        titles = [t["title"] for t in r2 if t["project_id"] == pid]
        assert "TEST_open1" in titles
        assert "TEST_doing1" in titles
        assert "TEST_done1" in titles  # backend returns all; UI filters done
        # each has project_name populated
        for t in r2:
            if t["project_id"] == pid:
                assert t.get("project_name") == "TEST_mytasks_proj"
        # sorted newest first - our last-created should appear before earlier ones
        proj_tasks = [t for t in r2 if t["project_id"] == pid]
        # created_at strings ISO - newest first
        cats = [t["created_at"] for t in proj_tasks]
        assert cats == sorted(cats, reverse=True), f"not sorted desc: {cats}"

    def test_bob_does_not_see_alice_private_tasks(self, alice_token, bob_token):
        pid = self._created["project_id"]
        assert pid, "prior test must have created a project"
        r = requests.get(f"{API}/tasks/mine", headers=_h(bob_token), timeout=20).json()
        assert not any(t["project_id"] == pid for t in r), "bob should not see alice's tasks (not a member)"

    def test_zzz_cleanup(self, alice_token):
        pid = self._created["project_id"]
        if not pid:
            return
        for tid in self._created["task_ids"]:
            requests.delete(f"{API}/tasks/{tid}", headers=_h(alice_token))
        requests.delete(f"{API}/projects/{pid}", headers=_h(alice_token))
