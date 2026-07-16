"""Iteration 33: email verification flow tests."""
import os
import time
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def mongo_db():
    # Read backend .env for db name
    url = MONGO_URL
    name = DB_NAME
    try:
        with open("/app/backend/.env") as f:
            for line in f:
                line = line.strip()
                if line.startswith("MONGO_URL="):
                    url = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("DB_NAME="):
                    name = line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return MongoClient(url)[name]


@pytest.fixture(scope="module")
def fresh_user():
    ts = int(time.time() * 1000)
    email = f"verify_{ts}@example.com"
    password = "Test@123"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": password, "name": "Verify User"}, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    data = r.json()
    return {"email": email, "password": password, "token": data["token"], "user": data["user"]}


def test_register_returns_unverified_and_creates_token(fresh_user, mongo_db):
    u = fresh_user["user"]
    assert u.get("email_verified") is False
    assert fresh_user["token"]
    doc = mongo_db.email_verifications.find_one({"email": fresh_user["email"]})
    assert doc is not None, "no verification token doc created"
    assert doc.get("token")


def test_verify_email_bad_token():
    r = requests.get(f"{API}/auth/verify-email", params={"token": "badtoken"}, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is False
    assert "invalid" in j["message"].lower() or "expired" in j["message"].lower()


def test_resend_verification_unverified(fresh_user):
    r = requests.post(f"{API}/auth/resend-verification",
                      headers={"Authorization": f"Bearer {fresh_user['token']}"}, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert "ok" in j and "message" in j
    # ok may be True/False (send may fail with no provider); either acceptable


def test_verify_email_happy_and_single_use(fresh_user, mongo_db):
    doc = mongo_db.email_verifications.find_one({"email": fresh_user["email"]})
    assert doc, "expected verification token in db"
    token = doc["token"]
    r = requests.get(f"{API}/auth/verify-email", params={"token": token}, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True, f"expected ok=true, got {j}"

    # confirm user is now verified
    me = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {fresh_user['token']}"}, timeout=30).json()
    assert me.get("email_verified") is True

    # single use: reuse fails
    r2 = requests.get(f"{API}/auth/verify-email", params={"token": token}, timeout=30)
    j2 = r2.json()
    assert j2["ok"] is False


def test_resend_for_already_verified(fresh_user):
    r = requests.post(f"{API}/auth/resend-verification",
                      headers={"Authorization": f"Bearer {fresh_user['token']}"}, timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["ok"] is True
    assert "already verified" in j["message"].lower()


def test_admin_user_shows_verified():
    r = requests.post(f"{API}/auth/login", json={"email": "admin@stitches.app", "password": "Admin@123"}, timeout=30)
    assert r.status_code == 200
    u = r.json()["user"]
    assert u.get("email_verified") is True
