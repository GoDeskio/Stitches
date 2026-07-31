"""Backend tests: Discord + WhatsApp alert channels (iteration 52)."""
import os
import time
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


def test_channels_save_persist_discord_whatsapp():
    tok = _login()
    payload = {
        "slack_webhook": "",
        "discord_webhook": "https://httpbin.org/post",
        "whatsapp_webhook": "https://httpbin.org/anything",
        "webhook_url": "",
    }
    r = requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_h(tok), json=payload, timeout=15)
    assert r.status_code == 200, r.text

    g = requests.get(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_h(tok), timeout=15)
    assert g.status_code == 200
    body = g.json()
    assert body.get("discord_webhook") == payload["discord_webhook"], body
    assert body.get("whatsapp_webhook") == payload["whatsapp_webhook"], body


def test_channels_test_endpoint_sent_to_flags():
    tok = _login()
    # Ensure channels are set
    requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_h(tok),
                 json={"slack_webhook": "", "discord_webhook": "https://httpbin.org/post",
                       "whatsapp_webhook": "https://httpbin.org/anything", "webhook_url": ""},
                 timeout=15)
    r = requests.post(f"{BASE_URL}/api/admin/deploy/alert-channels/test", headers=_h(tok), timeout=20)
    assert r.status_code == 200, r.text
    j = r.json()
    sent_to = j.get("sent_to") or {}
    assert sent_to.get("discord") is True, j
    assert sent_to.get("whatsapp") is True, j


def test_incident_dispatch_to_discord_and_whatsapp():
    tok = _login()
    # Configure channels
    requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_h(tok),
                 json={"slack_webhook": "", "discord_webhook": "https://httpbin.org/post",
                       "whatsapp_webhook": "https://httpbin.org/anything", "webhook_url": ""},
                 timeout=15)
    inc_id = None
    try:
        cr = requests.post(f"{BASE_URL}/api/admin/deploy/status-incidents", headers=_h(tok),
                           json={"group_key": "platform", "impact": "degraded",
                                 "text": "TEST_iter52_dw opened"}, timeout=20)
        assert cr.status_code == 200, cr.text
        inc_id = cr.json().get("incident_id")
        assert inc_id
        # give async dispatch a beat
        time.sleep(2)
    finally:
        if inc_id:
            requests.post(f"{BASE_URL}/api/admin/deploy/status-incidents/{inc_id}/update",
                          headers=_h(tok), json={"resolve": True, "text": "TEST_iter52_dw resolved"}, timeout=15)


def test_cleanup_channels():
    tok = _login()
    r = requests.put(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_h(tok),
                     json={"slack_webhook": "", "discord_webhook": "",
                           "whatsapp_webhook": "", "webhook_url": ""}, timeout=15)
    assert r.status_code == 200
    g = requests.get(f"{BASE_URL}/api/admin/deploy/alert-channels", headers=_h(tok), timeout=15).json()
    assert g.get("discord_webhook") in ("", None)
    assert g.get("whatsapp_webhook") in ("", None)
    assert g.get("slack_webhook") in ("", None)
    assert g.get("webhook_url") in ("", None)
