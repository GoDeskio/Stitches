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

app = FastAPI()
api_router = APIRouter(prefix="/api")
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


def create_access_token(user_id: str, email: str) -> str:
    payload = {"sub": user_id, "email": email,
               "exp": datetime.now(timezone.utc) + timedelta(days=7), "type": "access"}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def public_user(u: dict) -> dict:
    u = dict(u)
    u.pop("_id", None)
    u.pop("password_hash", None)
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
DEFAULT_SEO = {"title": "Stitches — Where Ideas are Stitched together",
               "description": "A tactile neumorphic workspace for business & creative teams to chat, collaborate and share.",
               "keywords": "collaboration, workspace, chat, projects, teams, creative",
               "og_image": ""}


async def log_activity(user_id, action, meta=None):
    await db.activity_log.insert_one({
        "user_id": user_id, "action": action, "meta": meta or {},
        "created_at": now_iso()})


async def create_notification(user_id, ntype, title, body, link=""):
    await db.notifications.insert_one({
        "notification_id": f"ntf_{uuid.uuid4().hex[:12]}", "user_id": user_id,
        "type": ntype, "title": title, "body": body, "link": link,
        "read": False, "created_at": now_iso()})


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


# ---------------- Models ----------------
class RegisterInput(BaseModel):
    email: EmailStr
    password: str
    name: str


class LoginInput(BaseModel):
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    company: Optional[str] = None
    company_role: Optional[str] = None
    bio: Optional[str] = None
    avatar: Optional[str] = None
    project_info: Optional[str] = None
    theme: Optional[str] = None
    ui_scale: Optional[float] = None


class WorkspaceInput(BaseModel):
    name: str
    description: Optional[str] = ""
    icon: Optional[str] = None


class InviteInput(BaseModel):
    email: EmailStr


class ChannelInput(BaseModel):
    workspace_id: str
    name: str
    type: Optional[str] = "channel"
    description: Optional[str] = ""


class MessageInput(BaseModel):
    channel_id: str
    text: str


class ProjectInput(BaseModel):
    name: str
    description: Optional[str] = ""
    status: Optional[str] = "active"
    workspace_id: Optional[str] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class IntegrationInput(BaseModel):
    type: str
    name: str
    config: Dict[str, Any] = {}


class AiInput(BaseModel):
    message: str
    model: Optional[str] = "gpt-5.4"
    provider: Optional[str] = "openai"
    conversation_id: Optional[str] = None


