from fastapi import APIRouter
from core import *
from core import _fernet
from services.livekit import get_livekit_cfg

router = APIRouter()


@router.post("/rtc/sfu-token")
async def sfu_token(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    room = (body or {}).get("room_id")
    if not room:
        raise HTTPException(status_code=400, detail="Missing room_id")
    lk = await get_livekit_cfg()
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
    lk = await get_livekit_cfg()
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


@router.delete("/admin/sfu-config")
async def admin_clear_sfu(user: dict = Depends(require_admin)):
    await db.settings.delete_one({"key": "livekit"})
    return {"ok": True}
