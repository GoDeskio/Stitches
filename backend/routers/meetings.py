import smtplib
from email.message import EmailMessage
from fastapi import APIRouter, Response
from fastapi.concurrency import run_in_threadpool
from core import *
from core import call_manager, _create_message, _fernet

router = APIRouter()


def _expand_occurrences(base_iso, recurrence, window_start, window_end, limit=60):
    from datetime import datetime, timedelta
    try:
        base = datetime.fromisoformat(base_iso)
    except Exception:
        return []
    if recurrence not in ("daily", "weekly"):
        return [base] if (window_start <= base <= window_end) else []
    step = timedelta(days=1) if recurrence == "daily" else timedelta(days=7)
    occ = base
    while occ < window_start:
        occ += step
    out = []
    while occ <= window_end and len(out) < limit:
        out.append(occ)
        occ += step
    return out


async def _invite_users(invitee_ids, host, doc, join_url):
    from datetime import datetime, timezone, timedelta
    when_txt = ""
    ics = None
    rec = doc.get("recurrence") or "none"
    rec_txt = " (repeats daily)" if rec == "daily" else (" (repeats weekly)" if rec == "weekly" else "")
    sa = doc.get("scheduled_at")
    if sa:
        try:
            start = datetime.fromisoformat(sa)
            when_txt = f" on {start.strftime('%b %d, %Y at %H:%M UTC')}{rec_txt}"
            ics = build_ics(start, start + timedelta(hours=1), doc["name"], f"Join: {join_url}", host.get("email", "stitches"), doc["room_id"], recurrence=rec)
        except Exception:
            pass
    for uid in invitee_ids:
        if uid == host["user_id"]:
            continue
        u = await db.users.find_one({"user_id": uid}, {"_id": 0, "email": 1, "name": 1})
        if not u:
            continue
        await create_notification(uid, "meeting", f"{host.get('name')} invited you to a meeting",
                                  f"{doc['name']}{when_txt}. Tap to join.", f"/call/{doc['room_id']}")
        if u.get("email"):
            html = (f"<div style='font-family:sans-serif;max-width:520px'>"
                    f"<h2 style='color:#c0202e'>{doc['name']}</h2>"
                    f"<p>{host.get('name')} invited you to a Stitches meeting{when_txt}.</p>"
                    f"<p><a href='{join_url}' style='background:#c0202e;color:#fff;padding:12px 22px;border-radius:12px;text-decoration:none;font-weight:600'>Join meeting</a></p>"
                    f"<p style='color:#888;font-size:13px'>Or open this link: {join_url}</p></div>")
            await send_meeting_email(u["email"], f"Meeting invite: {doc['name']}", html, ics, sender_user_id=host["user_id"])


@router.post("/meetings")
async def create_meeting(request: Request, user: dict = Depends(get_current_user)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    channel_id = body.get("channel_id")
    invitee_ids = body.get("invitee_ids") or []
    description = body.get("description") or ""
    recurrence = body.get("recurrence") or "none"
    if recurrence not in ("none", "daily", "weekly"):
        recurrence = "none"
    scheduled_at = body.get("scheduled_at")
    if scheduled_at:
        try:
            from datetime import datetime, timezone
            scheduled_at = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None).isoformat()
        except Exception:
            scheduled_at = None
    room_id = f"room_{uuid.uuid4().hex[:10]}"
    doc = {"room_id": room_id,
           "name": body.get("name") or f"{user.get('name', 'Stitches')}'s meeting",
           "host_id": user["user_id"], "host_name": user.get("name"),
           "channel_id": channel_id, "invitees": invitee_ids, "description": description,
           "scheduled_at": scheduled_at, "recurrence": recurrence, "active": True, "created_at": now_iso()}
    await db.meetings.insert_one(doc)
    await log_activity(user["user_id"], "meeting_create", {"room_id": room_id})
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    join_url = f"{base}/call/{room_id}"
    link = f"/call/{room_id}"
    if channel_id:
        await _create_message(channel_id, user, f"Started a video meeting — join here: {join_url}")
        ch = await db.channels.find_one({"channel_id": channel_id})
        if ch:
            wsdoc = await db.workspaces.find_one({"workspace_id": ch.get("workspace_id")})
            for uid in (wsdoc or {}).get("members", []):
                if uid != user["user_id"]:
                    await create_notification(uid, "meeting", f"{user.get('name')} started a meeting",
                                              f"Join the #{ch.get('name')} call now.", link)
    if invitee_ids:
        await _invite_users(invitee_ids, user, doc, join_url)
    doc.pop("_id", None)
    doc["link"] = link
    return doc


