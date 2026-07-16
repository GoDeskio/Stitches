"""Iteration 22: RTC config + admin TURN recheck."""
import os, requests, pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")


def _login(email, pw):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_tok():
    return _login("admin@stitches.app", "Admin@123")


@pytest.fixture(scope="module")
def demo_tok():
    return _login("demo@stitches.app", "Demo@123")


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def test_rtc_config_stun_default(demo_tok, admin_tok):
    # ensure clean state first
    requests.put(f"{BASE}/api/admin/rtc-config", json={"urls": "", "username": "", "credential": ""}, headers=_h(admin_tok), timeout=10)
    r = requests.get(f"{BASE}/api/rtc/config", headers=_h(demo_tok), timeout=10)
    assert r.status_code == 200
    ice = r.json()["iceServers"]
    assert any("stun:" in (s["urls"] if isinstance(s["urls"], str) else s["urls"][0]) for s in ice)


def test_admin_rtc_get_masks_credential(admin_tok):
    r = requests.get(f"{BASE}/api/admin/rtc-config", headers=_h(admin_tok), timeout=10)
    assert r.status_code == 200
    body = r.json()
    assert "has_credential" in body
    assert "credential" not in body


def test_admin_rtc_forbidden_for_non_admin(demo_tok):
    r = requests.get(f"{BASE}/api/admin/rtc-config", headers=_h(demo_tok), timeout=10)
    assert r.status_code == 403


def test_set_turn_and_verify_appears_in_ice(admin_tok, demo_tok):
    payload = {"urls": "turn:turn.example.com:3478", "username": "u", "credential": "c"}
    r = requests.put(f"{BASE}/api/admin/rtc-config", json=payload, headers=_h(admin_tok), timeout=10)
    assert r.status_code == 200
    ice = requests.get(f"{BASE}/api/rtc/config", headers=_h(demo_tok), timeout=10).json()["iceServers"]
    assert any("turn:" in (s["urls"] if isinstance(s["urls"], str) else s["urls"][0]) for s in ice), ice
    # cleanup - clear
    requests.put(f"{BASE}/api/admin/rtc-config", json={"urls": "", "username": "", "credential": ""}, headers=_h(admin_tok), timeout=10)
    ice2 = requests.get(f"{BASE}/api/rtc/config", headers=_h(demo_tok), timeout=10).json()["iceServers"]
    assert not any("turn:" in (s["urls"] if isinstance(s["urls"], str) else s["urls"][0]) for s in ice2)


def test_create_meeting(demo_tok):
    r = requests.post(f"{BASE}/api/meetings", json={"name": "TEST_it22"}, headers=_h(demo_tok), timeout=10)
    assert r.status_code == 200
    assert r.json().get("room_id", "").startswith("room_")
