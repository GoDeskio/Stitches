from dotenv import load_dotenv
from pathlib import Path
import os

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, Form, Header, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, Response as FastResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import uuid
import logging
import bcrypt
import jwt
import secrets
import requests
import json
import asyncio

# ---------------- DB ----------------
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = "HS256"
APP_NAME = "stitches"
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")

logger = logging.getLogger("stitches")
logging.basicConfig(level=logging.INFO)


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ---------------- Auth helpers ----------------
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: str, email: str, jti: str = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": user_id, "email": email, "iat": now,
               "exp": now + timedelta(days=7), "type": "access"}
    if jti:
        payload["jti"] = jti
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _device_label(ua: str) -> str:
    ua = ua or ""
    low = ua.lower()
    if "iphone" in low: os_name = "iPhone"
    elif "ipad" in low: os_name = "iPad"
    elif "android" in low: os_name = "Android"
    elif "mac os" in low or "macintosh" in low: os_name = "macOS"
    elif "windows" in low: os_name = "Windows"
    elif "linux" in low: os_name = "Linux"
    else: os_name = "Unknown device"
    if "edg/" in low: browser = "Edge"
    elif "chrome" in low and "chromium" not in low: browser = "Chrome"
    elif "firefox" in low: browser = "Firefox"
    elif "safari" in low: browser = "Safari"
    elif "electron" in low or "stitches" in low: browser = "Desktop app"
    else: browser = "Browser"
    return f"{browser} on {os_name}"


async def record_session(user_id: str, jti: str, request: Request):
    ua = request.headers.get("user-agent", "") if request else ""
    ip = (request.client.host if request and request.client else "") or ""
    device = _device_label(ua)
    prior = await db.sessions.count_documents({"user_id": user_id})
    known = await db.sessions.count_documents({"user_id": user_id, "device": device, "ip": ip})
    await db.sessions.insert_one({
        "session_id": f"ses_{uuid.uuid4().hex[:12]}", "user_id": user_id, "jti": jti,
        "device": device, "user_agent": ua[:300], "ip": ip,
        "revoked": False, "created_at": now_iso(), "last_seen": now_iso()})
    if prior > 0 and known == 0:
        await create_notification(
            user_id, "security", "New sign-in to your account",
            f"A new device just signed in: {device}" + (f" · {ip}" if ip else "") + ". If this wasn't you, sign it out in Settings.",
            "/settings")


def jti_from_request(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        h = request.headers.get("Authorization", "")
        if h.startswith("Bearer "):
            token = h[7:]
    if not token:
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM]).get("jti")
    except jwt.InvalidTokenError:
        return None


def public_user(u: dict) -> dict:
    u = dict(u)
    u.pop("_id", None)
    u.pop("password_hash", None)
    u["email_verified"] = u.get("email_verified", True)
    return u


async def resolve_user_from_token(token: str) -> Optional[dict]:
    if not token:
        return None
    # Try JWT
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("type") == "access":
            user = await db.users.find_one({"user_id": payload["sub"]}, {"_id": 0})
            if user:
                sva = user.get("sessions_valid_after")
                iat = payload.get("iat")
                if sva and (not iat or int(iat) < int(sva)):
                    return None
                jti = payload.get("jti")
                if jti:
                    sess = await db.sessions.find_one({"jti": jti})
                    if sess:
                        if sess.get("revoked"):
                            return None
                        last = sess.get("last_seen")
                        stale = True
                        if last:
                            try:
                                stale = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() > 60
                            except Exception:
                                stale = True
                        if stale:
                            await db.sessions.update_one({"jti": jti}, {"$set": {"last_seen": now_iso()}})
                return user
    except jwt.InvalidTokenError:
        pass
    # Try Google session token
    session = await db.user_sessions.find_one({"session_token": token})
    if session:
        expires_at = session.get("expires_at")
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if not expires_at or expires_at > datetime.now(timezone.utc):
            user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
            if user:
                return user
    return None


async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("session_token") or request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    user = await resolve_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return public_user(user)


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def set_auth_cookie(response: Response, key: str, value: str, max_age: int):
    response.set_cookie(key=key, value=value, httponly=True, secure=True,
                        samesite="none", max_age=max_age, path="/")


DEFAULT_FEATURES = {"chat": True, "projects": True, "assets": True,
                    "integrations": True, "ai_assistant": True, "friends": True}
DEFAULT_NOTIF_PREFS = {"master": True, "workspace": True, "project": True, "friend": True, "security": True, "email": True}
DEFAULT_SEO = {"title": "Stitches — Where Ideas are Stitched together",
               "description": "A tactile neumorphic workspace for business & creative teams to chat, collaborate and share.",
               "keywords": "collaboration, workspace, chat, projects, teams, creative",
               "og_image": ""}


async def log_activity(user_id, action, meta=None):
    await db.activity_log.insert_one({
        "user_id": user_id, "action": action, "meta": meta or {},
        "created_at": now_iso()})


