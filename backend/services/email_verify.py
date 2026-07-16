import os
import secrets
from datetime import datetime, timezone, timedelta
from core import db, now_iso
from services.email import send_email_detailed

_TOKEN_TTL_HOURS = 24


def _frontend():
    return os.environ.get("FRONTEND_URL", "").rstrip("/")


def _verify_html(name, link):
    return (f"<div style='font-family:-apple-system,Segoe UI,sans-serif;max-width:520px;margin:0 auto;background:#f6f6f6;padding:28px'>"
            f"<h1 style='color:#c0202e;font-size:22px;margin:0 0 8px'>Verify your email</h1>"
            f"<p style='color:#333;font-size:14px'>Hi {name or 'there'}, welcome to Stitches! Please confirm your email address to activate your account.</p>"
            f"<p style='margin:24px 0'><a href='{link}' style='background:#c0202e;color:#fff;text-decoration:none;padding:12px 24px;border-radius:10px;font-weight:600;font-size:14px'>Verify email</a></p>"
            f"<p style='color:#888;font-size:12px'>Or paste this link in your browser:<br><span style='word-break:break-all'>{link}</span></p>"
            f"<p style='color:#aaa;font-size:11px;margin-top:20px'>This link expires in {_TOKEN_TTL_HOURS} hours. If you didn't sign up, ignore this email.</p></div>")


async def create_and_send_verification(user_id, email, name=""):
    token = secrets.token_urlsafe(32)
    await db.email_verifications.delete_many({"user_id": user_id})
    await db.email_verifications.insert_one({
        "token": token, "user_id": user_id, "email": email,
        "expires_at": datetime.now(timezone.utc) + timedelta(hours=_TOKEN_TTL_HOURS),
        "created_at": now_iso()})
    link = f"{_frontend()}/verify-email?token={token}"
    ok, detail = await send_email_detailed(email, "Verify your Stitches email", _verify_html(name, link))
    return ok, detail, link


async def verify_token(token: str):
    if not token:
        return False, "Missing verification token"
    doc = await db.email_verifications.find_one({"token": token})
    if not doc:
        return False, "This verification link is invalid or has already been used."
    exp = doc.get("expires_at")
    if isinstance(exp, str):
        exp = datetime.fromisoformat(exp)
    if exp and exp.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        await db.email_verifications.delete_one({"token": token})
        return False, "This verification link has expired. Please request a new one."
    await db.users.update_one({"user_id": doc["user_id"]}, {"$set": {"email_verified": True}})
    await db.email_verifications.delete_many({"user_id": doc["user_id"]})
    return True, "Your email has been verified."
