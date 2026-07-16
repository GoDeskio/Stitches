from fastapi import APIRouter, Response
from core import *
from core import call_manager, _create_message
from routers.smtp_config import build_ics, send_meeting_email

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
