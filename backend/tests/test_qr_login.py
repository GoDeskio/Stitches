"""Tests for QR cross-device login (generate/claim)."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stitches-connect.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO = {"email": "demo@stitches.app", "password": "Demo@123"}


@pytest.fixture(scope="module")
def demo_token():
    r = requests.post(f"{API}/auth/login", json=DEMO, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_qr_generate_requires_auth():
    r = requests.post(f"{API}/auth/qr/generate", timeout=20)
    assert r.status_code == 401


def test_qr_generate_ok(demo_token):
    r = requests.post(f"{API}/auth/qr/generate",
                      headers={"Authorization": f"Bearer {demo_token}"}, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "token" in data and isinstance(data["token"], str) and len(data["token"]) > 10
    assert data.get("expires_in_seconds") == 180


def test_qr_claim_flow(demo_token):
    # generate
    g = requests.post(f"{API}/auth/qr/generate",
                      headers={"Authorization": f"Bearer {demo_token}"}, timeout=20)
    assert g.status_code == 200
    qr_token = g.json()["token"]

    # claim from "new device" (no auth header, fresh session)
    s = requests.Session()
    c = s.post(f"{API}/auth/qr/claim", json={"token": qr_token}, timeout=20)
    assert c.status_code == 200, c.text
    payload = c.json()
    assert "user" in payload and "token" in payload
    assert payload["user"]["email"] == DEMO["email"]
    access = payload["token"]
    assert isinstance(access, str) and access.count(".") == 2  # JWT

    # token works on /auth/me
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {access}"}, timeout=20)
    assert me.status_code == 200
    assert me.json()["email"] == DEMO["email"]

    # reuse -> 401
    reuse = requests.post(f"{API}/auth/qr/claim", json={"token": qr_token}, timeout=20)
    assert reuse.status_code == 401


def test_qr_claim_invalid_token():
    r = requests.post(f"{API}/auth/qr/claim", json={"token": "garbage-invalid-xxxx"}, timeout=20)
    assert r.status_code == 401


def test_qr_claim_missing_token():
    r = requests.post(f"{API}/auth/qr/claim", json={}, timeout=20)
    assert r.status_code == 400
