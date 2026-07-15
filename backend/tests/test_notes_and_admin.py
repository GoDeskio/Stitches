"""Backend tests for Notes CRUD + Admin disable/reinstate flow."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}
DEMO = {"email": "demo@stitches.app", "password": "Demo@123"}
ALICE = {"email": "alice@stitches.app", "password": "Alice@123"}
BOB = {"email": "bob@stitches.app", "password": "Bob@123"}


def login(creds):
    r = requests.post(f"{API}/auth/login", json=creds, timeout=30)
    return r


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def demo_token():
    r = login(DEMO)
    assert r.status_code == 200, f"Demo login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def alice_token():
    r = login(ALICE)
    assert r.status_code == 200, f"Alice login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    r = login(ADMIN)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


# ---------------- Notes ----------------
class TestNotes:
    def test_create_get_update_delete_note(self, demo_token):
        # CREATE
        payload = {"title": "TEST_note_title", "content": "hello world", "color": "yellow"}
        r = requests.post(f"{API}/notes", json=payload, headers=auth_headers(demo_token))
        assert r.status_code == 200, r.text
        note = r.json()
        assert note["title"] == "TEST_note_title"
        assert note["content"] == "hello world"
        assert note["color"] == "yellow"
        assert "note_id" in note
        note_id = note["note_id"]

        # LIST includes it
        r = requests.get(f"{API}/notes", headers=auth_headers(demo_token))
        assert r.status_code == 200
        ids = [n["note_id"] for n in r.json()]
        assert note_id in ids

        # UPDATE
        upd = {"title": "TEST_note_updated", "content": "changed", "color": "blue"}
        r = requests.put(f"{API}/notes/{note_id}", json=upd, headers=auth_headers(demo_token))
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "TEST_note_updated"
        assert r.json()["content"] == "changed"

        # Verify via GET
        r = requests.get(f"{API}/notes", headers=auth_headers(demo_token))
        found = [n for n in r.json() if n["note_id"] == note_id]
        assert found and found[0]["title"] == "TEST_note_updated"

        # DELETE
        r = requests.delete(f"{API}/notes/{note_id}", headers=auth_headers(demo_token))
        assert r.status_code == 200

        # Verify gone
        r = requests.get(f"{API}/notes", headers=auth_headers(demo_token))
        ids = [n["note_id"] for n in r.json()]
        assert note_id not in ids

    def test_notes_are_private_per_user(self, demo_token, alice_token):
        # Demo creates a note
        r = requests.post(f"{API}/notes",
                          json={"title": "TEST_private", "content": "secret", "color": "red"},
                          headers=auth_headers(demo_token))
        assert r.status_code == 200
        nid = r.json()["note_id"]

        # Alice should NOT see it
        r = requests.get(f"{API}/notes", headers=auth_headers(alice_token))
        assert r.status_code == 200
        alice_ids = [n["note_id"] for n in r.json()]
        assert nid not in alice_ids

        # Alice cannot delete demo's note (should be no-op; then still exists for demo)
        r = requests.delete(f"{API}/notes/{nid}", headers=auth_headers(alice_token))
        # backend returns ok either way but must not affect demo's note
        r = requests.get(f"{API}/notes", headers=auth_headers(demo_token))
        demo_ids = [n["note_id"] for n in r.json()]
        assert nid in demo_ids, "Another user was able to delete owner's note!"

        # cleanup
        requests.delete(f"{API}/notes/{nid}", headers=auth_headers(demo_token))

    def test_notes_requires_auth(self):
        r = requests.get(f"{API}/notes")
        assert r.status_code in (401, 403)


# ---------------- Admin disable/reinstate ----------------
class TestAdminDisable:
    def test_disable_and_reinstate_bob(self, admin_token):
        # find bob
        r = requests.get(f"{API}/admin/users", headers=auth_headers(admin_token))
        assert r.status_code == 200
        users = r.json()
        bob = next((u for u in users if u.get("email") == BOB["email"]), None)
        assert bob is not None, "Bob not found in admin users list"
        bob_id = bob["user_id"]

        try:
            # Disable
            r = requests.put(f"{API}/admin/users/{bob_id}",
                             json={"is_active": False}, headers=auth_headers(admin_token))
            assert r.status_code == 200, r.text
            assert r.json().get("is_active") is False

            # Bob cannot login -> 403
            r = login(BOB)
            assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"
            assert "disabled" in r.text.lower()

            # Reinstate
            r = requests.put(f"{API}/admin/users/{bob_id}",
                             json={"is_active": True}, headers=auth_headers(admin_token))
            assert r.status_code == 200
            assert r.json().get("is_active") is True

            # Bob can login again
            r = login(BOB)
            assert r.status_code == 200, f"Bob login after reinstate failed: {r.text}"
        finally:
            # ALWAYS reinstate
            requests.put(f"{API}/admin/users/{bob_id}",
                         json={"is_active": True}, headers=auth_headers(admin_token))

    def test_admin_users_requires_admin(self, demo_token):
        r = requests.get(f"{API}/admin/users", headers=auth_headers(demo_token))
        assert r.status_code in (401, 403)
