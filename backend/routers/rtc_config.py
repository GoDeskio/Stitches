from fastapi import APIRouter
from core import *
from routers.sfu_config import _get_livekit_cfg

router = APIRouter()


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


@router.delete("/admin/rtc-config")
async def admin_clear_rtc(user: dict = Depends(require_admin)):
    await db.settings.delete_one({"key": "turn"})
    return {"ok": True}
