from fastapi import APIRouter
from core import *
from core import call_manager

router = APIRouter()


@router.post("/meetings")
async def create_meeting(request: Request, user: dict = Depends(get_current_user)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    room_id = f"room_{uuid.uuid4().hex[:10]}"
    doc = {"room_id": room_id,
           "name": (body or {}).get("name") or f"{user.get('name', 'Stitches')}'s meeting",
           "host_id": user["user_id"], "host_name": user.get("name"),
           "active": True, "created_at": now_iso()}
    await db.meetings.insert_one(doc)
    await log_activity(user["user_id"], "meeting_create", {"room_id": room_id})
    doc.pop("_id", None)
    return doc


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
    return {"iceServers": _build_ice(await _get_turn_cfg())}


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
    val = {"urls": (body.get("urls") or "").strip(),
           "username": (body.get("username") or "").strip(),
           "credential": cred if cred else prev.get("credential", "")}
    await db.settings.update_one({"key": "turn"}, {"$set": {"key": "turn", "value": val}}, upsert=True)
    return {"ok": True}
