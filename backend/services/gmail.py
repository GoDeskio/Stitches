import os
import base64
from email.message import EmailMessage
from datetime import datetime
import httpx
from fastapi.concurrency import run_in_threadpool
from core import db, get_google_oauth_cfg, now_iso, logger

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def gmail_redirect_uri():
    return (os.environ.get("GMAIL_REDIRECT_URI")
            or os.environ.get("FRONTEND_URL", "").rstrip("/") + "/api/oauth/gmail/callback")


def _client_config(oc):
    return {"web": {"client_id": oc["client_id"], "client_secret": oc["client_secret"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [gmail_redirect_uri()]}}


async def get_gmail_status():
    oc = await get_google_oauth_cfg()
    configured = bool(oc["client_id"] and oc["client_secret"])
    doc = await db.settings.find_one({"key": "gmail_token"})
    val = (doc or {}).get("value", {})
    return {"configured": configured, "connected": bool(val.get("refresh_token")),
            "email": val.get("email", ""), "redirect_uri": gmail_redirect_uri()}


async def gmail_authorize_url(state: str):
    from google_auth_oauthlib.flow import Flow
    oc = await get_google_oauth_cfg()
    if not (oc["client_id"] and oc["client_secret"]):
        return None
    flow = Flow.from_client_config(_client_config(oc), scopes=GMAIL_SCOPES, redirect_uri=gmail_redirect_uri())
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent", state=state)
    return url


async def gmail_exchange_code(code: str):
    import warnings
    from google_auth_oauthlib.flow import Flow
    oc = await get_google_oauth_cfg()
    flow = Flow.from_client_config(_client_config(oc), scopes=None, redirect_uri=gmail_redirect_uri())

    def _fetch():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            flow.fetch_token(code=code)
        return flow.credentials

    creds = await run_in_threadpool(_fetch)
    email = ""
    try:
        async with httpx.AsyncClient() as c:
            r = await c.get("https://www.googleapis.com/oauth2/v2/userinfo",
                            headers={"Authorization": f"Bearer {creds.token}"}, timeout=10.0)
            if r.status_code == 200:
                email = r.json().get("email", "")
    except Exception:
        pass
    val = {"access_token": creds.token, "refresh_token": creds.refresh_token or "",
           "token_uri": creds.token_uri, "client_id": creds.client_id, "client_secret": creds.client_secret,
           "scopes": list(creds.scopes or []), "expiry": creds.expiry.isoformat() if creds.expiry else "",
           "email": email, "updated_at": now_iso()}
    await db.settings.update_one({"key": "gmail_token"}, {"$set": {"key": "gmail_token", "value": val}}, upsert=True)
    return email


async def disconnect_gmail():
    await db.settings.delete_one({"key": "gmail_token"})


async def _get_creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request as GReq
    doc = await db.settings.find_one({"key": "gmail_token"})
    val = (doc or {}).get("value", {})
    if not val.get("refresh_token"):
        return None

    def _refresh():
        creds = Credentials(token=val.get("access_token") or None, refresh_token=val.get("refresh_token"),
                            token_uri=val.get("token_uri") or "https://oauth2.googleapis.com/token",
                            client_id=val.get("client_id"), client_secret=val.get("client_secret"),
                            scopes=val.get("scopes"))
        exp = val.get("expiry")
        if exp:
            try:
                creds.expiry = datetime.fromisoformat(exp).replace(tzinfo=None)
            except Exception:
                creds.expiry = None
        refreshed = False
        if not creds.token or creds.expiry is None or creds.expired:
            creds.refresh(GReq())
            refreshed = True
        return creds, refreshed

    creds, refreshed = await run_in_threadpool(_refresh)
    if refreshed:
        await db.settings.update_one({"key": "gmail_token"},
                                     {"$set": {"value.access_token": creds.token,
                                               "value.expiry": creds.expiry.isoformat() if creds.expiry else ""}})
    return creds


async def gmail_connected():
    doc = await db.settings.find_one({"key": "gmail_token"})
    return bool((doc or {}).get("value", {}).get("refresh_token"))


async def send_via_gmail(to_email, subject, html, ics=None, sender=None):
    from googleapiclient.discovery import build
    creds = await _get_creds()
    if not creds:
        raise RuntimeError("Gmail not connected")

    def _send():
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        msg = EmailMessage()
        msg["To"] = to_email
        msg["Subject"] = subject
        if sender:
            msg["From"] = sender
        msg.set_content("Open this email in an HTML-capable client.")
        msg.add_alternative(html, subtype="html")
        if ics:
            msg.add_attachment(ics.encode("utf-8"), maintype="text", subtype="calendar",
                               params={"method": "REQUEST", "name": "invite.ics"}, filename="invite.ics")
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        service.users().messages().send(userId="me", body={"raw": raw}).execute()

    await run_in_threadpool(_send)