@router.get("/meetings/upcoming")
async def upcoming_meetings(user: dict = Depends(get_current_user)):
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window_start = now - timedelta(hours=1)
    window_end = now + timedelta(days=30)
    docs = await db.meetings.find(
        {"scheduled_at": {"$ne": None},
         "$or": [{"host_id": user["user_id"]}, {"invitees": user["user_id"]}]},
        {"_id": 0}).to_list(200)
    items = []
    for m in docs:
        rec = m.get("recurrence") or "none"
        for occ in _expand_occurrences(m["scheduled_at"], rec, window_start, window_end):
            item = dict(m)
            item["scheduled_at"] = occ.isoformat()
            item["recurrence"] = rec
            item.pop("reminded_occurrences", None)
            items.append(item)
    items.sort(key=lambda x: x["scheduled_at"])
    return items[:50]


@router.get("/meetings/{room_id}")
async def get_meeting(room_id: str, user: dict = Depends(get_current_user)):
    m = await db.meetings.find_one({"room_id": room_id}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")
    m["participants"] = call_manager.count(room_id)
    return m


@router.get("/admin/meetings")
async def admin_list_meetings(user: dict = Depends(require_admin)):
    items = await db.meetings.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    for m in items:
        m["participants"] = call_manager.count(m["room_id"])
        m["live"] = m["participants"] > 0
    return items


@router.post("/admin/meetings/{room_id}/end")
async def admin_end_meeting(room_id: str, user: dict = Depends(require_admin)):
    await call_manager.broadcast(room_id, {"type": "ended"})
    await db.meetings.update_one({"room_id": room_id}, {"$set": {"active": False}})
    return {"ok": True}


# ---------------- WebRTC / TURN configuration ----------------
async def _get_turn_cfg():
    doc = await db.settings.find_one({"key": "turn"})
    val = (doc or {}).get("value", {})
    return {
        "urls": val.get("urls") or os.environ.get("TURN_URLS", ""),
        "username": val.get("username") or os.environ.get("TURN_USERNAME", ""),
        "credential": val.get("credential") or os.environ.get("TURN_CREDENTIAL", ""),
    }


def _build_ice(turn):
    ice = [{"urls": "stun:stun.l.google.com:19302"}, {"urls": "stun:global.stun.twilio.com:3478"}]
    if turn.get("urls"):
        entry = {"urls": [u.strip() for u in turn["urls"].split(",") if u.strip()]}
        if turn.get("username"):
            entry["username"] = turn["username"]
        if turn.get("credential"):
            entry["credential"] = turn["credential"]
        ice.append(entry)
    return ice


@router.get("/rtc/config")
async def rtc_config(user: dict = Depends(get_current_user)):
    lk = await _get_livekit_cfg()
    sfu_on = lk["enabled"] and bool(lk["url"] and lk["api_key"] and lk["api_secret"])
    return {"iceServers": _build_ice(await _get_turn_cfg()), "sfu": {"enabled": sfu_on, "url": lk["url"] if sfu_on else ""}}


# ---------------- Self-hosted SFU (LiveKit) ----------------
async def _get_livekit_cfg():
    doc = await db.settings.find_one({"key": "livekit"})
    val = (doc or {}).get("value", {})
    secret = ""
    if val.get("api_secret_enc"):
        try:
            secret = _fernet.decrypt(val["api_secret_enc"].encode()).decode()
        except Exception:
            secret = ""
    return {
        "enabled": bool(val.get("enabled")) if val else (os.environ.get("LIVEKIT_ENABLED", "false").lower() == "true"),
        "url": val.get("url") or os.environ.get("LIVEKIT_URL", ""),
        "api_key": val.get("api_key") or os.environ.get("LIVEKIT_API_KEY", ""),
        "api_secret": secret or os.environ.get("LIVEKIT_API_SECRET", ""),
    }


@router.post("/rtc/sfu-token")
async def sfu_token(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    room = (body or {}).get("room_id")
    if not room:
        raise HTTPException(status_code=400, detail="Missing room_id")
    lk = await _get_livekit_cfg()
    if not (lk["enabled"] and lk["url"] and lk["api_key"] and lk["api_secret"]):
        raise HTTPException(status_code=400, detail="SFU is not enabled")
    from livekit import api as lkapi
    from datetime import timedelta
    token = (lkapi.AccessToken(lk["api_key"], lk["api_secret"])
             .with_identity(user["user_id"]).with_name(user.get("name", "Guest"))
             .with_grants(lkapi.VideoGrants(room_join=True, room=room))
             .with_ttl(timedelta(hours=6)).to_jwt())
    return {"token": token, "url": lk["url"]}


@router.get("/admin/sfu-config")
async def admin_get_sfu(user: dict = Depends(require_admin)):
    lk = await _get_livekit_cfg()
    return {"enabled": lk["enabled"], "url": lk["url"], "api_key": lk["api_key"], "has_secret": bool(lk["api_secret"])}


@router.put("/admin/sfu-config")
async def admin_set_sfu(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    existing = await db.settings.find_one({"key": "livekit"})
    prev = (existing or {}).get("value", {})
    secret = body.get("api_secret", "")
    enc = _fernet.encrypt(secret.encode()).decode() if secret else prev.get("api_secret_enc", "")
    val = {"enabled": bool(body.get("enabled")), "url": (body.get("url") or "").strip(),
           "api_key": (body.get("api_key") or "").strip(), "api_secret_enc": enc}
    await db.settings.update_one({"key": "livekit"}, {"$set": {"key": "livekit", "value": val}}, upsert=True)
    return {"ok": True}


# ---------------- Email (SMTP) + calendar (.ics) ----------------
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


async def _get_smtp_cfg():
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
            "port": int(val.get("port") or os.environ.get("SMTP_PORT", 587)), "username": username,
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


async def _get_user_smtp(user_id):
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
    return {"enabled": bool(val.get("enabled")), "host": val.get("host", ""), "port": int(val.get("port") or 587),
            "username": val.get("username", ""), "password": pwd,
            "from_address": val.get("from_address") or val.get("username", "")}


def _smtp_complete(c):
    return bool(c and c.get("enabled") and c["host"] and c["username"] and c["password"] and c["from_address"])


async def send_meeting_email(to_email, subject, html, ics=None, sender_user_id=None):
    cfg = None
    if sender_user_id:
        us = await _get_user_smtp(sender_user_id)
        if _smtp_complete(us):
            cfg = us
    if not cfg:
        admincfg = await _get_smtp_cfg()
        if _smtp_complete(admincfg):
            cfg = admincfg
    if not cfg:
        return False
    try:
        await run_in_threadpool(_send_email_sync, cfg, to_email, subject, html, ics)
        return True
    except Exception:
        return False


@router.get("/me/smtp-config")
async def get_my_smtp(user: dict = Depends(get_current_user)):
    c = await _get_user_smtp(user["user_id"]) or {"enabled": False, "host": "", "port": 587, "username": "", "from_address": "", "password": ""}
    return {"enabled": c["enabled"], "host": c["host"], "port": c["port"], "username": c["username"],
            "from_address": c["from_address"], "has_password": bool(c.get("password"))}


@router.put("/me/smtp-config")
async def set_my_smtp(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    prev = (await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "smtp": 1}) or {}).get("smtp") or {}
    pw = body.get("password", "")
    enc = _fernet.encrypt(pw.encode()).decode() if pw else prev.get("password_enc", "")
    val = {"enabled": bool(body.get("enabled")), "host": (body.get("host") or "").strip(),
           "port": int(body.get("port") or 587), "username": (body.get("username") or "").strip(),
           "from_address": (body.get("from_address") or "").strip(), "password_enc": enc}
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"smtp": val}})
    return {"ok": True}


