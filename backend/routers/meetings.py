from fastapi import APIRouter
from core import *
from core import call_manager, _create_message, _fernet

router = APIRouter()


@router.post("/meetings")
async def create_meeting(request: Request, user: dict = Depends(get_current_user)):
    try:
        body = await request.json()
    except Exception:
        body = {}
    body = body or {}
    channel_id = body.get("channel_id")
    room_id = f"room_{uuid.uuid4().hex[:10]}"
    doc = {"room_id": room_id,
           "name": body.get("name") or f"{user.get('name', 'Stitches')}'s meeting",
           "host_id": user["user_id"], "host_name": user.get("name"),
           "channel_id": channel_id, "active": True, "created_at": now_iso()}
    await db.meetings.insert_one(doc)
    await log_activity(user["user_id"], "meeting_create", {"room_id": room_id})
    link = f"/call/{room_id}"
    if channel_id:
        base = os.environ.get("FRONTEND_URL", "").rstrip("/")
        await _create_message(channel_id, user, f"Started a video meeting — join here: {base}/call/{room_id}")
        ch = await db.channels.find_one({"channel_id": channel_id})
        if ch:
            wsdoc = await db.workspaces.find_one({"workspace_id": ch.get("workspace_id")})
            for uid in (wsdoc or {}).get("members", []):
                if uid != user["user_id"]:
                    await create_notification(uid, "meeting", f"{user.get('name')} started a meeting",
                                              f"Join the #{ch.get('name')} call now.", link)
    doc.pop("_id", None)
    doc["link"] = link
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
