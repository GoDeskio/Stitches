"""SFU admin config + ring notification tests (iteration 23)."""
import os, requests, pytest, uuid

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = BASE + "/api"

def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]

@pytest.fixture(scope="module")
def admin_h():
    return {"Authorization": f"Bearer {_login('admin@stitches.app','Admin@123')}"}

@pytest.fixture(scope="module")
def demo_h():
    return {"Authorization": f"Bearer {_login('demo@stitches.app','Demo@123')}"}

@pytest.fixture(scope="module")
def alice_h():
    return {"Authorization": f"Bearer {_login('alice@stitches.app','Alice@123')}"}


# --- rtc/config sfu default OFF ---
def test_rtc_config_sfu_default_off(demo_h):
    r = requests.get(f"{API}/rtc/config", headers=demo_h, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert "sfu" in d and d["sfu"]["enabled"] is False
    assert isinstance(d.get("iceServers"), list) and len(d["iceServers"]) >= 1


# --- sfu-token gated when disabled ---
def test_sfu_token_400_when_disabled(demo_h):
    r = requests.post(f"{API}/rtc/sfu-token", headers=demo_h, json={"room_id": "room_test"}, timeout=10)
    assert r.status_code == 400


# --- admin sfu-config toggle round-trip ---
def test_admin_sfu_config_toggle(admin_h):
    # Enable
    payload = {"enabled": True, "url": "wss://livekit.example.com", "api_key": "APItestkey", "api_secret": "supersecret_test_value"}
    r = requests.put(f"{API}/admin/sfu-config", headers=admin_h, json=payload, timeout=10)
    assert r.status_code == 200
    g = requests.get(f"{API}/admin/sfu-config", headers=admin_h, timeout=10).json()
    assert g["enabled"] is True
    assert g["url"] == payload["url"]
    assert g["api_key"] == payload["api_key"]
    assert g["has_secret"] is True
    # rtc/config now reflects
    r2 = requests.get(f"{API}/rtc/config", headers=admin_h, timeout=10).json()
    assert r2["sfu"]["enabled"] is True and r2["sfu"]["url"] == payload["url"]
    # Disable + clear
    r = requests.put(f"{API}/admin/sfu-config", headers=admin_h,
                     json={"enabled": False, "url": "", "api_key": "", "api_secret": ""}, timeout=10)
    assert r.status_code == 200
    r3 = requests.get(f"{API}/rtc/config", headers=admin_h, timeout=10).json()
    assert r3["sfu"]["enabled"] is False


# --- non-admin cannot access admin sfu-config ---
def test_sfu_config_admin_gated(demo_h):
    r = requests.get(f"{API}/admin/sfu-config", headers=demo_h, timeout=10)
    assert r.status_code in (401, 403)


# --- Channel Meet: creates meeting, posts message with URL, notifies members ---
def test_channel_meet_ring_notification(demo_h, alice_h):
    # find a channel demo has where alice is also a member
    ws = requests.get(f"{API}/workspaces", headers=demo_h, timeout=10).json()
    assert isinstance(ws, list) and len(ws) > 0
    # get channels of first workspace
    workspace_id = ws[0]["workspace_id"]
    # ensure alice joined
    requests.post(f"{API}/workspaces/{workspace_id}/join", headers=alice_h, timeout=10)
    chans = requests.get(f"{API}/workspaces/{workspace_id}/channels", headers=demo_h, timeout=10).json()
    assert len(chans) > 0
    channel_id = chans[0]["channel_id"]

    # snapshot alice's notifications count
    def _list(h):
        d = requests.get(f"{API}/notifications", headers=h, timeout=10).json()
        return d.get("notifications", d) if isinstance(d, dict) else d
    n_before = _list(alice_h)
    before_ids = {n.get("notification_id") for n in n_before}

    # create meeting via channel
    r = requests.post(f"{API}/meetings", headers=demo_h, json={"channel_id": channel_id}, timeout=15)
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["room_id"].startswith("room_")

    # message posted to channel with join URL
    msgs = requests.get(f"{API}/channels/{channel_id}/messages?limit=5", headers=demo_h, timeout=10).json()
    assert any("Started a video meeting" in (mm.get("text") or "") and m["room_id"] in (mm.get("text") or "") for mm in msgs)

    # alice sees meeting notification
    n_after = _list(alice_h)
    new_notifs = [n for n in n_after if n.get("notification_id") not in before_ids]
    meeting_notifs = [n for n in new_notifs if n.get("type") == "meeting"]
    assert len(meeting_notifs) >= 1, f"No meeting notification for Alice: {new_notifs}"
    assert m["room_id"] in (meeting_notifs[0].get("link") or "")
