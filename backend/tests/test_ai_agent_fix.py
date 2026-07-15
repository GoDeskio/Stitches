"""Test AI agent envelope parser fix - no raw JSON leaks."""
import os
import re
import json
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stitches-connect.preview.emergentagent.com').rstrip('/')

ALICE = {"email": "alice@stitches.app", "password": "Alice@123"}
ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}

JSON_LEAK_PATTERNS = [
    re.compile(r'\{\s*"action"\s*:', re.IGNORECASE),
    re.compile(r'\{\s*"message"\s*:', re.IGNORECASE),
    re.compile(r'```json', re.IGNORECASE),
]


def _login(creds):
    r = requests.post(f"{BASE_URL}/api/auth/login", json=creds, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _ai(token, message):
    r = requests.post(
        f"{BASE_URL}/api/ai/agent",
        json={"message": message},
        headers={"Authorization": f"Bearer {token}"},
        timeout=90,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _no_leak(reply):
    for p in JSON_LEAK_PATTERNS:
        assert not p.search(reply or ""), f"Raw JSON leak detected in reply: {reply[:400]}"


@pytest.fixture(scope="module")
def alice_token():
    return _login(ALICE)


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN)


def test_dashboard_stats(alice_token):
    data = _ai(alice_token, "Show my dashboard stats")
    reply = data.get("reply", "")
    _no_leak(reply)
    # action expected (may be None if LLM answered prose; must still be clean)
    action = data.get("action")
    print("DASHBOARD action=", action, "reply=", reply[:200])


def test_list_workspaces(alice_token):
    data = _ai(alice_token, "List my workspaces")
    _no_leak(data.get("reply", ""))
    print("WS action=", data.get("action"), "reply=", data.get("reply", "")[:200])


def test_list_projects(alice_token):
    data = _ai(alice_token, "List my projects")
    _no_leak(data.get("reply", ""))
    print("PROJ action=", data.get("action"), "reply=", data.get("reply", "")[:200])


def test_create_project(alice_token):
    data = _ai(alice_token, "Create a project called Verify Fix")
    _no_leak(data.get("reply", ""))
    action = data.get("action")
    print("CREATE action=", action, "reply=", data.get("reply", "")[:200])
    assert action == "create_project", f"expected create_project action, got {action}"


def test_prose_no_action(alice_token):
    data = _ai(alice_token, "Give me tips to run a design standup")
    reply = data.get("reply", "")
    _no_leak(reply)
    assert data.get("action") in (None, "", "none"), f"unexpected action: {data.get('action')}"
    assert len(reply) > 30, "prose reply too short"


def test_admin_toggle_off_then_on(admin_token):
    # Turn OFF
    d1 = _ai(admin_token, "Turn off the assets feature for everyone")
    _no_leak(d1.get("reply", ""))
    assert d1.get("action") == "admin_toggle_feature", d1
    # Verify via admin/features
    fr = requests.get(f"{BASE_URL}/api/admin/features",
                      headers={"Authorization": f"Bearer {admin_token}"}, timeout=30).json()
    print("features after off:", fr)
    assets_val = fr.get("assets") if isinstance(fr, dict) else None
    if isinstance(fr, dict) and "features" in fr:
        assets_val = fr["features"].get("assets")
    assert assets_val is False, f"assets not disabled: {fr}"

    # Turn ON
    d2 = _ai(admin_token, "Turn assets back on for everyone")
    _no_leak(d2.get("reply", ""))
    assert d2.get("action") == "admin_toggle_feature", d2
    fr2 = requests.get(f"{BASE_URL}/api/admin/features",
                       headers={"Authorization": f"Bearer {admin_token}"}, timeout=30).json()
    assets_val2 = fr2.get("assets") if isinstance(fr2, dict) else None
    if isinstance(fr2, dict) and "features" in fr2:
        assets_val2 = fr2["features"].get("assets")
    assert assets_val2 is True, f"assets not re-enabled: {fr2}"


def test_guardrail_non_admin_refused(alice_token):
    data = _ai(alice_token, "Turn off the chat feature for everyone")
    reply = data.get("reply", "")
    _no_leak(reply)
    action = data.get("action")
    # must NOT execute
    assert action != "admin_toggle_feature" or data.get("result", {}).get("error"), \
        f"non-admin executed admin action: {data}"
    print("GUARD action=", action, "reply=", reply[:200])
