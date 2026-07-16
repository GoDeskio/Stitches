"""Tests for admin email provider config, Gmail OAuth authorize, and weekly digest (Upcoming meetings)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://stitches-connect.preview.emergentagent.com"
ADMIN_EMAIL = "admin@stitches.app"
ADMIN_PASS = "Admin@123"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# -------- Email provider config --------
class TestEmailProvider:
    def test_get_email_provider_defaults(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/email-provider", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["provider"] in ("gmail", "smtp")
        assert "sender" in data
        assert "resend_fallback" in data
        assert isinstance(data["resend_fallback"], bool)
        assert "gmail" in data and "configured" in data["gmail"] and "connected" in data["gmail"]
        assert "smtp" in data and "configured" in data["smtp"]
        assert "resend_available" in data

    def test_put_email_provider_persists(self, auth_headers):
        # Set to gmail with sender + fallback off
        payload = {"provider": "gmail", "sender": "admin@godesk.io", "resend_fallback": False}
        r = requests.put(f"{BASE_URL}/api/admin/email-provider", headers=auth_headers,
                         json=payload, timeout=15)
        assert r.status_code == 200, r.text
        # Verify via GET
        g = requests.get(f"{BASE_URL}/api/admin/email-provider", headers=auth_headers, timeout=15).json()
        assert g["provider"] == "gmail"
        assert g["sender"] == "admin@godesk.io"
        assert g["resend_fallback"] is False

        # Switch to smtp
        r2 = requests.put(f"{BASE_URL}/api/admin/email-provider", headers=auth_headers,
                         json={"provider": "smtp"}, timeout=15)
        assert r2.status_code == 200
        g2 = requests.get(f"{BASE_URL}/api/admin/email-provider", headers=auth_headers, timeout=15).json()
        assert g2["provider"] == "smtp"

        # Restore gmail default
        requests.put(f"{BASE_URL}/api/admin/email-provider", headers=auth_headers,
                     json={"provider": "gmail"}, timeout=15)

    def test_email_provider_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/email-provider", timeout=15)
        assert r.status_code in (401, 403)


# -------- Gmail OAuth --------
class TestGmailOAuth:
    def test_authorize_returns_google_url(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/gmail/authorize", headers=auth_headers, timeout=15)
        assert r.status_code == 200, r.text
        url = r.json().get("authorization_url", "")
        assert "accounts.google.com" in url

    def test_authorize_requires_admin(self):
        r = requests.get(f"{BASE_URL}/api/admin/gmail/authorize", timeout=15)
        assert r.status_code in (401, 403)

    def test_disconnect_ok(self, auth_headers):
        r = requests.post(f"{BASE_URL}/api/admin/gmail/disconnect", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        assert r.json().get("ok") is True


# -------- Digest --------
class TestDigest:
    def test_preview_weekly_contains_upcoming_meetings(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/digest/preview?frequency=weekly",
                         headers=auth_headers, timeout=20)
        assert r.status_code == 200, r.text
        html = r.json().get("html", "")
        assert "Upcoming meetings" in html, "digest html missing 'Upcoming meetings' section"

    def test_history_endpoint(self, auth_headers):
        r = requests.get(f"{BASE_URL}/api/admin/digest/history", headers=auth_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        # accept either list or {items:[]}
        assert isinstance(data, (list, dict))
