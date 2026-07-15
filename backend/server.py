from core import *
from core import _create_message, resolve_user_from_token, ws_manager, public_user
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.middleware.cors import CORSMiddleware
import os

from routers import auth, users, messaging, projects, assets, integrations, ai, admin

app = FastAPI()
api_router = APIRouter(prefix="/api")
for _mod in (auth, users, messaging, projects, assets, integrations, ai, admin):
    api_router.include_router(_mod.router)


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
            if data.get("type") == "typing":
                await ws_manager.broadcast(channel_id, {"type": "typing", "user_id": user["user_id"], "user_name": user.get("name")})
                continue
            text = data.get("text", "").strip()
            if text:
                msg = await _create_message(channel_id, public_user(user), text)
                await ws_manager.broadcast(channel_id, {"type": "message", "message": msg})
    except WebSocketDisconnect:
        ws_manager.disconnect(channel_id, websocket)
    except Exception:
        ws_manager.disconnect(channel_id, websocket)

app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
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


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
