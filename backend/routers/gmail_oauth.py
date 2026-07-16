from fastapi import APIRouter, Query, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
import os
from core import db, require_admin, resolve_user_from_token, create_access_token, now_iso, log_activity
from services.gmail import (get_gmail_status, gmail_authorize_url, gmail_exchange_code,
                            disconnect_gmail, save_service_account, get_service_account_status,
                            disconnect_service_account)
from services.mailgun import (get_mailgun_admin, save_mailgun_admin, disconnect_mailgun_admin,
                              get_mailgun_user, save_mailgun_user, clear_mailgun_user,
                              verify_webhook, record_email_event, get_email_events_summary, unsuppress)
from core import get_current_user
from services.email import get_email_provider_cfg, get_smtp_cfg, get_email_health

router = APIRouter()


@router.get("/admin/email-provider")
async def admin_get_email_provider(user: dict = Depends(require_admin)):
    cfg = await get_email_provider_cfg()
    gmail = await get_gmail_status()
    sa = await get_service_account_status()
    mg = await get_mailgun_admin()
    smtp = await get_smtp_cfg()
    return {"provider": cfg["provider"], "sender": cfg["sender"], "resend_fallback": cfg["resend_fallback"],
            "gmail": gmail, "gmail_sa": sa,
            "mailgun": {"configured": bool(mg["domain"] and mg["has_api_key"]), "domain": mg["domain"],
                        "region": mg["region"], "sender": mg["sender"], "has_api_key": mg["has_api_key"],
                        "has_webhook_key": mg["has_webhook_key"]},
            "smtp": {"configured": bool(smtp["host"] and smtp["username"] and smtp["password"]),
                     "enabled": smtp["enabled"], "from_address": smtp["from_address"]},
            "resend_available": bool(os.environ.get("RESEND_API_KEY") and os.environ.get("SENDER_EMAIL"))}


@router.put("/admin/email-provider")
async def admin_set_email_provider(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    existing = await db.settings.find_one({"key": "email_provider"})
    val = (existing or {}).get("value", {})
    if body.get("provider") in ("mailgun", "gmail", "gmail_sa", "smtp"):
        val["provider"] = body["provider"]
    if "sender" in body:
        val["sender"] = (body.get("sender") or "").strip()[:200]
    if "resend_fallback" in body:
        val["resend_fallback"] = bool(body.get("resend_fallback"))
    await db.settings.update_one({"key": "email_provider"}, {"$set": {"key": "email_provider", "value": val}}, upsert=True)
    return await get_email_provider_cfg()


@router.get("/admin/mailgun-config")
async def admin_get_mailgun(user: dict = Depends(require_admin)):
    return await get_mailgun_admin()


@router.put("/admin/mailgun-config")
async def admin_set_mailgun(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    await save_mailgun_admin(body)
    return {"ok": True}


@router.delete("/admin/mailgun-config")
async def admin_clear_mailgun(user: dict = Depends(require_admin)):
    await disconnect_mailgun_admin()
    return {"ok": True}


@router.get("/me/mailgun-config")
async def get_my_mailgun(user: dict = Depends(get_current_user)):
    return await get_mailgun_user(user["user_id"])


@router.put("/me/mailgun-config")
async def set_my_mailgun(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    await save_mailgun_user(user["user_id"], body)
    return {"ok": True}


@router.delete("/me/mailgun-config")
async def clear_my_mailgun(user: dict = Depends(get_current_user)):
    await clear_mailgun_user(user["user_id"])
    return {"ok": True}


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


@router.get("/admin/email-health")
async def admin_email_health(user: dict = Depends(require_admin)):
    return await get_email_health()


@router.get("/admin/email-events")
async def admin_email_events(user: dict = Depends(require_admin)):
    summary = await get_email_events_summary()
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    summary["webhook_url"] = f"{frontend}/api/webhooks/mailgun"
    return summary


@router.post("/admin/email-events/unsuppress")
async def admin_unsuppress(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    await unsuppress((body or {}).get("email", ""))
    return {"ok": True}


@router.post("/webhooks/mailgun")
async def mailgun_webhook(request: Request):
    body = await request.json()
    sig = (body or {}).get("signature", {}) or {}
    ok = await verify_webhook(sig.get("timestamp", ""), sig.get("token", ""), sig.get("signature", ""))
    if not ok:
        raise HTTPException(status_code=406, detail="Invalid signature")
    ed = (body or {}).get("event-data", {}) or {}
    event = ed.get("event", "")
    recipient = ed.get("recipient", "")
    reason = ed.get("reason", "") or (ed.get("delivery-status", {}) or {}).get("message", "")
    if event:
        await record_email_event(event, recipient, reason)
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
