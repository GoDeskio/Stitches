"""Backend tests for site-wide heatmap tracking + admin endpoints."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, pwd):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pwd}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login("admin@stitches.app", "Admin@123")


@pytest.fixture(scope="module")
def demo_token():
    return _login("demo@stitches.app", "Demo@123")


def test_track_public_no_auth():
    """POST /track works without authentication."""
    payload = {
        "visitor_id": "v_test_pytest",
        "events": [
            {"type": "view", "path": "/dashboard"},
            {"type": "click", "path": "/dashboard", "x": 0.25, "y": 0.5, "label": "TEST_pytest_btn"},
            {"type": "click", "path": "/dashboard", "x": 0.5, "y": 0.6, "label": "TEST_pytest_btn"},
            {"type": "click", "path": "/messages", "x": 0.75, "y": 0.4, "label": "TEST_msg_btn"},
        ],
    }
    r = requests.post(f"{API}/track", json=payload, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert j["stored"] == 4


def test_track_invalid_type_ignored():
    r = requests.post(f"{API}/track", json={"visitor_id": "v_x", "events": [{"type": "hover", "path": "/"}]}, timeout=10)
    assert r.status_code == 200
    assert r.json()["stored"] == 0


def test_heatmap_paths_requires_admin(demo_token):
    r = requests.get(f"{API}/admin/heatmap/paths",
                     headers={"Authorization": f"Bearer {demo_token}"}, timeout=15)
    assert r.status_code == 403


def test_heatmap_clicks_requires_admin(demo_token):
    r = requests.get(f"{API}/admin/heatmap/clicks?path=/dashboard",
                     headers={"Authorization": f"Bearer {demo_token}"}, timeout=15)
    assert r.status_code == 403


def test_heatmap_paths_shape(admin_token):
    r = requests.get(f"{API}/admin/heatmap/paths",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    j = r.json()
    for k in ("paths", "visitors", "total_clicks", "total_views"):
        assert k in j
    assert isinstance(j["paths"], list)
    # Should include /dashboard because of test_track_public_no_auth above
    paths = [p["path"] for p in j["paths"]]
    assert "/dashboard" in paths
    assert j["total_clicks"] >= 3
    assert j["total_views"] >= 1


def test_heatmap_clicks_shape(admin_token):
    r = requests.get(f"{API}/admin/heatmap/clicks",
                     params={"path": "/dashboard"},
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    j = r.json()
    assert set(j.keys()) >= {"points", "top_elements", "count"}
    assert isinstance(j["points"], list)
    assert isinstance(j["top_elements"], list)
    assert j["count"] == len(j["points"])
    # Should include our TEST_pytest_btn
    labels = [t["label"] for t in j["top_elements"]]
    assert any("TEST_pytest_btn" in l for l in labels)
    # Points x/y in [0,1]
    for p in j["points"][:20]:
        assert 0.0 <= p["x"] <= 1.0
        assert 0.0 <= p["y"] <= 1.0


def test_admin_heatmap_grid(admin_token):
    r = requests.get(f"{API}/admin/heatmap",
                     headers={"Authorization": f"Bearer {admin_token}"}, timeout=15)
    assert r.status_code == 200
    grid = r.json()["grid"]
    assert len(grid) == 7 and all(len(row) == 24 for row in grid)