@router.delete("/me/smtp-config")
async def clear_my_smtp(user: dict = Depends(get_current_user)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$unset": {"smtp": ""}})
    return {"ok": True}


@router.delete("/admin/smtp-config")
async def admin_clear_smtp(user: dict = Depends(require_admin)):
    await db.settings.delete_one({"key": "smtp"})
    return {"ok": True}


@router.delete("/admin/sfu-config")
async def admin_clear_sfu(user: dict = Depends(require_admin)):
    await db.settings.delete_one({"key": "livekit"})
    return {"ok": True}


@router.delete("/admin/rtc-config")
async def admin_clear_rtc(user: dict = Depends(require_admin)):
    await db.settings.delete_one({"key": "turn"})
    return {"ok": True}


@router.get("/meetings/{room_id}/ics")
async def meeting_ics(room_id: str, user: dict = Depends(get_current_user)):
    from datetime import datetime, timezone, timedelta
    m = await db.meetings.find_one({"room_id": room_id}, {"_id": 0})
    if not m:
        raise HTTPException(status_code=404, detail="Meeting not found")
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    join = f"{base}/call/{room_id}"
    sa = m.get("scheduled_at")
    start = datetime.fromisoformat(sa) if sa else datetime.now(timezone.utc).replace(tzinfo=None)
    ics = build_ics(start, start + timedelta(hours=1), m.get("name", "Stitches meeting"), f"Join: {join}", m.get("host_name", "stitches"), room_id, recurrence=m.get("recurrence") or "none")
    return Response(content=ics, media_type="text/calendar",
                    headers={"Content-Disposition": f"attachment; filename=stitches-{room_id}.ics"})


@router.get("/admin/smtp-config")
async def admin_get_smtp(user: dict = Depends(require_admin)):
    c = await _get_smtp_cfg()
    return {"enabled": c["enabled"], "host": c["host"], "port": c["port"],
            "username": c["username"], "from_address": c["from_address"], "has_password": bool(c["password"])}


@router.put("/admin/smtp-config")
async def admin_set_smtp(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    existing = await db.settings.find_one({"key": "smtp"})
    prev = (existing or {}).get("value", {})
    pw = body.get("password", "")
    enc = _fernet.encrypt(pw.encode()).decode() if pw else prev.get("password_enc", "")
    val = {"enabled": bool(body.get("enabled")), "host": (body.get("host") or "").strip(),
           "port": int(body.get("port") or 587), "username": (body.get("username") or "").strip(),
           "from_address": (body.get("from_address") or "").strip(), "password_enc": enc}
    await db.settings.update_one({"key": "smtp"}, {"$set": {"key": "smtp", "value": val}}, upsert=True)
    return {"ok": True}


@router.get("/admin/rtc-config")
async def admin_get_rtc(user: dict = Depends(require_admin)):
    t = await _get_turn_cfg()
    return {"urls": t.get("urls", ""), "username": t.get("username", ""), "has_credential": bool(t.get("credential"))}


@router.put("/admin/rtc-config")
async def admin_set_rtc(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    existing = await db.settings.find_one({"key": "turn"})
    prev = (existing or {}).get("value", {})
    cred = body.get("credential", "")
    urls = (body.get("urls") or "").strip()
    val = {"urls": urls,
           "username": (body.get("username") or "").strip(),
           "credential": ("" if not urls else (cred if cred else prev.get("credential", "")))}
    await db.settings.update_one({"key": "turn"}, {"$set": {"key": "turn", "value": val}}, upsert=True)
    return {"ok": True}