class SeoInput(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[str] = None
    og_image: Optional[str] = None


class FeatureFlagsInput(BaseModel):
    flags: Dict[str, bool]


class SetPasswordInput(BaseModel):
    password: str


class UserAdminUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class EmailInput(BaseModel):
    email: EmailStr


class UserIdInput(BaseModel):
    user_id: str


# ---------------- Auth Routes ----------------
@api_router.post("/auth/register")
async def register(data: RegisterInput, response: Response):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id, "email": email, "name": data.name,
        "password_hash": hash_password(data.password), "role": "user",
        "username": email.split("@")[0], "avatar": None, "phone": "", "address": "",
        "company": "", "company_role": "", "bio": "", "project_info": "",
        "theme": "dark", "ui_scale": 1.0, "auth_provider": "password",
        "is_active": True, "friends": [],
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    token = create_access_token(user_id, email)
    set_auth_cookie(response, "access_token", token, 604800)
    await log_activity(user_id, "register")
    return {"user": public_user(doc), "token": token}


@api_router.post("/auth/login")
async def login(data: LoginInput, response: Response, request: Request):
    email = data.email.lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if isinstance(locked_until, str):
            locked_until = datetime.fromisoformat(locked_until)
        if locked_until and locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(data.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("is_active") is False:
        raise HTTPException(status_code=403, detail="Your account has been disabled by an administrator")
    await db.login_attempts.delete_one({"identifier": identifier})
    token = create_access_token(user["user_id"], email)
    set_auth_cookie(response, "access_token", token, 604800)
    await log_activity(user["user_id"], "login")
    return {"user": public_user(user), "token": token}


@api_router.post("/auth/google/session")
async def google_session(request: Request, response: Response):
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    resp = requests.get("https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
                        headers={"X-Session-ID": session_id}, timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    d = resp.json()
    email = d["email"].lower()
    user = await db.users.find_one({"email": email})
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id, "email": email, "name": d.get("name", email),
            "role": "user", "username": email.split("@")[0], "avatar": d.get("picture"),
            "phone": "", "address": "", "company": "", "company_role": "", "bio": "",
            "project_info": "", "theme": "dark", "ui_scale": 1.0, "auth_provider": "google",
            "is_active": True, "friends": [],
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
    session_token = d.get("session_token") or secrets.token_urlsafe(32)
    await db.user_sessions.insert_one({
        "user_id": user["user_id"], "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": now_iso(),
    })
    set_auth_cookie(response, "session_token", session_token, 604800)
    return {"user": public_user(user), "token": session_token}


@api_router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@api_router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# ---------------- User / Profile ----------------
@api_router.put("/users/me")
async def update_profile(data: ProfileUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return public_user(fresh)


@api_router.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users


# ---------------- Workspaces ----------------
@api_router.get("/workspaces")
async def list_workspaces(user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find({"members": user["user_id"]}, {"_id": 0}).to_list(200)
    return ws


@api_router.post("/workspaces")
async def create_workspace(data: WorkspaceInput, user: dict = Depends(get_current_user)):
    ws_id = f"ws_{uuid.uuid4().hex[:12]}"
    doc = {"workspace_id": ws_id, "name": data.name, "description": data.description,
           "icon": data.icon, "owner_id": user["user_id"], "members": [user["user_id"]],
           "created_at": now_iso()}
    await db.workspaces.insert_one(doc)
    for cname in ["general", "random"]:
        await db.channels.insert_one({
            "channel_id": f"ch_{uuid.uuid4().hex[:12]}", "workspace_id": ws_id,
            "name": cname, "type": "channel", "description": "",
            "created_at": now_iso()})
    doc.pop("_id", None)
    return doc


@api_router.post("/workspaces/{workspace_id}/join")
async def join_workspace(workspace_id: str, user: dict = Depends(get_current_user)):
    await db.workspaces.update_one({"workspace_id": workspace_id},
                                   {"$addToSet": {"members": user["user_id"]}})
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@api_router.get("/workspaces/{workspace_id}/members")
async def workspace_members(workspace_id: str, user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    members = await db.users.find({"user_id": {"$in": ws.get("members", [])}},
                                  {"_id": 0, "password_hash": 0}).to_list(500)
    for m in members:
        m["is_owner"] = m["user_id"] == ws.get("owner_id")
    return members


@api_router.post("/workspaces/{workspace_id}/invite")
async def invite_member(workspace_id: str, data: InviteInput, user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    invitee = await db.users.find_one({"email": data.email.lower()})
    if not invitee:
        raise HTTPException(status_code=404, detail="No Stitches user found with that email")
    if invitee["user_id"] in ws.get("members", []):
        raise HTTPException(status_code=400, detail="User is already a member")
    await db.workspaces.update_one({"workspace_id": workspace_id},
                                   {"$addToSet": {"members": invitee["user_id"]}})
    await create_notification(invitee["user_id"], "workspace", "Added to a workspace",
                              f"{user.get('name')} added you to '{ws.get('name')}'", "/messages")
    return {"ok": True, "member": public_user(invitee)}


# ---------------- Channels ----------------
@api_router.get("/workspaces/{workspace_id}/channels")
async def list_channels(workspace_id: str, user: dict = Depends(get_current_user)):
    chs = await db.channels.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(200)
    return chs


@api_router.post("/channels")
async def create_channel(data: ChannelInput, user: dict = Depends(get_current_user)):
    ch_id = f"ch_{uuid.uuid4().hex[:12]}"
    doc = {"channel_id": ch_id, "workspace_id": data.workspace_id, "name": data.name,
           "type": data.type, "description": data.description, "created_at": now_iso()}
    await db.channels.insert_one(doc)
    doc.pop("_id", None)
    return doc


# ---------------- Messages ----------------
@api_router.get("/channels/{channel_id}/messages")
async def get_messages(channel_id: str, user: dict = Depends(get_current_user)):
    msgs = await db.messages.find({"channel_id": channel_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return msgs


async def _create_message(channel_id: str, user: dict, text: str) -> dict:
    doc = {"message_id": f"msg_{uuid.uuid4().hex[:12]}", "channel_id": channel_id,
           "user_id": user["user_id"], "author_name": user.get("name"),
           "author_avatar": user.get("avatar"), "text": text, "created_at": now_iso()}
    await db.messages.insert_one(doc)
    doc.pop("_id", None)
    return doc


@api_router.post("/messages")
async def post_message(data: MessageInput, user: dict = Depends(get_current_user)):
    await ensure_feature("chat")
    doc = await _create_message(data.channel_id, user, data.text)
    await ws_manager.broadcast(data.channel_id, {"type": "message", "message": doc})
    await log_activity(user["user_id"], "message", {"channel_id": data.channel_id})
    return doc


# ---------------- WebSocket for realtime ----------------
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


@app.websocket("/api/ws/{channel_id}")
async def websocket_endpoint(websocket: WebSocket, channel_id: str, token: str = Query(None)):
    user = await resolve_user_from_token(token) if token else None
    if not user:
        await websocket.close(code=1008)
        return
    await ws_manager.connect(channel_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            text = data.get("text", "").strip()
            if text:
                msg = await _create_message(channel_id, public_user(user), text)
                await ws_manager.broadcast(channel_id, {"type": "message", "message": msg})
    except WebSocketDisconnect:
        ws_manager.disconnect(channel_id, websocket)
    except Exception:
        ws_manager.disconnect(channel_id, websocket)


# ---------------- Projects ----------------
@api_router.get("/projects")
async def list_projects(user: dict = Depends(get_current_user)):
    projs = await db.projects.find({"members": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return projs


@api_router.post("/projects")
async def create_project(data: ProjectInput, user: dict = Depends(get_current_user)):
    await ensure_feature("projects")
    doc = {"project_id": f"proj_{uuid.uuid4().hex[:12]}", "name": data.name,
           "description": data.description, "status": data.status,
           "workspace_id": data.workspace_id, "owner_id": user["user_id"],
           "members": [user["user_id"]], "created_at": now_iso()}
    await db.projects.insert_one(doc)
    await log_activity(user["user_id"], "project_create", {"name": data.name})
    doc.pop("_id", None)
    return doc


@api_router.put("/projects/{project_id}")
async def update_project(project_id: str, data: ProjectUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        await db.projects.update_one({"project_id": project_id}, {"$set": updates})
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    return p


@api_router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    await db.projects.delete_one({"project_id": project_id, "owner_id": user["user_id"]})
    return {"ok": True}


# ---------------- Assets / Files ----------------
@api_router.post("/assets/upload")
async def upload_asset(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    await ensure_feature("assets")
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "bin"
    path = f"{APP_NAME}/uploads/{user['user_id']}/{uuid.uuid4()}.{ext}"
    data = await file.read()
    result = put_object(path, data, file.content_type or "application/octet-stream")
    doc = {"asset_id": f"asset_{uuid.uuid4().hex[:12]}", "storage_path": result["path"],
           "original_filename": file.filename, "content_type": file.content_type,
           "size": result.get("size", len(data)), "owner_id": user["user_id"],
           "shared_with": [], "is_shared": False, "is_deleted": False, "created_at": now_iso()}
    await db.assets.insert_one(doc)
    await log_activity(user["user_id"], "asset_upload", {"name": file.filename})
    doc.pop("_id", None)
    return doc


@api_router.get("/assets")
async def list_assets(user: dict = Depends(get_current_user)):
    assets = await db.assets.find(
        {"is_deleted": False, "$or": [{"owner_id": user["user_id"]},
                                      {"shared_with": user["user_id"]}, {"is_shared": True}]},
        {"_id": 0}).sort("created_at", -1).to_list(500)
    return assets


@api_router.get("/assets/{asset_id}/download")
async def download_asset(asset_id: str, authorization: str = Header(None), auth: str = Query(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif auth:
        token = auth
    user = await resolve_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    record = await db.assets.find_one({"asset_id": asset_id, "is_deleted": False})
    if not record:
        raise HTTPException(status_code=404, detail="Asset not found")
    data, content_type = get_object(record["storage_path"])
    return FastResponse(content=data, media_type=record.get("content_type") or content_type,
                        headers={"Content-Disposition": f'inline; filename="{record["original_filename"]}"'})


@api_router.post("/assets/{asset_id}/share")
async def share_asset(asset_id: str, user: dict = Depends(get_current_user)):
    await db.assets.update_one({"asset_id": asset_id, "owner_id": user["user_id"]},
                               {"$set": {"is_shared": True}})
    a = await db.assets.find_one({"asset_id": asset_id}, {"_id": 0})
    return a


@api_router.delete("/assets/{asset_id}")
async def delete_asset(asset_id: str, user: dict = Depends(get_current_user)):
    await db.assets.update_one({"asset_id": asset_id, "owner_id": user["user_id"]},
                               {"$set": {"is_deleted": True}})
    return {"ok": True}


# ---------------- Integrations ----------------
INTEGRATION_CATALOG = [
    {"type": "n8n", "name": "N8N", "category": "Automation",
     "fields": [{"key": "base_url", "label": "N8N Instance URL", "type": "url"},
                {"key": "api_key", "label": "API Key", "type": "password"}]},
    {"type": "cloud_storage", "name": "Cloud Storage", "category": "Storage",
     "fields": [{"key": "provider", "label": "Provider (S3/GDrive/Dropbox)", "type": "text"},
                {"key": "bucket", "label": "Bucket / Folder", "type": "text"},
                {"key": "access_key", "label": "Access Key", "type": "password"}]},
    {"type": "llm", "name": "AI LLM", "category": "AI",
     "fields": [{"key": "provider", "label": "Provider (OpenAI/Anthropic/Gemini)", "type": "text"},
                {"key": "api_key", "label": "API Key", "type": "password"},
                {"key": "model", "label": "Default Model", "type": "text"}]},
    {"type": "mcp", "name": "MCP Server", "category": "AI",
     "fields": [{"key": "server_url", "label": "MCP Server URL", "type": "url"},
                {"key": "token", "label": "Auth Token", "type": "password"}]},
]


@api_router.get("/integrations/catalog")
async def integrations_catalog(user: dict = Depends(get_current_user)):
    return INTEGRATION_CATALOG


@api_router.get("/integrations")
async def list_integrations(user: dict = Depends(get_current_user)):
    items = await db.integrations.find({"owner_id": user["user_id"]}, {"_id": 0}).to_list(200)
    for it in items:
        cfg = it.get("config", {})
        it["config_masked"] = {k: ("••••••" if k in ("api_key", "token", "access_key") and v else v) for k, v in cfg.items()}
        it.pop("config", None)
    return items


@api_router.post("/integrations")
async def create_integration(data: IntegrationInput, user: dict = Depends(get_current_user)):
    await ensure_feature("integrations")
    doc = {"integration_id": f"int_{uuid.uuid4().hex[:12]}", "type": data.type,
           "name": data.name, "config": data.config, "owner_id": user["user_id"],
           "status": "connected", "created_at": now_iso()}
    await db.integrations.insert_one(doc)
    await log_activity(user["user_id"], "integration_connect", {"type": data.type})
    doc.pop("_id", None)
    doc.pop("config", None)
    return doc


@api_router.delete("/integrations/{integration_id}")
async def delete_integration(integration_id: str, user: dict = Depends(get_current_user)):
    await db.integrations.delete_one({"integration_id": integration_id, "owner_id": user["user_id"]})
    return {"ok": True}


# ---------------- AI Assistant ----------------
@api_router.get("/ai/conversations")
async def list_conversations(user: dict = Depends(get_current_user)):
    convs = await db.ai_conversations.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return convs


@api_router.get("/ai/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    msgs = await db.ai_messages.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return msgs


@api_router.post("/ai/chat")
async def ai_chat(data: AiInput, user: dict = Depends(get_current_user)):
    await ensure_feature("ai_assistant")
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone

    conversation_id = data.conversation_id
    if not conversation_id:
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        await db.ai_conversations.insert_one({
            "conversation_id": conversation_id, "owner_id": user["user_id"],
            "title": data.message[:40], "created_at": now_iso(), "updated_at": now_iso()})
    await log_activity(user["user_id"], "ai_chat")
    await db.ai_messages.insert_one({
        "conversation_id": conversation_id, "role": "user", "content": data.message,
        "created_at": now_iso()})

    chat = LlmChat(api_key=EMERGENT_KEY, session_id=conversation_id,
                   system_message="You are Stitch, the AI assistant inside Stitches, a collaboration workspace for business and creative teams. Be concise, helpful and friendly.").with_model(data.provider, data.model)
    user_message = UserMessage(text=data.message)

    async def event_generator():
        full = ""
        yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"
        try:
            async for event in chat.stream_message(user_message):
                if isinstance(event, TextDelta):
                    full += event.content
                    yield f"data: {json.dumps({'delta': event.content})}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as e:
            logger.error(f"AI error: {e}")
            yield f"data: {json.dumps({'delta': f'[Error: {str(e)}]'})}\n\n"
        await db.ai_messages.insert_one({
            "conversation_id": conversation_id, "role": "assistant", "content": full,
            "created_at": now_iso()})
        await db.ai_conversations.update_one({"conversation_id": conversation_id},
                                             {"$set": {"updated_at": now_iso()}})
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------------- Dashboard / Admin ----------------
@api_router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    ws_count = await db.workspaces.count_documents({"members": user["user_id"]})
    proj_count = await db.projects.count_documents({"members": user["user_id"]})
    asset_count = await db.assets.count_documents({"owner_id": user["user_id"], "is_deleted": False})
    int_count = await db.integrations.count_documents({"owner_id": user["user_id"]})
    msg_count = await db.messages.count_documents({"user_id": user["user_id"]})
    recent_projects = await db.projects.find({"members": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(5)
    return {"workspaces": ws_count, "projects": proj_count, "assets": asset_count,
            "integrations": int_count, "messages": msg_count, "recent_projects": recent_projects}


@api_router.get("/admin/stats")
async def admin_stats(user: dict = Depends(require_admin)):
    total_users = await db.users.count_documents({})
    total_ws = await db.workspaces.count_documents({})
    total_proj = await db.projects.count_documents({})
    total_assets = await db.assets.count_documents({"is_deleted": False})
    total_int = await db.integrations.count_documents({})
    total_msgs = await db.messages.count_documents({})
    recent_users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(10)
    return {"total_users": total_users, "total_workspaces": total_ws, "total_projects": total_proj,
            "total_assets": total_assets, "total_integrations": total_int, "total_messages": total_msgs,
            "recent_users": recent_users}


# ---------------- Notifications ----------------
@api_router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    items = await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    unread = sum(1 for i in items if not i.get("read"))
    return {"notifications": items, "unread": unread}


@api_router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one({"notification_id": notification_id, "user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}


@api_router.post("/notifications/read-all")
async def read_all_notifications(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}


# ---------------- Feature flags ----------------
@api_router.get("/features")
async def features(user: dict = Depends(get_current_user)):
    return await get_feature_flags()


@api_router.get("/admin/features")
async def admin_get_features(user: dict = Depends(require_admin)):
    return await get_feature_flags()


@api_router.put("/admin/features")
async def admin_set_features(data: FeatureFlagsInput, user: dict = Depends(require_admin)):
    flags = await get_feature_flags()
    flags.update(data.flags)
    await db.settings.update_one({"key": "feature_flags"}, {"$set": {"value": flags}}, upsert=True)
    return flags


# ---------------- SEO ----------------
@api_router.get("/seo")
async def seo_public():
    return await get_seo_settings()


@api_router.put("/admin/seo")
async def admin_set_seo(data: SeoInput, user: dict = Depends(require_admin)):
    seo = await get_seo_settings()
    seo.update({k: v for k, v in data.model_dump().items() if v is not None})
    await db.settings.update_one({"key": "seo"}, {"$set": {"value": seo}}, upsert=True)
    return seo


# ---------------- Monitoring & Heatmap ----------------
@api_router.get("/admin/monitoring")
async def admin_monitoring(user: dict = Depends(require_admin)):
    now = datetime.now(timezone.utc)
    recent = await db.activity_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    by_action, daily = {}, {}
    for r in recent:
        by_action[r["action"]] = by_action.get(r["action"], 0) + 1
        d = r.get("created_at", "")[:10]
        if d:
            daily[d] = daily.get(d, 0) + 1
    today = now.date().isoformat()
    active_today = len({r["user_id"] for r in recent if r.get("created_at", "")[:10] == today and r.get("user_id")})
    feed = recent[:15]
    uids = list({f.get("user_id") for f in feed if f.get("user_id")})
    users = await db.users.find({"user_id": {"$in": uids}}, {"_id": 0, "user_id": 1, "name": 1, "email": 1}).to_list(100)
    umap = {u["user_id"]: u for u in users}
    for f in feed:
        u = umap.get(f.get("user_id"))
        f["user_name"] = u["name"] if u else "System"
        f["user_email"] = u["email"] if u else ""
    return {"total_events": await db.activity_log.count_documents({}),
            "active_today": active_today, "by_action": by_action,
            "daily": [{"date": k, "count": daily[k]} for k in sorted(daily.keys())][-7:],
            "feed": feed}


@api_router.get("/admin/heatmap")
async def admin_heatmap(user: dict = Depends(require_admin)):
    grid = [[0] * 24 for _ in range(7)]
    logs = await db.activity_log.find({}, {"_id": 0, "created_at": 1}).to_list(5000)
    for l in logs:
        try:
            dt = datetime.fromisoformat(l["created_at"])
            grid[dt.weekday()][dt.hour] += 1
        except Exception:
            continue
    return {"grid": grid}


# ---------------- Admin user management ----------------
@api_router.get("/admin/users")
async def admin_users(user: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
    return users


@api_router.put("/admin/users/{user_id}")
async def admin_update_user(user_id: str, data: UserAdminUpdate, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        await db.users.update_one({"user_id": user_id}, {"$set": updates})
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return u


@api_router.post("/admin/users/{user_id}/set-password")
async def admin_set_password(user_id: str, data: SetPasswordInput, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"user_id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one({"user_id": user_id}, {"$set": {"password_hash": hash_password(data.password)}})
    await log_activity(user["user_id"], "admin_reset_password", {"target": user_id})
    return {"ok": True, "message": "Password updated"}


@api_router.post("/admin/users/{user_id}/impersonate")
async def admin_impersonate(user_id: str, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    token = create_access_token(target["user_id"], target["email"])
    await log_activity(user["user_id"], "impersonate", {"target": user_id})
    return {"token": token, "user": public_user(target)}


# ---------------- Friends ----------------
@api_router.get("/friends")
async def list_friends(user: dict = Depends(get_current_user)):
    me = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "friends": 1})
    ids = (me or {}).get("friends", [])
    friends = await db.users.find({"user_id": {"$in": ids}}, {"_id": 0, "password_hash": 0}).to_list(500)
    return friends


@api_router.post("/friends")
async def add_friend(data: EmailInput, user: dict = Depends(get_current_user)):
    friend = await db.users.find_one({"email": data.email.lower()})
    if not friend:
        raise HTTPException(status_code=404, detail="No Stitches user found with that email")
    if friend["user_id"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot add yourself")
    await db.users.update_one({"user_id": user["user_id"]}, {"$addToSet": {"friends": friend["user_id"]}})
    await db.users.update_one({"user_id": friend["user_id"]}, {"$addToSet": {"friends": user["user_id"]}})
    await create_notification(friend["user_id"], "friend", "New connection", f"{user.get('name')} connected with you")
    return {"ok": True, "friend": public_user(friend)}


@api_router.delete("/friends/{friend_id}")
async def remove_friend(friend_id: str, user: dict = Depends(get_current_user)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$pull": {"friends": friend_id}})
    await db.users.update_one({"user_id": friend_id}, {"$pull": {"friends": user["user_id"]}})
    return {"ok": True}


# ---------------- Project members ----------------
@api_router.get("/projects/{project_id}/members")
async def project_members(project_id: str, user: dict = Depends(get_current_user)):
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    members = await db.users.find({"user_id": {"$in": p.get("members", [])}}, {"_id": 0, "password_hash": 0}).to_list(500)
    for m in members:
        m["is_owner"] = m["user_id"] == p.get("owner_id")
    return members


@api_router.post("/projects/{project_id}/invite")
async def project_invite(project_id: str, data: EmailInput, user: dict = Depends(get_current_user)):
    p = await db.projects.find_one({"project_id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    invitee = await db.users.find_one({"email": data.email.lower()})
    if not invitee:
        raise HTTPException(status_code=404, detail="No Stitches user found with that email")
    if invitee["user_id"] in p.get("members", []):
        raise HTTPException(status_code=400, detail="User is already a member")
    await db.projects.update_one({"project_id": project_id}, {"$addToSet": {"members": invitee["user_id"]}})
    await create_notification(invitee["user_id"], "project", "Added to a project",
                              f"{user.get('name')} added you to '{p.get('name')}'", "/projects")
    return {"ok": True, "member": public_user(invitee)}


@api_router.post("/projects/{project_id}/remove")
async def project_remove(project_id: str, data: UserIdInput, user: dict = Depends(get_current_user)):
    p = await db.projects.find_one({"project_id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if data.user_id == p.get("owner_id"):
        raise HTTPException(status_code=400, detail="Cannot remove the project owner")
    await db.projects.update_one({"project_id": project_id}, {"$pull": {"members": data.user_id}})
    return {"ok": True}


@api_router.post("/workspaces/{workspace_id}/remove")
async def workspace_remove(workspace_id: str, data: UserIdInput, user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if data.user_id == ws.get("owner_id"):
        raise HTTPException(status_code=400, detail="Cannot remove the workspace owner")
    await db.workspaces.update_one({"workspace_id": workspace_id}, {"$pull": {"members": data.user_id}})
    return {"ok": True}


@api_router.get("/")
async def root():
    return {"message": "Stitches API"}


# ---------------- Startup ----------------
@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token")
    admin_email = os.environ.get("ADMIN_EMAIL")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    existing = await db.users.find_one({"email": admin_email})
    if existing is None:
        await db.users.insert_one({
            "user_id": f"user_{uuid.uuid4().hex[:12]}", "email": admin_email,
            "name": "Stitches Admin", "password_hash": hash_password(admin_password),
            "role": "admin", "username": "admin", "avatar": None, "phone": "", "address": "",
            "company": "Stitches", "company_role": "Administrator", "bio": "", "project_info": "",
            "theme": "dark", "ui_scale": 1.0, "auth_provider": "password", "is_active": True, "friends": [], "created_at": now_iso()})
    elif not verify_password(admin_password, existing.get("password_hash", "")):
        await db.users.update_one({"email": admin_email},
                                  {"$set": {"password_hash": hash_password(admin_password), "role": "admin"}})
    try:
        init_storage()
        logger.info("Storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed: {e}")


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