from cryptography.fernet import Fernet
_fernet = Fernet(os.environ["ENCRYPTION_KEY"].encode())
SECRET_FIELDS = {"api_key", "token", "access_key", "secret_key", "access_token", "password", "basic_pass"}


def encrypt_config(cfg: dict) -> dict:
    out = {}
    for k, v in (cfg or {}).items():
        if v in (None, "") or not isinstance(v, str):
            out[k] = v
        else:
            out[k] = _fernet.encrypt(v.encode()).decode()
    return out


def decrypt_config(cfg: dict) -> dict:
    out = {}
    for k, v in (cfg or {}).items():
        if isinstance(v, str) and v:
            try:
                out[k] = _fernet.decrypt(v.encode()).decode()
            except Exception:
                out[k] = v  # legacy plaintext
        else:
            out[k] = v
    return out


async def get_notif_global():
    doc = await db.settings.find_one({"key": "notifications_global"})
    prefs = dict(DEFAULT_NOTIF_PREFS)
    if doc:
        prefs.update(doc.get("value", {}))
    return prefs


async def create_notification(user_id, ntype, title, body, link=""):
    glob = await get_notif_global()
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "notification_prefs": 1})
    prefs = {**DEFAULT_NOTIF_PREFS, **((u or {}).get("notification_prefs") or {})}
    if ntype == "security":
        # security alerts bypass the master mute; only a dedicated toggle can silence them
        if not glob.get("security", True) or not prefs.get("security", True):
            return
    else:
        if not glob.get("master", True) or not glob.get(ntype, True):
            return
        if not prefs.get("master", True) or not prefs.get(ntype, True):
            return
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}", "user_id": user_id,
        "type": ntype, "title": title, "body": body, "link": link,
        "read": False, "created_at": now_iso()})
    # best-effort email delivery of the notification
    if prefs.get("email", True) and glob.get("email", True):
        try:
            full = await db.users.find_one({"user_id": user_id}, {"_id": 0, "email": 1, "name": 1})
            if full and full.get("email"):
                from services.email import send_email_detailed
                link_html = (f"<p style='margin:18px 0'><a href='{os.environ.get('FRONTEND_URL','').rstrip('/')}{link}' "
                             f"style='color:#c0202e;font-weight:600;text-decoration:none'>Open in Stitches →</a></p>") if link else ""
                html = (f"<div style='font-family:-apple-system,Segoe UI,sans-serif;max-width:520px;margin:0 auto;background:#f6f6f6;padding:28px'>"
                        f"<h2 style='color:#c0202e;font-size:18px;margin:0 0 8px'>{title}</h2>"
                        f"<p style='color:#333;font-size:14px'>{body}</p>{link_html}"
                        f"<p style='color:#aaa;font-size:11px;margin-top:20px'>You're receiving this because notifications are on. Manage them in Settings → Notifications.</p></div>")
                await send_email_detailed(full["email"], f"Stitches · {title}", html)
        except Exception as e:
            logger.warning(f"notification email failed: {e}")


async def get_feature_flags():
    doc = await db.settings.find_one({"key": "feature_flags"})
    flags = dict(DEFAULT_FEATURES)
    if doc:
        flags.update(doc.get("value", {}))
    return flags


async def ensure_feature(name):
    flags = await get_feature_flags()
    if not flags.get(name, True):
        raise HTTPException(status_code=403, detail="This feature has been disabled by the administrator")


async def get_seo_settings():
    doc = await db.settings.find_one({"key": "seo"})
    seo = dict(DEFAULT_SEO)
    if doc:
        seo.update(doc.get("value", {}))
    return seo


async def get_google_oauth_cfg():
    doc = await db.settings.find_one({"key": "google_oauth"})
    val = (doc or {}).get("value", {})
    return {
        "client_id": val.get("client_id") or os.environ.get("GOOGLE_CLIENT_ID", ""),
        "client_secret": val.get("client_secret") or os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "redirect_uri": os.environ.get("GOOGLE_DRIVE_REDIRECT_URI") or (os.environ.get("FRONTEND_URL", "").rstrip("/") + "/api/integrations/google/callback"),
    }


async def get_desktop_repo():
    doc = await db.settings.find_one({"key": "desktop_release"})
    val = (doc or {}).get("value", {})
    return (val.get("repo") or os.environ.get("DESKTOP_RELEASE_REPO", "")).strip().strip("/")


async def scan_due_reminders():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    horizon = (now + timedelta(hours=24)).date().isoformat()
    today = now.date().isoformat()
    count = 0
    cur = db.tasks.find({"status": {"$ne": "done"}, "assignee_id": {"$nin": [None, ""]},
                         "due_date": {"$nin": [None, ""], "$lte": horizon}, "reminded": {"$ne": True}})
    async for t in cur:
        overdue = t.get("due_date", "") < today
        title = "Task overdue" if overdue else "Task due soon"
        body = f"'{t.get('title')}' is {'overdue' if overdue else 'due ' + t.get('due_date', '')}"
        await create_notification(t["assignee_id"], "task_due", title, body, "/dashboard")
        await db.tasks.update_one({"task_id": t["task_id"]}, {"$set": {"reminded": True}})
        count += 1
    return count


