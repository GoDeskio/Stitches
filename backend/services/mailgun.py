import httpx
from fastapi.concurrency import run_in_threadpool
from core import db, _fernet


def _enc(v):
    return _fernet.encrypt(v.encode()).decode() if v else ""


def _dec(v):
    if not v:
        return ""
    try:
        return _fernet.decrypt(v.encode()).decode()
    except Exception:
        return ""


def _base_url(region):
    return "https://api.eu.mailgun.net" if (region or "").upper() == "EU" else "https://api.mailgun.net"


# ---------------- Admin (platform) Mailgun config ----------------
async def get_mailgun_admin(reveal=False):
    doc = await db.settings.find_one({"key": "mailgun_config"})
    val = (doc or {}).get("value", {})
    api_key = _dec(val.get("api_key_enc"))
    return {"enabled": bool(val.get("enabled")), "domain": val.get("domain", ""),
            "region": val.get("region", "US"), "sender": val.get("sender", ""),
            "api_key": api_key if reveal else "", "has_api_key": bool(api_key)}


async def save_mailgun_admin(body: dict):
    existing = await db.settings.find_one({"key": "mailgun_config"})
    prev = (existing or {}).get("value", {})
    api_key = body.get("api_key", "")
    enc = _enc(api_key) if api_key else prev.get("api_key_enc", "")
    val = {"enabled": bool(body.get("enabled", True)), "domain": (body.get("domain") or "").strip(),
           "region": (body.get("region") or "US").strip().upper(), "sender": (body.get("sender") or "").strip(),
           "api_key_enc": enc}
    await db.settings.update_one({"key": "mailgun_config"}, {"$set": {"key": "mailgun_config", "value": val}}, upsert=True)


async def mailgun_admin_configured():
    cfg = await get_mailgun_admin(reveal=True)
    return bool(cfg["domain"] and cfg["api_key"])


async def disconnect_mailgun_admin():
    await db.settings.delete_one({"key": "mailgun_config"})


# ---------------- Per-user Mailgun config ----------------
async def get_mailgun_user(user_id, reveal=False):
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "mailgun": 1})
    val = (u or {}).get("mailgun") or {}
    api_key = _dec(val.get("api_key_enc"))
    return {"enabled": bool(val.get("enabled")), "domain": val.get("domain", ""),
            "region": val.get("region", "US"), "sender": val.get("sender", ""),
            "api_key": api_key if reveal else "", "has_api_key": bool(api_key)}


async def save_mailgun_user(user_id, body: dict):
    prev = (await db.users.find_one({"user_id": user_id}, {"_id": 0, "mailgun": 1}) or {}).get("mailgun") or {}
    api_key = body.get("api_key", "")
    enc = _enc(api_key) if api_key else prev.get("api_key_enc", "")
    val = {"enabled": bool(body.get("enabled")), "domain": (body.get("domain") or "").strip(),
           "region": (body.get("region") or "US").strip().upper(), "sender": (body.get("sender") or "").strip(),
           "api_key_enc": enc}
    await db.users.update_one({"user_id": user_id}, {"$set": {"mailgun": val}})


async def clear_mailgun_user(user_id):
    await db.users.update_one({"user_id": user_id}, {"$unset": {"mailgun": ""}})


def _user_mailgun_complete(cfg):
    return bool(cfg and cfg.get("enabled") and cfg.get("domain") and cfg.get("api_key"))


# ---------------- Send ----------------
async def send_via_mailgun(cfg, to_email, subject, html, ics=None, sender=None):
    if not (cfg.get("domain") and cfg.get("api_key")):
        raise RuntimeError("Mailgun not configured")
    url = f"{_base_url(cfg.get('region'))}/v3/{cfg['domain']}/messages"
    data = {"from": sender or cfg.get("sender") or f"noreply@{cfg['domain']}",
            "to": to_email, "subject": subject, "html": html}
    files = [("attachment", ("invite.ics", ics.encode("utf-8"), "text/calendar"))] if ics else None
    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.post(url, auth=("api", cfg["api_key"]), data=data, files=files)
    if r.status_code != 200:
        raise RuntimeError(f"Mailgun {r.status_code}: {r.text[:200]}")
