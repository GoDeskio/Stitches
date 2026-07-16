"""Iteration 34: CRM backend tests + Email tab split verification."""
import os
import time
import uuid
import requests
import pytest
from pathlib import Path

# Load backend URL from frontend/.env
env_path = Path("/app/frontend/.env")
BASE_URL = None
for line in env_path.read_text().splitlines():
    if line.startswith("REACT_APP_BACKEND_URL"):
        BASE_URL = line.split("=", 1)[1].strip().strip('"').strip("'").rstrip("/")
        break
assert BASE_URL, "REACT_APP_BACKEND_URL missing"

ADMIN = {"email": "admin@stitches.app", "password": "Admin@123"}


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=ADMIN, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="module")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ------------- Public lead capture -------------
def test_public_lead_capture_creates():
    email = f"lead_{uuid.uuid4().hex[:10]}@example.com"
    r = requests.post(f"{BASE_URL}/api/leads",
                      json={"name": "Jane", "email": email, "company": "Acme",
                            "source": "hero_form", "message": "Interested in demo"},
                      timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert not body.get("duplicate")


def test_public_lead_duplicate_returns_duplicate_flag():
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    r1 = requests.post(f"{BASE_URL}/api/leads", json={"email": email, "name": "A"}, timeout=15)
    assert r1.status_code == 200 and r1.json().get("ok") is True
    r2 = requests.post(f"{BASE_URL}/api/leads", json={"email": email, "name": "B"}, timeout=15)
    assert r2.status_code == 200
    j = r2.json()
    assert j.get("ok") is True and j.get("duplicate") is True


def test_public_lead_invalid_email_400():
    r = requests.post(f"{BASE_URL}/api/leads", json={"email": "not-an-email", "name": "X"}, timeout=15)
    assert r.status_code == 400


# ------------- Admin auth guard -------------
def test_crm_endpoints_require_admin():
    for path in ["/api/admin/crm/stats", "/api/admin/crm/contacts"]:
        r = requests.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code in (401, 403), f"{path} => {r.status_code}"
    r = requests.post(f"{BASE_URL}/api/admin/crm/sync-users", timeout=15)
    assert r.status_code in (401, 403)


# ------------- Sync users idempotency -------------
def test_sync_users_idempotent(h):
    r1 = requests.post(f"{BASE_URL}/api/admin/crm/sync-users", headers=h, timeout=30)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["ok"] is True
    assert isinstance(d1["total_users"], int)
    # second call should add 0
    r2 = requests.post(f"{BASE_URL}/api/admin/crm/sync-users", headers=h, timeout=30)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["added"] == 0
    assert d2["total_users"] == d1["total_users"]


# ------------- Stats -------------
def test_crm_stats_shape(h):
    r = requests.get(f"{BASE_URL}/api/admin/crm/stats", headers=h, timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ("visitors", "leads", "users", "customers", "by_stage",
              "visitor_to_lead", "lead_to_customer"):
        assert k in d, f"missing {k}"
    for s in ("new", "contacted", "qualified", "proposal", "won", "lost"):
        assert s in d["by_stage"]


# ------------- Contacts list with filters + pagination -------------
def test_contacts_list_filters_and_pagination(h):
    r = requests.get(f"{BASE_URL}/api/admin/crm/contacts", headers=h,
                     params={"type": "user", "page": 1}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    for k in ("contacts", "total", "page", "pages"):
        assert k in d
    assert d["page"] == 1
    for c in d["contacts"]:
        assert c.get("type") == "user"
        assert "_id" not in c  # ObjectId excluded


# ------------- Create / update / notes / delete lifecycle -------------
def test_contact_lifecycle(h):
    email = f"crm_{uuid.uuid4().hex[:10]}@example.com"
    # CREATE
    r = requests.post(f"{BASE_URL}/api/admin/crm/contacts", headers=h,
                      json={"email": email, "name": "Lifecycle Test", "company": "Co"}, timeout=15)
    assert r.status_code == 200, r.text
    c = r.json()
    cid = c["contact_id"]
    assert c["email"] == email
    assert c["stage"] == "new"

    # DUPLICATE => 400
    r_dup = requests.post(f"{BASE_URL}/api/admin/crm/contacts", headers=h,
                          json={"email": email, "name": "dup"}, timeout=15)
    assert r_dup.status_code == 400

    # MISSING EMAIL => 400
    r_bad = requests.post(f"{BASE_URL}/api/admin/crm/contacts", headers=h,
                          json={"name": "no-email"}, timeout=15)
    assert r_bad.status_code == 400

    # UPDATE stage
    r_u = requests.put(f"{BASE_URL}/api/admin/crm/contacts/{cid}", headers=h,
                       json={"stage": "qualified", "company": "NewCo"}, timeout=15)
    assert r_u.status_code == 200
    assert r_u.json()["stage"] == "qualified"

    # GET verify persistence
    r_g = requests.get(f"{BASE_URL}/api/admin/crm/contacts/{cid}", headers=h, timeout=15)
    assert r_g.status_code == 200
    assert r_g.json()["stage"] == "qualified"
    assert r_g.json()["company"] == "NewCo"

    # NOTES
    r_n = requests.post(f"{BASE_URL}/api/admin/crm/contacts/{cid}/notes", headers=h,
                       json={"text": "Called and left VM"}, timeout=15)
    assert r_n.status_code == 200
    assert r_n.json()["text"] == "Called and left VM"

    r_g2 = requests.get(f"{BASE_URL}/api/admin/crm/contacts/{cid}", headers=h, timeout=15)
    notes = r_g2.json().get("notes", [])
    assert any(n["text"] == "Called and left VM" for n in notes)

    # DELETE
    r_d = requests.delete(f"{BASE_URL}/api/admin/crm/contacts/{cid}", headers=h, timeout=15)
    assert r_d.status_code == 200
    r_g3 = requests.get(f"{BASE_URL}/api/admin/crm/contacts/{cid}", headers=h, timeout=15)
    assert r_g3.status_code == 404