async def scan_meeting_reminders():
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    horizon = now + timedelta(minutes=30)
    cur = db.meetings.find({"scheduled_at": {"$ne": None}})
    async for m in cur:
        try:
            base = datetime.fromisoformat(m["scheduled_at"])
        except Exception:
            continue
        rec = m.get("recurrence") or "none"
        occ = None
        if rec in ("daily", "weekly"):
            step = timedelta(days=1) if rec == "daily" else timedelta(days=7)
            o = base
            while o < now:
                o += step
            if now <= o <= horizon:
                occ = o
        else:
            if now <= base <= horizon:
                occ = base
        if not occ:
            continue
        occ_key = occ.isoformat()
        if occ_key in (m.get("reminded_occurrences") or []):
            continue
        for uid in set([m.get("host_id")] + (m.get("invitees") or [])):
            if uid:
                await create_notification(uid, "meeting", "Meeting starting soon",
                                          f"'{m.get('name')}' starts soon. Tap to join.", f"/call/{m['room_id']}")
        await db.meetings.update_one({"room_id": m["room_id"]}, {"$push": {"reminded_occurrences": occ_key}})


# ---------------- Storage ----------------
storage_key = None


def init_storage():
    global storage_key
    if storage_key:
        return storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    storage_key = resp.json()["storage_key"]
    return storage_key


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = requests.put(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key, "Content-Type": content_type},
                        data=data, timeout=120)
    resp.raise_for_status()
    return resp.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}",
                        headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")



# ---------------- Shared message helpers ----------------
async def _create_message(channel_id: str, user: dict, text: str, parent_id: str = None, mentions: list = None) -> dict:
    doc = {"message_id": f"msg_{uuid.uuid4().hex[:12]}", "channel_id": channel_id,
           "user_id": user["user_id"], "author_name": user.get("name"),
           "author_avatar": user.get("avatar"), "text": text,
           "parent_id": parent_id, "mentions": mentions or [], "created_at": now_iso()}
    await db.messages.insert_one(doc)
    doc.pop("_id", None)
    return doc


async def _notify_mentions(msg: dict, author: dict):
    for uid in (msg.get("mentions") or []):
        if uid == author["user_id"]:
            continue
        snippet = (msg.get("text") or "")[:120]
        await create_notification(uid, "mention", f"{author.get('name')} mentioned you", snippet, "/messages")


# ---------------- WebSocket manager ----------------
class WSManager:
    def __init__(self):
        self.rooms: Dict[str, List[WebSocket]] = {}

    async def connect(self, channel_id: str, ws: WebSocket):
        await ws.accept()
        self.rooms.setdefault(channel_id, []).append(ws)

    def disconnect(self, channel_id: str, ws: WebSocket):
        if channel_id in self.rooms and ws in self.rooms[channel_id]:
            self.rooms[channel_id].remove(ws)

    async def broadcast(self, channel_id: str, data: dict):
        for conn in list(self.rooms.get(channel_id, [])):
            try:
                await conn.send_json(data)
            except Exception:
                self.disconnect(channel_id, conn)


ws_manager = WSManager()


# ---------------- Call (WebRTC) signaling manager ----------------
class CallManager:
    def __init__(self):
        self.rooms: Dict[str, Dict[str, dict]] = {}

    async def connect(self, room_id, peer_id, name, user_id, ws):
        await ws.accept()
        self.rooms.setdefault(room_id, {})[peer_id] = {"ws": ws, "name": name, "user_id": user_id}

    def peers(self, room_id, exclude=None):
        return [{"peer_id": pid, "name": m["name"]} for pid, m in self.rooms.get(room_id, {}).items() if pid != exclude]

    def count(self, room_id):
        return len(self.rooms.get(room_id, {}))

    def disconnect(self, room_id, peer_id):
        r = self.rooms.get(room_id)
        if r and peer_id in r:
            del r[peer_id]
        if r is not None and not r:
            self.rooms.pop(room_id, None)

    async def send(self, room_id, peer_id, data):
        m = self.rooms.get(room_id, {}).get(peer_id)
        if m:
            try:
                await m["ws"].send_json(data)
            except Exception:
                pass

    async def broadcast(self, room_id, data, exclude=None):
        for pid, m in list(self.rooms.get(room_id, {}).items()):
            if pid == exclude:
                continue
            try:
                await m["ws"].send_json(data)
            except Exception:
                pass


call_manager = CallManager()

from models import *  # re-export models for routers


PRESENCE_WINDOW = 90


def is_online(last_seen):
    if not last_seen:
        return False
    try:
        dt = datetime.fromisoformat(last_seen)
    except Exception:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() < PRESENCE_WINDOW
