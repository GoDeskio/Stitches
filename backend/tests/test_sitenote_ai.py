"""Tests for site-config (announcement + support email) and AI agent contact_support + regression."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@stitches.app", "Admin@123")


@pytest.fixture(scope="module")
def demo_token():
    return _login("demo@stitches.app", "Demo@123")


@pytest.fixture(scope="module")
def admin_h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def demo_h(demo_token):
    return {"Authorization": f"Bearer {demo_token}"}


# ---------------- site-config ----------------

def test_public_site_config_no_auth():
    r = requests.get(f"{API}/site-config", timeout=20)
    assert r.status_code == 200
    data = r.json()
    assert "announcement" in data and "support_email" in data
    ann = data["announcement"]
    for k in ("enabled", "title", "message", "signature", "updated_at"):
        assert k in ann, f"missing key {k} in announcement"


def test_admin_put_site_config_persists(admin_h):
    payload = {
        "announcement": {"enabled": False, "title": "Welcome!", "message": "Hi", "signature": "- Team"},
        "support_email": "help@stitches.app",
    }
    r = requests.put(f"{API}/admin/site-config", json=payload, headers=admin_h, timeout=20)
    assert r.status_code == 200, r.text
    # verify via public endpoint
    r2 = requests.get(f"{API}/site-config", timeout=20)
    assert r2.status_code == 200
    d = r2.json()
    assert d["announcement"]["enabled"] is False
    assert d["announcement"]["title"] == "Welcome!"
    assert d["announcement"]["message"] == "Hi"
    assert d["announcement"]["signature"] == "- Team"
    assert d["announcement"]["updated_at"], "updated_at should be set"
    assert d["support_email"] == "help@stitches.app"


def test_non_admin_forbidden_on_admin_site_config(demo_h):
    r = requests.get(f"{API}/admin/site-config", headers=demo_h, timeout=20)
    assert r.status_code == 403
    r2 = requests.put(f"{API}/admin/site-config", json={"announcement": {"enabled": True}}, headers=demo_h, timeout=20)
    assert r2.status_code == 403


# ---------------- AI agent ----------------

def test_ai_contact_support_flow(demo_h, admin_h):
    r = requests.post(f"{API}/ai/agent",
                      json={"message": "The video call feature crashes when I join, can someone help?"},
                      headers=demo_h, timeout=60)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("action") == "contact_support", f"expected contact_support, got {body.get('action')} full={body}"
    assert body.get("result", {}).get("ok") is True
    # verify admin notification created
    time.sleep(1)
    n = requests.get(f"{API}/notifications", headers=admin_h, timeout=20)
    assert n.status_code == 200
    notifs = n.json().get("notifications", [])
    support_notifs = [x for x in notifs if x.get("type") == "support"]
    assert support_notifs, f"no support notification found; got {len(notifs)} total"
    assert any("Support request" in (x.get("title") or "") for x in support_notifs)


def test_ai_create_project_regression(demo_h):
    name = f"TEST_Apollo_{int(time.time())}"
    r = requests.post(f"{API}/ai/agent", json={"message": f"create a project called {name}"},
                      headers=demo_h, timeout=60)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b.get("action") == "create_project", f"expected create_project got {b}"
    assert b.get("result", {}).get("ok") is True


def test_ai_informational_question_regression(demo_h):
    r = requests.post(f"{API}/ai/agent", json={"message": "what is a workspace?"},
                      headers=demo_h, timeout=60)
    assert r.status_code == 200, r.text
    b = r.json()
    assert b.get("action") is None, f"expected null action got {b}"
    assert b.get("reply"), "should have a text reply"


# ---------------- cleanup ----------------

def test_zz_cleanup(admin_h, demo_token):
    # reset site config
    requests.put(f"{API}/admin/site-config",
                 json={"announcement": {"enabled": True,
                                        "title": "Hello, and welcome",
                                        "message": ("Thank you for visiting our website. It's new and has a lot of bugs, "
                                                    "but if you use it and help us improve it, it's free forever. "
                                                    "Thank you for your patience and support."),
                                        "signature": "— The Development team"},
                       "support_email": ""},
                 headers=admin_h, timeout=20)
    # delete TEST_Apollo projects owned by demo
    dh = {"Authorization": f"Bearer {demo_token}"}
    prs = requests.get(f"{API}/projects", headers=dh, timeout=20)
    if prs.status_code == 200:
        for p in prs.json():
            if (p.get("name") or "").startswith("TEST_Apollo"):
                requests.delete(f"{API}/projects/{p['project_id']}", headers=dh, timeout=20)
