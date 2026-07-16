from core import *
from core import _create_message, resolve_user_from_token, ws_manager, public_user, call_manager
from fastapi import FastAPI, APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.middleware.cors import CORSMiddleware
import os
import asyncio

from routers import auth, users, messaging, projects, assets, integrations, ai, admin, meetings, rtc_config, sfu_config, smtp_config

app = FastAPI()
api_router = APIRouter(prefix="/api")
for _mod in (auth, users, messaging, projects, assets, integrations, ai, admin, meetings, rtc_config, sfu_config, smtp_config):
    api_router.include_router(_mod.router)


@app.websocket("/api/ws/call/{room_id}")
async def call_websocket(websocket: WebSocket, room_id: str, token: str = Query(None), name: str = Query(None)):
    user = await resolve_user_from_token(token) if token else None
    if not user:
        await websocket.close(code=1008)
        return
    peer_id = uuid.uuid4().hex[:10]
    display = name or user.get("name") or "Guest"
    await call_manager.connect(room_id, peer_id, display, user["user_id"], websocket)
    await websocket.send_json({"type": "welcome", "peer_id": peer_id, "peers": call_manager.peers(room_id, exclude=peer_id)})
    await call_manager.broadcast(room_id, {"type": "peer-joined", "peer_id": peer_id, "name": display}, exclude=peer_id)
    try:
        while True:
            msg = await websocket.receive_json()
            t = msg.get("type")
            if t == "signal":
                await call_manager.send(room_id, msg.get("to"), {"type": "signal", "from": peer_id, "data": msg.get("data")})
            elif t == "chat":
                await call_manager.broadcast(room_id, {"type": "chat", "from": peer_id, "name": display, "text": str(msg.get("text", ""))[:2000]}, exclude=peer_id)
            elif t == "hand":
                await call_manager.broadcast(room_id, {"type": "hand", "from": peer_id, "name": display, "raised": bool(msg.get("raised"))}, exclude=peer_id)
            elif t == "leave":
                break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        call_manager.disconnect(room_id, peer_id)
        await call_manager.broadcast(room_id, {"type": "peer-left", "peer_id": peer_id})


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
_cors_env = os.environ.get("CORS_ORIGINS", "").strip()
_frontend = os.environ.get("FRONTEND_URL", "http://localhost:3000")
if _cors_env and _cors_env != "*":
    _origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _origins = [_frontend]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    await db.users.create_index("email", unique=True)
    await db.users.create_index("user_id", unique=True)
    await db.user_sessions.create_index("session_token")
    await db.messages.create_index([("channel_id", 1), ("created_at", 1)])
    await db.sessions.create_index("jti")
    await db.sessions.create_index("user_id")
    await db.sessions.create_index([("user_id", 1), ("last_seen", -1)])
    await db.sessions.create_index("revoked_at", expireAfterSeconds=604800)
    await db.qr_tokens.create_index("token", unique=True)
    await db.qr_tokens.create_index("expires_at", expireAfterSeconds=0)
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
    asyncio.create_task(_reminder_loop())


async def _reminder_loop():
    while True:
        try:
            await scan_due_reminders()
            await scan_meeting_reminders()
        except Exception as e:
            logger.warning(f"reminder scan failed: {e}")
        await asyncio.sleep(1800)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
