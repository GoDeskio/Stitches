import os
import requests
import pytest
from datetime import date

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')
if not BASE_URL:
    # Fallback: read frontend/.env
    with open('/app/frontend/.env') as f:
        for line in f:
            if line.startswith('REACT_APP_BACKEND_URL'):
                BASE_URL = line.split('=', 1)[1].strip().rstrip('/')

CREDS = {
    "admin": ("admin@stitches.app", "Admin@123"),
    "demo": ("demo@stitches.app", "Demo@123"),
    "alice": ("alice@stitches.app", "Alice@123"),
    "bob": ("bob@stitches.app", "Bob@123"),
}


def login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=15)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    data = r.json()
    assert "token" in data
    return data["token"], data["user"]


@pytest.fixture(scope="module")
def tokens():
    out = {}
    for k, (e, p) in CREDS.items():
        tok, u = login(e, p)
        out[k] = {"token": tok, "user": u}
    return out


def H(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---- REGRESSION ----
def test_all_four_logins(tokens):
    assert set(tokens.keys()) == {"admin", "demo", "alice", "bob"}


def test_auth_me(tokens):
    for k, v in tokens.items():
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=H(v["token"]), timeout=10)
        assert r.status_code == 200
        assert r.json()["email"] == CREDS[k][0]


@pytest.mark.parametrize("path", ["/api/workspaces", "/api/projects", "/api/tasks/mine", "/api/notifications", "/api/integrations"])
def test_protected_routes_with_token(tokens, path):
    r = requests.get(f"{BASE_URL}{path}", headers=H(tokens["alice"]["token"]), timeout=15)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"


@pytest.mark.parametrize("path", ["/api/workspaces", "/api/projects", "/api/tasks/mine", "/api/notifications"])
def test_protected_routes_without_token(path):
    r = requests.get(f"{BASE_URL}{path}", timeout=10)
    assert r.status_code in (401, 403), f"{path} unauth got {r.status_code}"


def test_google_authorize_url(tokens):
    r = requests.get(f"{BASE_URL}/api/integrations/google/authorize", headers=H(tokens["admin"]["token"]), timeout=10)
    # Should return a URL (may 400 if not configured; check either well-formed URL or config-missing error)
    assert r.status_code in (200, 400, 404), f"{r.status_code} {r.text[:200]}"
    if r.status_code == 200:
        body = r.json()
        # search for a url field
        url = body.get("url") or body.get("authorize_url") or ""
        assert "http" in str(body), f"No URL in response: {body}"


def test_admin_disable_reinstate(tokens):
    # Find demo user id
    r = requests.get(f"{BASE_URL}/api/admin/users", headers=H(tokens["admin"]["token"]), timeout=10)
    assert r.status_code == 200
    users = r.json()
    demo = next((u for u in users if u["email"] == "demo@stitches.app"), None)
    assert demo
    uid = demo["user_id"]
    # Disable
    r = requests.put(f"{BASE_URL}/api/admin/users/{uid}", headers=H(tokens["admin"]["token"]),
                     json={"is_active": False}, timeout=10)
    assert r.status_code == 200
    # Login should fail
    r2 = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "demo@stitches.app", "password": "Demo@123"}, timeout=10)
    assert r2.status_code in (401, 403)
    # Reinstate
    r = requests.put(f"{BASE_URL}/api/admin/users/{uid}", headers=H(tokens["admin"]["token"]),
                     json={"is_active": True}, timeout=10)
    assert r.status_code == 200
    r2 = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "demo@stitches.app", "password": "Demo@123"}, timeout=10)
    assert r2.status_code == 200


