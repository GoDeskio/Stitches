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
    wh = _dec(val.get("webhook_key_enc"))
    return {"enabled": bool(val.get("enabled")), "domain": val.get("domain", ""),
            "region": val.get("region", "US"), "sender": val.get("sender", ""),
            "api_key": api_key if reveal else "", "has_api_key": bool(api_key),
            "webhook_signing_key": wh if reveal else "", "has_webhook_key": bool(wh)}


async def save_mailgun_admin(body: dict):
    existing = await db.settings.find_one({"key": "mailgun_config"})
    prev = (existing or {}).get("value", {})
    api_key = body.get("api_key", "")
    enc = _enc(api_key) if api_key else prev.get("api_key_enc", "")
    wh = body.get("webhook_signing_key", "")
    wh_enc = _enc(wh) if wh else prev.get("webhook_key_enc", "")
    val = {"enabled": bool(body.get("enabled", True)), "domain": (body.get("domain") or "").strip(),
           "region": (body.get("region") or "US").strip().upper(), "sender": (body.get("sender") or "").strip(),
           "api_key_enc": enc, "webhook_key_enc": wh_enc}
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


# ---------------- Webhooks / delivery analytics ----------------
import hashlib
import hmac
from datetime import datetime, timezone

_BOUNCE_EVENTS = {"failed", "bounced", "complained", "rejected"}


async def verify_webhook(timestamp: str, token: str, signature: str) -> bool:
    cfg = await get_mailgun_admin(reveal=True)
    key = cfg.get("webhook_signing_key")
    if not key or not timestamp or not token or not signature:
        return False
    computed = hmac.new(key.encode(), f"{timestamp}{token}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature)


async def record_email_event(event: str, recipient: str, reason: str = ""):
    await db.email_events.insert_one({
        "event": event, "recipient": (recipient or "").lower(), "reason": (reason or "")[:300],
        "created_at": datetime.now(timezone.utc)})
    if event in _BOUNCE_EVENTS and recipient:
        await db.suppressed_emails.update_one(
            {"email": recipient.lower()},
            {"$set": {"email": recipient.lower(), "reason": event, "detail": (reason or "")[:200],
                      "created_at": datetime.now(timezone.utc)}}, upsert=True)


async def is_suppressed(email: str) -> bool:
    return bool(await db.suppressed_emails.find_one({"email": (email or "").lower()}))


async def get_email_events_summary(limit=25):
    counts = {}
    for e in ("delivered", "opened", "clicked", "failed", "bounced", "complained"):
        counts[e] = await db.email_events.count_documents({"event": e})
    delivered = counts.get("delivered", 0)
    opened = counts.get("opened", 0)
    bounced = counts.get("failed", 0) + counts.get("bounced", 0) + counts.get("complained", 0)
    recent = await db.email_events.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    for r in recent:
        if isinstance(r.get("created_at"), datetime):
            r["created_at"] = r["created_at"].isoformat()
    suppressed = await db.suppressed_emails.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    for s in suppressed:
        if isinstance(s.get("created_at"), datetime):
            s["created_at"] = s["created_at"].isoformat()
    total = delivered + bounced
    return {"counts": counts, "delivered": delivered, "opened": opened, "bounced": bounced,
            "delivery_rate": round(delivered * 100 / total) if total else 0,
            "open_rate": round(opened * 100 / delivered) if delivered else 0,
            "recent": recent, "suppressed": suppressed}


async def unsuppress(email: str):
    await db.suppressed_emails.delete_one({"email": (email or "").lower()})


async def check_domain(cfg):
    if not (cfg.get("domain") and cfg.get("api_key")):
        return {"ok": False, "error": "Mailgun domain/API key not configured"}
    base = _base_url(cfg.get("region"))
    url = f"{base}/v4/domains/{cfg['domain']}"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(url, auth=("api", cfg["api_key"]))
        if r.status_code != 200:
            return {"ok": False, "error": f"Mailgun {r.status_code}: {r.text[:180]}"}
        d = r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    def _norm(rec):
        return {"type": rec.get("record_type", ""), "name": rec.get("name", ""),
                "value": rec.get("value", ""), "priority": rec.get("priority", ""),
                "valid": (rec.get("valid", "") or "").lower() == "valid"}

    sending = [_norm(x) for x in d.get("sending_dns_records", [])]
    receiving = [_norm(x) for x in d.get("receiving_dns_records", [])]
    state = (d.get("domain", {}) or {}).get("state", "")
    return {"ok": True, "state": state, "domain": cfg["domain"],
            "sending": sending, "receiving": receiving,
            "all_valid": all(x["valid"] for x in sending) if sending else False}
