from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
import os
from core import db, require_admin, resolve_user_from_token, create_access_token, now_iso, log_activity
from services.gmail import (get_gmail_status, gmail_authorize_url, gmail_exchange_code,
                            disconnect_gmail, save_service_account, get_service_account_status,
                            disconnect_service_account)
from services.email import get_email_provider_cfg, get_smtp_cfg

router = APIRouter()


@router.get("/admin/email-provider")
async def admin_get_email_provider(user: dict = Depends(require_admin)):
    cfg = await get_email_provider_cfg()
    gmail = await get_gmail_status()
    sa = await get_service_account_status()
    smtp = await get_smtp_cfg()
    return {"provider": cfg["provider"], "sender": cfg["sender"], "resend_fallback": cfg["resend_fallback"],
            "gmail": gmail, "gmail_sa": sa,
            "smtp": {"configured": bool(smtp["host"] and smtp["username"] and smtp["password"]),
                     "enabled": smtp["enabled"], "from_address": smtp["from_address"]},
            "resend_available": bool(os.environ.get("RESEND_API_KEY") and os.environ.get("SENDER_EMAIL"))}


@router.put("/admin/email-provider")
async def admin_set_email_provider(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    existing = await db.settings.find_one({"key": "email_provider"})
    val = (existing or {}).get("value", {})
    if body.get("provider") in ("gmail", "gmail_sa", "smtp"):
        val["provider"] = body["provider"]
    if "sender" in body:
        val["sender"] = (body.get("sender") or "").strip()[:200]
    if "resend_fallback" in body:
        val["resend_fallback"] = bool(body.get("resend_fallback"))
    await db.settings.update_one({"key": "email_provider"}, {"$set": {"key": "email_provider", "value": val}}, upsert=True)
    return await get_email_provider_cfg()


@router.put("/admin/gmail/service-account")
async def admin_set_service_account(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    sa_json = body.get("service_account_json") or ""
    if not sa_json.strip():
        raise HTTPException(status_code=400, detail="Paste the service account JSON")
    try:
        email = await save_service_account(sa_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid service account: {e}")
    return {"ok": True, "client_email": email}


@router.post("/admin/gmail/service-account/disconnect")
async def admin_disconnect_service_account(user: dict = Depends(require_admin)):
    await disconnect_service_account()
    return {"ok": True}


@router.get("/admin/gmail/authorize")
async def admin_gmail_authorize(user: dict = Depends(require_admin)):
    state = create_access_token(user["user_id"], user.get("email", ""))
    url = await gmail_authorize_url(state)
    if not url:
        raise HTTPException(status_code=400, detail="Google credentials not configured on the server.")
    return {"authorization_url": url}


@router.get("/oauth/gmail/callback")
async def gmail_callback(code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if error or not code or not state:
        return RedirectResponse(f"{frontend}/admin?gmail=error")
    user = await resolve_user_from_token(state)
    if not user or user.get("role") != "admin":
        return RedirectResponse(f"{frontend}/admin?gmail=error")
    try:
        email = await gmail_exchange_code(code)
    except Exception:
        return RedirectResponse(f"{frontend}/admin?gmail=error")
    await log_activity(user["user_id"], "gmail_connect", {"email": email})
    return RedirectResponse(f"{frontend}/admin?gmail=connected")


@router.post("/admin/gmail/disconnect")
async def admin_gmail_disconnect(user: dict = Depends(require_admin)):
    await disconnect_gmail()
    return {"ok": True}
