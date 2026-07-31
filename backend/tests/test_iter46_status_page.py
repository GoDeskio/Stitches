"""Backend tests for public status page + incident notes (iteration 46)."""
import os
import requests
from dotenv import dotenv_values

frontend_env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or frontend_env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}


def _login():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _h(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


# ---- Public status page config ----
def test_public_status_when_disabled_returns_enabled_false():
    token = _login()
    # Force disable
    r = requests.put(f"{BASE_URL}/api/admin/deploy/status-page", headers=_h(token), json={"enabled": False}, timeout=15)
    assert r.status_code == 200
    r2 = requests.get(f"{BASE_URL}/api/status/public", timeout=15)
    assert r2.status_code == 200
    assert r2.json().get("enabled") is False


def test_status_page_toggle_persist_and_public_render():
    token = _login()
    # Enable + set title
    r = requests.put(f"{BASE_URL}/api/admin/deploy/status-page", headers=_h(token),
                     json={"enabled": True, "title": "TEST_Stitches Status"}, timeout=15)
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is True
    assert data["title"] == "TEST_Stitches Status"

    # Admin GET returns same
    r2 = requests.get(f"{BASE_URL}/api/admin/deploy/status-page", headers=_h(token), timeout=15)
    assert r2.status_code == 200
    assert r2.json()["enabled"] is True

    # Public endpoint (no auth)
    r3 = requests.get(f"{BASE_URL}/api/status/public", timeout=15)
    assert r3.status_code == 200
    pj = r3.json()
    assert pj["enabled"] is True
    assert pj["title"] == "TEST_Stitches Status"
    assert "groups" in pj and isinstance(pj["groups"], list) and len(pj["groups"]) == 4
    keys = [g["key"] for g in pj["groups"]]
    assert set(keys) == {"platform", "ai", "calls", "email"}
    for g in pj["groups"]:
        assert "uptime" in g and "status" in g and "strip" in g
    assert pj["overall"] in {"operational", "degraded", "outage"}


def test_public_status_no_auth_required():
    # Should return without Authorization header
    r = requests.get(f"{BASE_URL}/api/status/public", timeout=15)
    assert r.status_code == 200


# ---- Incident notes ----
def test_incident_note_flow_and_public_incidents():
    token = _login()
    # Ensure enabled
    requests.put(f"{BASE_URL}/api/admin/deploy/status-page", headers=_h(token),
                 json={"enabled": True, "title": "TEST_Stitches Status"}, timeout=15)

    # Run diagnostics to create history entry
    r0 = requests.post(f"{BASE_URL}/api/admin/deploy/diagnose", headers=_h(token), json={"autofix": False}, timeout=30)
    assert r0.status_code == 200

    # Get all alerts
    r1 = requests.get(f"{BASE_URL}/api/admin/deploy/diagnose/alerts/all", headers=_h(token), timeout=15)
    assert r1.status_code == 200
    alerts = r1.json().get("alerts", [])

    if not alerts:
        # Seed a synthetic alert via direct DB? Not accessible via API. Skip note-visibility test.
        # Instead ensure 404 on unknown alert id.
        r_missing = requests.patch(f"{BASE_URL}/api/admin/deploy/diagnose/alerts/does_not_exist/note",
                                    headers=_h(token), json={"note": "x"}, timeout=15)
        assert r_missing.status_code == 404
        return

    alert_id = alerts[0]["alert_id"]
    note_text = "TEST_incident_note_iter46"
    r2 = requests.patch(f"{BASE_URL}/api/admin/deploy/diagnose/alerts/{alert_id}/note",
                        headers=_h(token), json={"note": note_text}, timeout=15)
    assert r2.status_code == 200
    assert r2.json()["note"] == note_text

    # Verify appears in public incidents
    r3 = requests.get(f"{BASE_URL}/api/status/public", timeout=15)
    assert r3.status_code == 200
    incidents = r3.json().get("incidents", [])
    assert any(i.get("note") == note_text for i in incidents), f"Note not visible publicly: {incidents}"


def test_incident_note_missing_alert_returns_404():
    token = _login()
    r = requests.patch(f"{BASE_URL}/api/admin/deploy/diagnose/alerts/nonexistent_id/note",
                       headers=_h(token), json={"note": "x"}, timeout=15)
    assert r.status_code == 404


def test_status_page_requires_admin():
    r = requests.get(f"{BASE_URL}/api/admin/deploy/status-page", timeout=15)
    assert r.status_code in (401, 403)
    r2 = requests.put(f"{BASE_URL}/api/admin/deploy/status-page", json={"enabled": False}, timeout=15)
    assert r2.status_code in (401, 403)