# ---- REMINDERS ----
@pytest.fixture(scope="module")
def project_and_task(tokens):
    admin_tok = tokens["admin"]["token"]
    alice_id = tokens["alice"]["user"]["user_id"]

    # Find a workspace (admin has default one, or create)
    ws_r = requests.get(f"{BASE_URL}/api/workspaces", headers=H(admin_tok), timeout=10)
    assert ws_r.status_code == 200
    workspaces = ws_r.json()
    if workspaces:
        ws_id = workspaces[0]["workspace_id"]
    else:
        wr = requests.post(f"{BASE_URL}/api/workspaces", headers=H(admin_tok), json={"name": "TEST_WS"}, timeout=10)
        assert wr.status_code == 200
        ws_id = wr.json()["workspace_id"]

    # Create project
    pr = requests.post(f"{BASE_URL}/api/projects", headers=H(admin_tok),
                      json={"name": "TEST_ReminderProject", "description": "test", "workspace_id": ws_id, "status": "active"}, timeout=10)
    assert pr.status_code == 200, pr.text
    project = pr.json()
    project_id = project["project_id"]

    # Invite alice to project
    inv = requests.post(f"{BASE_URL}/api/projects/{project_id}/invite", headers=H(admin_tok),
                       json={"email": "alice@stitches.app"}, timeout=10)
    # Might already be member, tolerate 200/400
    assert inv.status_code in (200, 400)

    # Create task with due date = today assigned to alice
    today = date.today().isoformat()
    tr = requests.post(f"{BASE_URL}/api/projects/{project_id}/tasks", headers=H(admin_tok),
                      json={"title": "TEST_ReminderTask", "assignee_id": alice_id, "due_date": today}, timeout=10)
    assert tr.status_code == 200, tr.text
    task = tr.json()

    yield {"project_id": project_id, "task_id": task["task_id"], "workspace_id": ws_id}

    # Cleanup
    requests.delete(f"{BASE_URL}/api/tasks/{task['task_id']}", headers=H(admin_tok), timeout=10)
    requests.delete(f"{BASE_URL}/api/projects/{project_id}", headers=H(admin_tok), timeout=10)


def test_scan_reminders_non_admin_403(tokens):
    r = requests.post(f"{BASE_URL}/api/tasks/scan-reminders", headers=H(tokens["alice"]["token"]), timeout=10)
    assert r.status_code == 403


def test_scan_reminders_creates_notification(tokens, project_and_task):
    admin_tok = tokens["admin"]["token"]
    alice_tok = tokens["alice"]["token"]

    # Fetch alice notifications baseline count
    base = requests.get(f"{BASE_URL}/api/notifications", headers=H(alice_tok), timeout=10).json()
    base_notifs = base.get("notifications", []) if isinstance(base, dict) else base
    base_ids = {n.get("notification_id") for n in base_notifs}

    # Scan reminders
    r = requests.post(f"{BASE_URL}/api/tasks/scan-reminders", headers=H(admin_tok), timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "reminded" in body
    assert body["reminded"] >= 1, f"expected >=1 got {body}"

    # Alice should see notification
    n = requests.get(f"{BASE_URL}/api/notifications", headers=H(alice_tok), timeout=10).json()
    assert isinstance(n, dict), f"Expected dict got {type(n)}: {n}"
    notifs = n["notifications"]
    new_notifs = [x for x in notifs if x.get("notification_id") not in base_ids]
    task_due = [x for x in new_notifs if x.get("type") == "task_due"]
    assert task_due, f"No task_due notification found. new_notifs={new_notifs}"
    nd = task_due[0]
    assert nd["title"] in ("Task due soon", "Task overdue")
    assert "TEST_ReminderTask" in nd.get("body", "")
    assert nd.get("link") == "/dashboard"

    # Scan again - should not duplicate
    r2 = requests.post(f"{BASE_URL}/api/tasks/scan-reminders", headers=H(admin_tok), timeout=15)
    assert r2.status_code == 200
    # It should reflect that this task is not scanned again (reminded=0 for our task)
    n2 = requests.get(f"{BASE_URL}/api/notifications", headers=H(alice_tok), timeout=10).json()
    task_due_2 = [x for x in n2["notifications"] if x.get("type") == "task_due" and "TEST_ReminderTask" in x.get("body", "")]
    assert len(task_due_2) == len(task_due), f"Duplicate reminder created: {len(task_due_2)} vs {len(task_due)}"


def test_reminder_reset_on_update(tokens, project_and_task):
    admin_tok = tokens["admin"]["token"]
    alice_tok = tokens["alice"]["token"]
    task_id = project_and_task["task_id"]

    # Update due_date -> should reset reminded
    today = date.today().isoformat()
    ur = requests.put(f"{BASE_URL}/api/tasks/{task_id}", headers=H(admin_tok),
                     json={"due_date": today}, timeout=10)
    assert ur.status_code == 200

    # Count existing task_due for our task
    before = requests.get(f"{BASE_URL}/api/notifications", headers=H(alice_tok), timeout=10).json()
    before_count = len([x for x in before["notifications"] if "TEST_ReminderTask" in x.get("body", "")])

    # Scan again
    r = requests.post(f"{BASE_URL}/api/tasks/scan-reminders", headers=H(admin_tok), timeout=15)
    assert r.status_code == 200
    assert r.json()["reminded"] >= 1

    after = requests.get(f"{BASE_URL}/api/notifications", headers=H(alice_tok), timeout=10).json()
    after_count = len([x for x in after["notifications"] if "TEST_ReminderTask" in x.get("body", "")])
    assert after_count == before_count + 1, f"Expected 1 new notif, before={before_count} after={after_count}"
