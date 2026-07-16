import os, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE:
    # fall back to reading frontend env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")

DEMO = {"email": "demo@stitches.app", "password": "Demo@123"}
ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}


def login(creds):
    r = requests.post(f"{BASE}/api/auth/login", json=creds, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def h(t):
    return {"Authorization": f"Bearer {t}"}


def test_admin_login_regression():
    t = login(ADMIN)
    r = requests.get(f"{BASE}/api/auth/me", headers=h(t), timeout=10)
    assert r.status_code == 200
    assert r.json()["email"] == "admin@stitches.app"


def test_devices_flow_end_to_end():
    # Two demo logins → 2 sessions
    t1 = login(DEMO)
    t2 = login(DEMO)

    # both tokens valid
    assert requests.get(f"{BASE}/api/auth/me", headers=h(t1)).status_code == 200
    assert requests.get(f"{BASE}/api/auth/me", headers=h(t2)).status_code == 200

    # list sessions - current flag exactly on t1's session
    r = requests.get(f"{BASE}/api/auth/sessions", headers=h(t1))
    assert r.status_code == 200
    sessions = r.json()
    assert len(sessions) >= 2
    currents = [s for s in sessions if s.get("current")]
    assert len(currents) == 1
    assert all("session_id" in s and "device" in s for s in sessions)

    # revoke-others from t1
    r = requests.post(f"{BASE}/api/auth/sessions/revoke-others", headers=h(t1))
    assert r.status_code == 200
    new_token = r.json()["token"]
    assert new_token

    # old t1 token now invalid
    assert requests.get(f"{BASE}/api/auth/me", headers=h(t1)).status_code == 401
    # t2 invalid
    assert requests.get(f"{BASE}/api/auth/me", headers=h(t2)).status_code == 401
    # new token works
    assert requests.get(f"{BASE}/api/auth/me", headers=h(new_token)).status_code == 200

    # exactly 1 active session
    r = requests.get(f"{BASE}/api/auth/sessions", headers=h(new_token))
    assert r.status_code == 200
    lst = r.json()
    assert len(lst) == 1
    assert lst[0]["current"] is True


def test_single_revoke():
    t1 = login(DEMO)
    t2 = login(DEMO)
    sessions = requests.get(f"{BASE}/api/auth/sessions", headers=h(t1)).json()
    # find non-current
    other = [s for s in sessions if not s.get("current")][0]
    r = requests.delete(f"{BASE}/api/auth/sessions/{other['session_id']}", headers=h(t1))
    assert r.status_code == 200
    # t2 should now 401
    assert requests.get(f"{BASE}/api/auth/me", headers=h(t2)).status_code == 401
    # t1 still valid
    assert requests.get(f"{BASE}/api/auth/me", headers=h(t1)).status_code == 200
    # cleanup: revoke-others to reset state
    requests.post(f"{BASE}/api/auth/sessions/revoke-others", headers=h(t1))
