"""Iteration 16 tests: task assignee/due, my_tasks widget backend, admin integrations catalog availability."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

CREDS = {
    "admin": ("admin@stitches.app", "Admin@123"),
    "alice": ("alice@stitches.app", "Alice@123"),
    "bob":   ("bob@stitches.app",   "Bob@123"),
    "demo":  ("demo@stitches.app",  "Demo@123"),
}


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def tokens():
    return {k: _login(*v) for k, v in CREDS.items()}


@pytest.fixture(scope="module")
def alice_project(tokens):
    """Create a project owned by alice, invite bob as member. Yield project_id + bob's user_id. Cleanup after."""
    tok = tokens["alice"]
    r = requests.post(f"{API}/projects", json={"name": "TEST_iter16_proj", "description": "assignee/due tests"}, headers=_h(tok), timeout=15)
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]

    # invite bob by email
    r2 = requests.post(f"{API}/projects/{pid}/invite", json={"email": "bob@stitches.app"}, headers=_h(tok), timeout=15)
    assert r2.status_code == 200, r2.text
    bob_uid = r2.json()["member"]["user_id"]

    # find alice's user_id from members list
    rm = requests.get(f"{API}/projects/{pid}/members", headers=_h(tok), timeout=15)
    assert rm.status_code == 200
    members = rm.json()
    alice_uid = next(m["user_id"] for m in members if m["email"] == "alice@stitches.app")

    yield {"project_id": pid, "alice_uid": alice_uid, "bob_uid": bob_uid}

    # cleanup
    try:
        requests.delete(f"{API}/projects/{pid}", headers=_h(tok), timeout=15)
    except Exception:
        pass


# ---------------- Task assignee + due date ----------------

