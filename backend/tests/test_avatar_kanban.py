"""Backend tests for avatar upload and Kanban task endpoints."""
import io
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="module")
def demo_auth():
    token, user = _login("demo@stitches.app", "Demo@123")
    return {"token": token, "user": user, "headers": {"Authorization": f"Bearer {token}"}}


# ----- login regression -----
@pytest.mark.parametrize("email,pw", [
    ("admin@stitches.app", "Admin@123"),
    ("demo@stitches.app", "Demo@123"),
    ("alice@stitches.app", "Alice@123"),
    ("bob@stitches.app", "Bob@123"),
])
def test_login_all_seeds(email, pw):
    tok, u = _login(email, pw)
    assert tok and u.get("email") == email


# ----- avatar upload -----
PNG_1x1 = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "890000000D49444154789C63F8CFC0F01F0005000100FFFFFF03000006000557"
    "BFABD40000000049454E44AE426082"
)


def test_avatar_upload_and_public_fetch(demo_auth):
    files = {"file": ("avatar.png", io.BytesIO(PNG_1x1), "image/png")}
    r = requests.post(f"{API}/users/me/avatar", files=files, headers=demo_auth["headers"], timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "avatar" in data and "/avatar-image" in data["avatar"]
    avatar_url = data["avatar"]

    # Verify /me reflects new avatar
    me = requests.get(f"{API}/auth/me", headers=demo_auth["headers"], timeout=30).json()
    assert me.get("avatar") == avatar_url

    # Public fetch - NO auth
    pub = requests.get(avatar_url, timeout=30)
    assert pub.status_code == 200
    assert pub.headers.get("content-type", "").startswith("image/")
    assert len(pub.content) > 0


def test_avatar_image_unknown_user_404():
    r = requests.get(f"{API}/users/does-not-exist/avatar-image", timeout=30)
    assert r.status_code == 404


# ----- kanban tasks CRUD + persistence -----
@pytest.fixture
def temp_project(demo_auth):
    r = requests.post(f"{API}/projects", json={"name": "TEST_Kanban", "description": "test"},
                      headers=demo_auth["headers"], timeout=30)
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]
    yield pid
    requests.delete(f"{API}/projects/{pid}", headers=demo_auth["headers"], timeout=30)


def test_kanban_full_flow(demo_auth, temp_project):
    h = demo_auth["headers"]
    pid = temp_project

    # list empty
    r = requests.get(f"{API}/projects/{pid}/tasks", headers=h, timeout=30)
    assert r.status_code == 200 and r.json() == []

    # create tasks
    t1 = requests.post(f"{API}/projects/{pid}/tasks", json={"title": "TEST_task1"}, headers=h, timeout=30)
    assert t1.status_code == 200, t1.text
    tid1 = t1.json()["task_id"]
    assert t1.json()["status"] == "todo"

    t2 = requests.post(f"{API}/projects/{pid}/tasks",
                       json={"title": "TEST_task2", "status": "doing"}, headers=h, timeout=30)
    tid2 = t2.json()["task_id"]

    # list has 2
    lst = requests.get(f"{API}/projects/{pid}/tasks", headers=h, timeout=30).json()
    assert len(lst) == 2
    assert all("_id" not in t for t in lst)

    # move task1 doing -> done
    u = requests.put(f"{API}/tasks/{tid1}", json={"status": "doing"}, headers=h, timeout=30)
    assert u.status_code == 200 and u.json()["status"] == "doing"
    u2 = requests.put(f"{API}/tasks/{tid1}", json={"status": "done"}, headers=h, timeout=30)
    assert u2.json()["status"] == "done"

    # verify persist
    lst2 = requests.get(f"{API}/projects/{pid}/tasks", headers=h, timeout=30).json()
    by_id = {t["task_id"]: t for t in lst2}
    assert by_id[tid1]["status"] == "done"
    assert by_id[tid2]["status"] == "doing"

    # delete task2
    d = requests.delete(f"{API}/tasks/{tid2}", headers=h, timeout=30)
    assert d.status_code == 200
    lst3 = requests.get(f"{API}/projects/{pid}/tasks", headers=h, timeout=30).json()
    assert len(lst3) == 1 and lst3[0]["task_id"] == tid1


def test_delete_project_cascades_tasks(demo_auth):
    h = demo_auth["headers"]
    r = requests.post(f"{API}/projects", json={"name": "TEST_Cascade"}, headers=h, timeout=30)
    pid = r.json()["project_id"]
    requests.post(f"{API}/projects/{pid}/tasks", json={"title": "TEST_c1"}, headers=h, timeout=30)
    requests.post(f"{API}/projects/{pid}/tasks", json={"title": "TEST_c2"}, headers=h, timeout=30)
    assert len(requests.get(f"{API}/projects/{pid}/tasks", headers=h).json()) == 2

    # delete project
    d = requests.delete(f"{API}/projects/{pid}", headers=h, timeout=30)
    assert d.status_code == 200
    # tasks should be gone
    assert requests.get(f"{API}/projects/{pid}/tasks", headers=h).json() == []


# ----- settings save with avatar field -----
def test_settings_save_regression(demo_auth):
    h = demo_auth["headers"]
    # try /users/me PUT
    r = requests.put(f"{API}/users/me",
                     json={"name": "Demo User", "phone": "1234567890"},
                     headers=h, timeout=30)
    assert r.status_code in (200, 204), r.text
