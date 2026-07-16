import smtplib
import os
from email.message import EmailMessage
from fastapi.concurrency import run_in_threadpool
from core import db, _fernet


# ---------------- calendar (.ics) ----------------
def _fmt_ics(dt):
    return dt.strftime("%Y%m%dT%H%M%SZ")


def build_ics(start, end, summary, description, organizer, uid, recurrence="none"):
    from datetime import datetime, timezone
    stamp = datetime.now(timezone.utc)
    rrule = ""
    if recurrence == "daily":
        rrule = "RRULE:FREQ=DAILY\r\n"
    elif recurrence == "weekly":
        rrule = "RRULE:FREQ=WEEKLY\r\n"
    return ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Stitches//EN\r\nCALSCALE:GREGORIAN\r\nMETHOD:REQUEST\r\n"
            "BEGIN:VEVENT\r\n"
            f"UID:{uid}@stitches\r\nDTSTAMP:{_fmt_ics(stamp)}\r\nDTSTART:{_fmt_ics(start)}\r\nDTEND:{_fmt_ics(end)}\r\n"
            f"{rrule}"
            f"SUMMARY:{summary}\r\nDESCRIPTION:{description}\r\nORGANIZER;CN={organizer}:mailto:{organizer}\r\n"
            "STATUS:CONFIRMED\r\nSEQUENCE:0\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")


# ---------------- Email (SMTP) ----------------
def _safe_port(v, default=587):
    try:
        return int(v or default)
    except (TypeError, ValueError):
        return default


async def get_smtp_cfg():
    doc = await db.settings.find_one({"key": "smtp"})
    val = (doc or {}).get("value", {})
    pwd = ""
    if val.get("password_enc"):
        try:
            pwd = _fernet.decrypt(val["password_enc"].encode()).decode()
        except Exception:
            pwd = ""
    username = val.get("username") or os.environ.get("SMTP_USER", "")
    return {"enabled": bool(val.get("enabled")), "host": val.get("host") or os.environ.get("SMTP_HOST", ""),
            "port": _safe_port(val.get("port") or os.environ.get("SMTP_PORT")), "username": username,
            "password": pwd or os.environ.get("SMTP_PASS", ""),
            "from_address": val.get("from_address") or os.environ.get("SMTP_FROM", "") or username}


def _send_email_sync(cfg, to_email, subject, html, ics):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = cfg["from_address"]
    msg["To"] = to_email
    msg.set_content("Open this invite in an HTML-capable email client.")
    msg.add_alternative(html, subtype="html")
    if ics:
        msg.add_attachment(ics.encode("utf-8"), maintype="text", subtype="calendar",
                           params={"method": "REQUEST", "name": "invite.ics"}, filename="invite.ics")
    port = int(cfg["port"])
    if port == 465:
        with smtplib.SMTP_SSL(cfg["host"], port, timeout=20) as s:
            s.login(cfg["username"], cfg["password"]); s.send_message(msg)
    else:
        with smtplib.SMTP(cfg["host"], port, timeout=20) as s:
            s.ehlo(); s.starttls(); s.ehlo(); s.login(cfg["username"], cfg["password"]); s.send_message(msg)


async def get_user_smtp(user_id):
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "smtp": 1})
    val = (u or {}).get("smtp") or {}
    if not val:
        return None
    pwd = ""
    if val.get("password_enc"):
        try:
            pwd = _fernet.decrypt(val["password_enc"].encode()).decode()
        except Exception:
            pwd = ""
    return {"enabled": bool(val.get("enabled")), "host": val.get("host", ""), "port": _safe_port(val.get("port")),
            "username": val.get("username", ""), "password": pwd,
            "from_address": val.get("from_address") or val.get("username", "")}


def _smtp_complete(c):
    return bool(c and c.get("enabled") and c["host"] and c["username"] and c["password"] and c["from_address"])


async def _send_via_resend(to_email, subject, html, ics):
    import resend
    resend.api_key = os.environ.get("RESEND_API_KEY")
    params = {"from": os.environ.get("SENDER_EMAIL"), "to": [to_email], "subject": subject, "html": html}
    if ics:
        params["attachments"] = [{"filename": "invite.ics", "content": list(ics.encode("utf-8"))}]
    await run_in_threadpool(resend.Emails.send, params)


async def get_email_provider_cfg():
    doc = await db.settings.find_one({"key": "email_provider"})
    val = (doc or {}).get("value", {})
    return {"provider": val.get("provider") or "gmail",
            "sender": val.get("sender") or os.environ.get("SENDER_EMAIL", "") or "admin@godesk.io",
            "resend_fallback": bool(val.get("resend_fallback"))}


async def send_email_detailed(to_email, subject, html, ics=None, sender_user_id=None):
    # returns (ok: bool, detail: str)
    from services.gmail import gmail_connected, send_via_gmail

    # 1) a user sending their own invite via personal SMTP takes priority
    if sender_user_id:
        us = await get_user_smtp(sender_user_id)
        if _smtp_complete(us):
            try:
                await run_in_threadpool(_send_email_sync, us, to_email, subject, html, ics)
                return True, "Sent via your personal SMTP"
            except Exception as e:
                return False, f"Personal SMTP failed: {e}"

    cfg = await get_email_provider_cfg()
    sender = cfg["sender"]
    order = ["gmail", "smtp"] if cfg["provider"] == "gmail" else ["smtp", "gmail"]
    last = "No email provider configured (connect Gmail or SMTP in the admin Email setup)"

    for p in order:
        if p == "gmail":
            if await gmail_connected():
                try:
                    await send_via_gmail(to_email, subject, html, ics, sender=sender)
                    return True, "Sent via Gmail"
                except Exception as e:
                    last = f"Gmail failed: {e}"
        else:
            admincfg = await get_smtp_cfg()
            if _smtp_complete(admincfg):
                try:
                    await run_in_threadpool(_send_email_sync, admincfg, to_email, subject, html, ics)
                    return True, "Sent via admin SMTP"
                except Exception as e:
                    last = f"Admin SMTP failed: {e}"

    # Resend only if explicitly enabled as a fallback
    if cfg["resend_fallback"] and os.environ.get("RESEND_API_KEY") and os.environ.get("SENDER_EMAIL"):
        try:
            await _send_via_resend(to_email, subject, html, ics)
            return True, f"Sent via Resend from {os.environ.get('SENDER_EMAIL')}"
        except Exception as e:
            last = f"Resend error: {e}"

    return False, last


async def send_meeting_email(to_email, subject, html, ics=None, sender_user_id=None):
    ok, _ = await send_email_detailed(to_email, subject, html, ics, sender_user_id)
    return ok