class TestTaskAssigneeDue:

    def test_create_task_with_assignee_and_due(self, tokens, alice_project):
        tok = tokens["alice"]
        pid = alice_project["project_id"]
        bob = alice_project["bob_uid"]
        payload = {"title": "TEST_task_assigned", "assignee_id": bob, "due_date": "2026-02-15"}
        r = requests.post(f"{API}/projects/{pid}/tasks", json=payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["assignee_id"] == bob
        assert t["due_date"] == "2026-02-15"
        # list should include assignee_name
        r2 = requests.get(f"{API}/projects/{pid}/tasks", headers=_h(tok), timeout=15)
        assert r2.status_code == 200
        found = [x for x in r2.json() if x["task_id"] == t["task_id"]]
        assert found, "task not present in list"
        assert (found[0].get("assignee_name") or "").startswith("Bob")

    def test_put_task_updates_assignee_and_due_persistent(self, tokens, alice_project):
        tok = tokens["alice"]
        pid = alice_project["project_id"]
        # create empty
        r = requests.post(f"{API}/projects/{pid}/tasks", json={"title": "TEST_task_update"}, headers=_h(tok), timeout=15)
        tid = r.json()["task_id"]
        # update
        r2 = requests.put(f"{API}/tasks/{tid}", json={"assignee_id": alice_project["alice_uid"], "due_date": "2026-03-01"}, headers=_h(tok), timeout=15)
        assert r2.status_code == 200, r2.text
        # reload via list, verify persistence + enrichment
        r3 = requests.get(f"{API}/projects/{pid}/tasks", headers=_h(tok), timeout=15)
        t = next(x for x in r3.json() if x["task_id"] == tid)
        assert t["assignee_id"] == alice_project["alice_uid"]
        assert t["due_date"] == "2026-03-01"
        assert (t["assignee_name"] or "").startswith("Alice")

    def test_non_member_cannot_update_task(self, tokens, alice_project):
        """demo is NOT a member — should get 403 when updating assignee/due."""
        alice_tok = tokens["alice"]
        pid = alice_project["project_id"]
        r = requests.post(f"{API}/projects/{pid}/tasks", json={"title": "TEST_task_403"}, headers=_h(alice_tok), timeout=15)
        tid = r.json()["task_id"]

        demo_tok = tokens["demo"]
        r2 = requests.put(f"{API}/tasks/{tid}", json={"assignee_id": alice_project["bob_uid"], "due_date": "2026-04-01"}, headers=_h(demo_tok), timeout=15)
        assert r2.status_code == 403, f"expected 403, got {r2.status_code} {r2.text}"


# ---------------- My tasks widget ----------------

class TestMyTasks:

    def test_mytasks_returns_project_name_and_assignee_name(self, tokens, alice_project):
        tok = tokens["alice"]
        pid = alice_project["project_id"]
        # create an open + a done task
        r1 = requests.post(f"{API}/projects/{pid}/tasks", json={"title": "TEST_mine_open", "assignee_id": alice_project["bob_uid"], "due_date": "2026-05-01", "status": "todo"}, headers=_h(tok), timeout=15)
        r2 = requests.post(f"{API}/projects/{pid}/tasks", json={"title": "TEST_mine_done", "status": "done"}, headers=_h(tok), timeout=15)
        assert r1.status_code == 200 and r2.status_code == 200

        # Alice's /tasks/mine should include both (backend returns all statuses; UI filters done)
        r = requests.get(f"{API}/tasks/mine", headers=_h(tok), timeout=15)
        assert r.status_code == 200
        items = r.json()
        titles = {i["title"] for i in items}
        assert "TEST_mine_open" in titles

        # find open one and check enrichment
        openi = next(i for i in items if i["title"] == "TEST_mine_open")
        assert openi.get("project_name") == "TEST_iter16_proj"
        assert (openi.get("assignee_name") or "").startswith("Bob")
        assert openi.get("due_date") == "2026-05-01"

    def test_mytasks_membership_scoped(self, tokens, alice_project):
        """demo is not a member — should not see alice's project tasks."""
        r = requests.get(f"{API}/tasks/mine", headers=_h(tokens["demo"]), timeout=15)
        assert r.status_code == 200
        for t in r.json():
            assert t["project_id"] != alice_project["project_id"], "demo should not see alice's tasks"


# ---------------- Admin integrations catalog availability ----------------

class TestAdminIntegrations:
    """Verify the same catalog+wizard endpoints admin uses in the Admin > Integrations tab work fine."""

    def test_catalog_available_to_admin(self, tokens):
        r = requests.get(f"{API}/integrations/catalog", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 200
        cat = r.json()
        types = {c["type"] for c in cat}
        # 8 connectors expected (n8n, aws_s3, dropbox, google_drive, llm, mcp, email, custom)
        expected = {"n8n", "aws_s3", "dropbox", "google_drive", "llm", "mcp", "email", "custom"}
        missing = expected - types
        assert not missing, f"missing connectors in catalog: {missing}"

    def test_admin_can_connect_custom_and_it_appears_in_admin_list(self, tokens):
        tok = tokens["admin"]
        payload = {
            "type": "custom",
            "name": "TEST_admin_custom_iter16",
            "auth_method": "basic",
            "config": {"base_url": "https://httpbin.org/basic-auth/user/pass", "username": "user", "password": "pass"},
        }
        r = requests.post(f"{API}/integrations", json=payload, headers=_h(tok), timeout=15)
        assert r.status_code == 200, r.text
        iid = r.json().get("integration_id")
        assert iid

        # admin list should include it
        r2 = requests.get(f"{API}/admin/integrations", headers=_h(tok), timeout=15)
        assert r2.status_code == 200
        names = {x["name"] for x in r2.json()}
        assert "TEST_admin_custom_iter16" in names

        # user's own list also shows it
        r3 = requests.get(f"{API}/integrations", headers=_h(tok), timeout=15)
        assert r3.status_code == 200
        assert any(x["integration_id"] == iid for x in r3.json())

        # cleanup
        requests.delete(f"{API}/integrations/{iid}", headers=_h(tok), timeout=15)

    def test_admin_google_oauth_endpoint_still_works(self, tokens):
        r = requests.get(f"{API}/admin/google-oauth", headers=_h(tokens["admin"]), timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "client_id" in data and "redirect_uri" in data
        # secret should be masked
        assert data.get("client_secret") in (None, "", "••••••") or "••" in (data.get("client_secret") or "")


# ---------------- Regression sanity ----------------

class TestRegressionQuick:

    def test_all_seed_logins(self):
        for _, (e, p) in CREDS.items():
            r = requests.post(f"{API}/auth/login", json={"email": e, "password": p}, timeout=15)
            assert r.status_code == 200, f"{e} login failed: {r.status_code}"

    def test_google_authorize_still_well_formed(self, tokens):
        r = requests.get(f"{API}/integrations/google/authorize", headers=_h(tokens["alice"]), timeout=15)
        assert r.status_code == 200
        url = r.json().get("authorization_url", "")
        assert "accounts.google.com" in url
        assert "drive.readonly" in url
        assert "access_type=offline" in url

    def test_projects_list_works(self, tokens):
        r = requests.get(f"{API}/projects", headers=_h(tokens["alice"]), timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- Cleanup fallback ----------------

class TestZzzCleanup:
    def test_cleanup_test_data(self, tokens):
        """Remove any stray TEST_ projects created by alice."""
        tok = tokens["alice"]
        r = requests.get(f"{API}/projects", headers=_h(tok), timeout=15)
        for p in r.json():
            if p.get("name", "").startswith("TEST_iter16"):
                requests.delete(f"{API}/projects/{p['project_id']}", headers=_h(tok), timeout=15)
        # remove any stray TEST_admin_custom_iter16
        admin = tokens["admin"]
        r2 = requests.get(f"{API}/integrations", headers=_h(admin), timeout=15)
        for it in r2.json():
            if it.get("name", "").startswith("TEST_admin_custom_iter16"):
                requests.delete(f"{API}/integrations/{it['integration_id']}", headers=_h(admin), timeout=15)
