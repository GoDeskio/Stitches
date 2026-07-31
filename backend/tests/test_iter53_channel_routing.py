"""Iteration 53 — Per-channel routing for Deployment Center alert channels."""
import os
import time
import requests
from dotenv import dotenv_values

env = dotenv_values("/app/frontend/.env")
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or env.get("REACT_APP_BACKEND_URL")).rstrip("/")

ADMIN_EMAIL = "admin@stitches.app"
ADMIN_PASS = "Admin@123"

URL_SLACK = "https://httpbin.org/status/200"
URL_DISCORD = "https://httpbin.org/status/201"   # maintenance
URL_WHATSAPP = "https://httpbin.org/status/202"  # outages
URL_WEBHOOK = "https://httpbin.org/status/203"   # all


def _login():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def test_get_alert_channels_has_mode_fields():
    tok = _login()
    r = requests.get(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_hdr(tok), timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("slack_mode", "discord_mode", "whatsapp_mode", "webhook_mode"):
        assert k in body, f"missing {k}"
        assert body[k] in ("all", "incidents", "outages", "maintenance")


def test_put_persists_modes():
    tok = _login()
    payload = {
        "slack_webhook": "",
        "discord_webhook": URL_DISCORD, "discord_mode": "maintenance",
        "whatsapp_webhook": URL_WHATSAPP, "whatsapp_mode": "outages",
        "webhook_url": URL_WEBHOOK, "webhook_mode": "all",
    }
    r = requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_hdr(tok), json=payload, timeout=15)
    assert r.status_code == 200, r.text
    # verify persistence
    r2 = requests.get(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_hdr(tok), timeout=15)
    b = r2.json()
    assert b["discord_webhook"] == URL_DISCORD
    assert b["discord_mode"] == "maintenance"
    assert b["whatsapp_webhook"] == URL_WHATSAPP
    assert b["whatsapp_mode"] == "outages"
    assert b["webhook_url"] == URL_WEBHOOK
    assert b["webhook_mode"] == "all"


def test_invalid_mode_falls_back_to_all():
    tok = _login()
    r = requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_hdr(tok),
                     json={"webhook_url": URL_WEBHOOK, "webhook_mode": "bogus"}, timeout=15)
    assert r.status_code == 200
    b = r.json()
    assert b["webhook_mode"] == "all"


def _create_incident(tok, impact, title):
    r = requests.post(f"{BASE_URL}/api/admin/deploy/status-incidents", headers=_hdr(tok),
                      json={"title": title, "impact": impact, "message": "TEST_iter53 routing test"}, timeout=20)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _resolve_incident(tok, inc_id):
    # try common patterns
    for path in (
        f"/api/admin/deploy/status-incidents/{inc_id}/resolve",
        f"/api/admin/deploy/status-incidents/{inc_id}",
    ):
        method = "POST" if "resolve" in path else "DELETE"
        try:
            r = requests.request(method, BASE_URL + path, headers=_hdr(tok), timeout=15)
            if r.status_code < 400:
                return
        except Exception:
            pass


def test_routing_degraded_and_outage():
    tok = _login()
    # configure channels
    payload = {
        "slack_webhook": "",
        "discord_webhook": URL_DISCORD, "discord_mode": "maintenance",
        "whatsapp_webhook": URL_WHATSAPP, "whatsapp_mode": "outages",
        "webhook_url": URL_WEBHOOK, "webhook_mode": "all",
    }
    r = requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_hdr(tok), json=payload, timeout=15)
    assert r.status_code == 200

    # snapshot log size (backend.err.log carries httpx INFO lines)
    LOG_PATH = "/var/log/supervisor/backend.err.log"
    try:
        start_size = os.path.getsize(LOG_PATH)
    except OSError:
        start_size = 0

    # (a) DEGRADED — only /203 (all) should fire
    inc1 = _create_incident(tok, "degraded", "TEST_iter53 degraded")
    time.sleep(3)

    # (b) OUTAGE — /203 (all) + /202 (whatsapp outages), NOT /201
    inc2 = _create_incident(tok, "outage", "TEST_iter53 outage")
    time.sleep(4)

    with open(LOG_PATH, "rb") as f:
        f.seek(start_size)
        log = f.read().decode("utf-8", errors="ignore")

    def cnt(sub):
        return log.count(sub)

    c203 = cnt("httpbin.org/status/203")
    c202 = cnt("httpbin.org/status/202")
    c201 = cnt("httpbin.org/status/201")
    print(f"log hits -> 203(all)={c203} 202(wa-outages)={c202} 201(dc-maint)={c201}")

    # cleanup incidents best-effort
    for inc in (inc1, inc2):
        iid = inc.get("id") or inc.get("_id") or (inc.get("incident") or {}).get("id")
        if iid:
            _resolve_incident(tok, iid)

    # Assertions on log evidence
    assert c203 >= 2, f"'all' webhook should fire for both incidents, got {c203}. log tail:\n{log[-2000:]}"
    assert c202 >= 1, f"whatsapp(outages) should fire on outage, got {c202}"
    assert c201 == 0, f"discord(maintenance) must NOT fire for incidents, got {c201}"


def test_cleanup_reset_channels():
    tok = _login()
    payload = {"slack_webhook": "", "discord_webhook": "", "whatsapp_webhook": "", "webhook_url": "",
               "slack_mode": "all", "discord_mode": "all", "whatsapp_mode": "all", "webhook_mode": "all"}
    r = requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_hdr(tok), json=payload, timeout=15)
    assert r.status_code == 200
    b = requests.get(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_hdr(tok), timeout=15).json()
    for k in ("slack_webhook", "discord_webhook", "whatsapp_webhook", "webhook_url"):
        assert b[k] == ""
    for k in ("slack_mode", "discord_mode", "whatsapp_mode", "webhook_mode"):
        assert b[k] == "all"
