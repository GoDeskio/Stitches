"""Tests for message reactions and AI agent send/invite actions."""
import os
import uuid
import time
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip()
BASE_URL = BASE_URL.rstrip("/")
API = f"{BASE_URL}/api"


def H(t):
    return {"Authorization": f"Bearer {t}"}


def login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


@pytest.fixture(scope="module")
def alice():
    return login("alice@stitches.app", "Alice@123")


@pytest.fixture(scope="module")
def bob():
    return login("bob@stitches.app", "Bob@123")


@pytest.fixture(scope="module")
def alice_ws(alice):
    tok, _ = alice
    # Create a fresh workspace for tests to avoid pollution
    name = f"TESTWS_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/workspaces", json={"name": name}, headers=H(tok))
    assert r.status_code == 200
    ws_id = r.json()["workspace_id"]
    chs = requests.get(f"{API}/workspaces/{ws_id}/channels", headers=H(tok)).json()
    general = next(c for c in chs if c["name"] == "general")
    return {"name": name, "ws_id": ws_id, "general_id": general["channel_id"]}


class TestReactions:
    def test_react_toggle(self, alice, alice_ws):
        tok, _ = alice
        r = requests.post(f"{API}/messages", json={"channel_id": alice_ws["general_id"], "text": "hi for react"}, headers=H(tok))
        assert r.status_code == 200
        mid = r.json()["message_id"]

        # add reaction
        r = requests.post(f"{API}/messages/{mid}/react", json={"emoji": "👍"}, headers=H(tok))
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        assert "👍" in d["reactions"] and len(d["reactions"]["👍"]) == 1

        # toggle off
        r = requests.post(f"{API}/messages/{mid}/react", json={"emoji": "👍"}, headers=H(tok))
        assert r.status_code == 200
        assert "👍" not in r.json()["reactions"]

    def test_reaction_multiple_users(self, alice, bob, alice_ws):
        atok, _ = alice
        btok, _ = bob
        # Add bob to workspace so he can react
        requests.post(f"{API}/workspaces/{alice_ws['ws_id']}/invite", json={"email": "bob@stitches.app"}, headers=H(atok))
        r = requests.post(f"{API}/messages", json={"channel_id": alice_ws["general_id"], "text": "multi-react"}, headers=H(atok))
        mid = r.json()["message_id"]

        r1 = requests.post(f"{API}/messages/{mid}/react", json={"emoji": "🎉"}, headers=H(atok))
        r2 = requests.post(f"{API}/messages/{mid}/react", json={"emoji": "🎉"}, headers=H(btok))
        assert r2.status_code == 200
        assert len(r2.json()["reactions"]["🎉"]) == 2


class TestAgentActions:
    def _agent(self, tok, msg):
        r = requests.post(f"{API}/ai/agent", json={"message": msg}, headers=H(tok), timeout=60)
        assert r.status_code == 200, r.text
        return r.json()

    def test_agent_send_message(self, alice, alice_ws):
        tok, _ = alice
        ws_name = alice_ws["name"]
        text = f"Standup at 10am {uuid.uuid4().hex[:6]}"
        d = self._agent(tok, f'Post "{text}" to the general channel in {ws_name}')
        assert d.get("action") == "send_message", d
        assert d.get("result", {}).get("ok") is True, d
        # Verify message exists
        msgs = requests.get(f"{API}/channels/{alice_ws['general_id']}/messages", headers=H(tok)).json()
        assert any(m["text"] == text for m in msgs), f"Message not found: {text}"
        # No raw JSON leak
        reply = d.get("reply", "")
        assert "{" not in reply or "action" not in reply.lower(), f"Possible JSON leak: {reply}"

    def test_agent_invite_to_workspace(self, alice, bob, alice_ws):
        tok, _ = alice
        btok, _ = bob
        # Create fresh workspace to test invite from scratch
        wsname = f"TESTAGENTWS_{uuid.uuid4().hex[:5]}"
        r = requests.post(f"{API}/workspaces", json={"name": wsname}, headers=H(tok))
        assert r.status_code == 200

        d = self._agent(tok, f"Add bob@stitches.app to my {wsname} workspace")
        assert d.get("action") == "invite_to_workspace", d
        assert d.get("result", {}).get("ok") is True, d

        # Bob should now see the workspace
        bws = requests.get(f"{API}/workspaces", headers=H(btok)).json()
        assert any(w["name"] == wsname for w in bws), f"Bob not in {wsname}"

    def test_agent_invite_to_project(self, alice, bob):
        tok, _ = alice
        btok, _ = bob
        pname = f"TESTAGENTPROJ_{uuid.uuid4().hex[:5]}"
        r = requests.post(f"{API}/projects", json={"name": pname, "status": "active"}, headers=H(tok))
        assert r.status_code == 200

        d = self._agent(tok, f"Add bob@stitches.app to my {pname} project")
        assert d.get("action") == "invite_to_project", d
        assert d.get("result", {}).get("ok") is True, d

        bprojs = requests.get(f"{API}/projects", headers=H(btok)).json()
        assert any(p["name"] == pname for p in bprojs), f"Bob not in {pname}"

    def test_agent_prose_no_json_leak(self, alice):
        tok, _ = alice
        d = self._agent(tok, "What is 2+2? Explain briefly.")
        reply = d.get("reply", "")
        # Should not include a JSON envelope
        assert not (reply.strip().startswith("{") and '"action"' in reply), f"JSON leak: {reply}"
