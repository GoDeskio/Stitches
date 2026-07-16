"""Tests for iteration 19: delete-avatar, downloads config, users search/limit, messages pagination."""
import os
import requests
import pytest
from datetime import datetime

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {email}: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@stitches.app", "Admin@123")


@pytest.fixture(scope="module")
def demo_token():
    return _login("demo@stitches.app", "Demo@123")


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---- Delete avatar ----
class TestDeleteAvatar:
    def test_delete_avatar_returns_null(self, demo_token):
        r = requests.delete(f"{API}/users/me/avatar", headers=_h(demo_token), timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("avatar") in (None, "", "null")
        # Verify persistence
        me = requests.get(f"{API}/auth/me", headers=_h(demo_token), timeout=30).json()
        assert me.get("avatar") in (None, "", "null")


# ---- Downloads config ----
class TestDownloadsConfig:
    def test_reset_empty_and_get(self, admin_token):
        # Clear first
        r = requests.put(f"{API}/admin/downloads-config", headers=_h(admin_token),
                         json={"repo": ""}, timeout=30)
        assert r.status_code == 200, r.text
        # GET release
        r = requests.get(f"{API}/downloads/release", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("repo") == ""
        assert d.get("releases_url") == ""
        assert "assets" in d
        assert set(d["assets"].keys()) >= {"windows", "macos", "linux"}

    def test_non_admin_put_forbidden(self, demo_token):
        r = requests.put(f"{API}/admin/downloads-config", headers=_h(demo_token),
                         json={"repo": "octocat/Hello-World"}, timeout=30)
        assert r.status_code == 403, r.text

    def test_admin_set_repo_and_url(self, admin_token):
        r = requests.put(f"{API}/admin/downloads-config", headers=_h(admin_token),
                         json={"repo": "octocat/Hello-World"}, timeout=30)
        assert r.status_code == 200, r.text
        r = requests.get(f"{API}/downloads/release", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d.get("repo") == "octocat/Hello-World"
        assert d.get("releases_url") == "https://github.com/octocat/Hello-World/releases"

    def test_cleanup_reset(self, admin_token):
        r = requests.put(f"{API}/admin/downloads-config", headers=_h(admin_token),
                         json={"repo": ""}, timeout=30)
        assert r.status_code == 200


# ---- Users list search/limit ----
class TestUsersSearchLimit:
    def test_limit_respected(self, admin_token):
        r = requests.get(f"{API}/users?limit=2", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        arr = r.json()
        # Some servers return {users:[..]} etc; handle both
        if isinstance(arr, dict):
            arr = arr.get("users") or arr.get("items") or []
        assert isinstance(arr, list)
        assert len(arr) <= 2

    def test_q_filter(self, admin_token):
        r = requests.get(f"{API}/users?limit=10&q=demo", headers=_h(admin_token), timeout=30)
        assert r.status_code == 200, r.text
        arr = r.json()
        if isinstance(arr, dict):
            arr = arr.get("users") or arr.get("items") or []
        assert any("demo" in (u.get("email", "") + u.get("name", "")).lower() for u in arr), arr

    def test_q_filter_case_insensitive(self, admin_token):
        r = requests.get(f"{API}/users?limit=10&q=DEMO", headers=_h(admin_token), timeout=30)
        arr = r.json()
        if isinstance(arr, dict):
            arr = arr.get("users") or arr.get("items") or []
        assert any("demo" in (u.get("email", "") + u.get("name", "")).lower() for u in arr)


# ---- Messages pagination ----
class TestMessagesPagination:
    def _get_channel(self, tok):
        r = requests.get(f"{API}/workspaces", headers=_h(tok), timeout=30)
        assert r.status_code == 200, r.text
        wss = r.json()
        if not wss:
            pytest.skip("no workspaces")
        ws = wss[0]
        wid = ws.get("workspace_id") or ws.get("id") or ws.get("_id")
        r = requests.get(f"{API}/workspaces/{wid}/channels", headers=_h(tok), timeout=30)
        assert r.status_code == 200, r.text
        chs = r.json()
        if not chs:
            pytest.skip("no channels")
        return chs[0].get("channel_id") or chs[0].get("id") or chs[0].get("_id")

    def test_limit_and_before(self, demo_token):
        cid = self._get_channel(demo_token)
        r = requests.get(f"{API}/channels/{cid}/messages?limit=3", headers=_h(demo_token), timeout=30)
        assert r.status_code == 200, r.text
        msgs = r.json()
        assert isinstance(msgs, list)
        assert len(msgs) <= 3
        # ascending by created_at
        if len(msgs) >= 2:
            ts = [m.get("created_at") or m.get("createdAt") for m in msgs]
            assert ts == sorted(ts), f"not ascending: {ts}"
            # Now test before
            cursor = msgs[0].get("created_at") or msgs[0].get("createdAt")
            r2 = requests.get(f"{API}/channels/{cid}/messages?limit=3&before={cursor}",
                              headers=_h(demo_token), timeout=30)
            assert r2.status_code == 200, r2.text
            older = r2.json()
            for m in older:
                mt = m.get("created_at") or m.get("createdAt")
                assert mt < cursor, f"{mt} not < {cursor}"
