from fastapi import APIRouter
from core import *
from core import _fernet
from services.email import get_smtp_cfg, get_user_smtp, _safe_port

router = APIRouter()


# ---------------- Per-user SMTP endpoints ----------------
@router.get("/me/smtp-config")
async def get_my_smtp(user: dict = Depends(get_current_user)):
    c = await get_user_smtp(user["user_id"]) or {"enabled": False, "host": "", "port": 587, "username": "", "from_address": "", "password": ""}
    return {"enabled": c["enabled"], "host": c["host"], "port": c["port"], "username": c["username"],
            "from_address": c["from_address"], "has_password": bool(c.get("password"))}


@router.put("/me/smtp-config")
async def set_my_smtp(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    prev = (await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "smtp": 1}) or {}).get("smtp") or {}
    pw = body.get("password", "")
    enc = _fernet.encrypt(pw.encode()).decode() if pw else prev.get("password_enc", "")
    val = {"enabled": bool(body.get("enabled")), "host": (body.get("host") or "").strip(),
           "port": _safe_port(body.get("port")), "username": (body.get("username") or "").strip(),
           "from_address": (body.get("from_address") or "").strip(), "password_enc": enc}
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"smtp": val}})
    return {"ok": True}


@router.delete("/me/smtp-config")
async def clear_my_smtp(user: dict = Depends(get_current_user)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$unset": {"smtp": ""}})
    return {"ok": True}


# ---------------- Admin SMTP endpoints ----------------
@router.get("/admin/smtp-config")
async def admin_get_smtp(user: dict = Depends(require_admin)):
    c = await get_smtp_cfg()
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
           "port": _safe_port(body.get("port")), "username": (body.get("username") or "").strip(),
           "from_address": (body.get("from_address") or "").strip(), "password_enc": enc}
    await db.settings.update_one({"key": "smtp"}, {"$set": {"key": "smtp", "value": val}}, upsert=True)
    return {"ok": True}


@router.delete("/admin/smtp-config")
async def admin_clear_smtp(user: dict = Depends(require_admin)):
    await db.settings.delete_one({"key": "smtp"})
    return {"ok": True}
