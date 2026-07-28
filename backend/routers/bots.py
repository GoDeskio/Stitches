from fastapi import APIRouter, HTTPException, Depends, Body, Request
from core import *
from core import _create_message, ws_manager, _fernet
from datetime import datetime, timezone, timedelta
import uuid
import hashlib
import secrets

router = APIRouter()

# Suggested categories surfaced in the UI (creators may also type a custom one)
BOT_CATEGORIES = ["general", "ci", "alerts", "support", "monitoring", "marketing", "sales", "ops"]


def _clean_category(v):
    v = (v or "general").strip().lower()[:24]
    return v or "general"


def _spark(b: dict, days: int = 14):
    """Oldest→newest daily message counts for a sparkline."""
    daily = b.get("daily") or {}
    today = datetime.now(timezone.utc).date()
    return [int(daily.get((today - timedelta(days=(days - 1 - i))).isoformat(), 0)) for i in range(days)]


def _hash(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def _dec(enc: str):
    if not enc:
        return None
    try:
        return _fernet.decrypt(enc.encode()).decode()
    except Exception:
        return None


def _public_bot(b: dict) -> dict:
    return {
        "bot_id": b["bot_id"], "name": b["name"], "enabled": b.get("enabled", True),
        "shared": bool(b.get("shared")), "category": b.get("category", "general"),
        "target_channel_id": b.get("target_channel_id"), "target_channel_name": b.get("target_channel_name"),
        "outbound_webhook_set": bool(b.get("outbound_webhook_enc")),
        "message_count": b.get("message_count", 0), "last_used_at": b.get("last_used_at"),
        "activity": _spark(b), "created_at": b.get("created_at"), "token": _dec(b.get("token_enc")),
    }


def _directory_bot(b: dict, owner_name: str, is_owner: bool) -> dict:
    # public-safe view for the shared directory — NEVER exposes the token
    return {
        "bot_id": b["bot_id"], "name": b["name"], "enabled": b.get("enabled", True),
        "category": b.get("category", "general"),
        "target_channel_name": b.get("target_channel_name"),
        "message_count": b.get("message_count", 0), "last_used_at": b.get("last_used_at"),
        "activity": _spark(b), "created_at": b.get("created_at"), "description": b.get("description", ""),
        "owner_name": owner_name or "A teammate", "is_owner": is_owner,
    }


async def _resolve_channel(user: dict, channel_id: str) -> dict:
    ch = await db.channels.find_one({"channel_id": channel_id})
    if not ch:
        raise HTTPException(status_code=400, detail="Channel not found")
    ws = await db.workspaces.find_one({"workspace_id": ch.get("workspace_id")})
    if ws and user["user_id"] != ws.get("owner_id") and user["user_id"] not in (ws.get("members") or []):
        raise HTTPException(status_code=403, detail="You don't have access to that channel")
    return ch


def _new_token() -> str:
    return "stbot_" + secrets.token_hex(24)


@router.post("/bots")
async def create_bot(body: dict = Body(...), user: dict = Depends(get_current_user)):
    name = (body.get("name") or "").strip()
    channel_id = body.get("target_channel_id")
    if not name:
        raise HTTPException(status_code=400, detail="Bot name is required")
    ch = await _resolve_channel(user, channel_id)
    token = _new_token()
    doc = {
        "bot_id": f"bot_{uuid.uuid4().hex[:12]}", "owner_id": user["user_id"], "name": name,
        "enabled": True, "shared": bool(body.get("shared")), "description": (body.get("description") or "").strip()[:280],
        "category": _clean_category(body.get("category")),
        "target_channel_id": channel_id, "target_channel_name": ch.get("name"),
        "token_hash": _hash(token), "token_enc": _fernet.encrypt(token.encode()).decode(),
        "outbound_webhook_enc": "", "message_count": 0, "daily": {}, "last_used_at": None, "created_at": now_iso(),
    }
    await db.bots.insert_one(doc)
    await log_activity(user["user_id"], "bot_create", {"bot_id": doc["bot_id"], "name": name})
    return _public_bot(doc)


@router.get("/bots")
async def list_bots(user: dict = Depends(get_current_user)):
    items = await db.bots.find({"owner_id": user["user_id"]}).sort("created_at", -1).to_list(200)
    return {"bots": [_public_bot(b) for b in items]}


async def _owner_names(items):
    owner_ids = list({b.get("owner_id") for b in items})
    users = await db.users.find({"user_id": {"$in": owner_ids}}, {"_id": 0, "user_id": 1, "name": 1}).to_list(len(owner_ids) or 1)
    return {u["user_id"]: u.get("name") for u in users}


@router.get("/bots/directory")
async def bot_directory(user: dict = Depends(get_current_user)):
    items = await db.bots.find({"shared": True}).sort("message_count", -1).to_list(300)
    names = await _owner_names(items)
    cats = sorted({b.get("category", "general") for b in items})
    return {"bots": [_directory_bot(b, names.get(b.get("owner_id")), b.get("owner_id") == user["user_id"]) for b in items],
            "categories": cats}


@router.get("/bots/featured")
async def featured_bots(user: dict = Depends(get_current_user)):
    items = await db.bots.find({"shared": True, "enabled": True}).to_list(300)
    items.sort(key=lambda b: (sum(_spark(b, 7)), b.get("message_count", 0)), reverse=True)
    top = items[:6]
    names = await _owner_names(top)
    out = []
    for b in top:
        d = _directory_bot(b, names.get(b.get("owner_id")), b.get("owner_id") == user["user_id"])
        d["recent"] = sum(_spark(b, 7))
        out.append(d)
    return {"bots": out}


@router.patch("/bots/{bot_id}")
async def update_bot(bot_id: str, body: dict = Body(...), user: dict = Depends(get_current_user)):
    b = await db.bots.find_one({"bot_id": bot_id, "owner_id": user["user_id"]})
    if not b:
        raise HTTPException(status_code=404, detail="Bot not found")
    sets = {}
    if "enabled" in body:
        sets["enabled"] = bool(body["enabled"])
    if "shared" in body:
        sets["shared"] = bool(body["shared"])
    if "description" in body:
        sets["description"] = (body.get("description") or "").strip()[:280]
    if "category" in body:
        sets["category"] = _clean_category(body.get("category"))
    if body.get("name", "").strip():
        sets["name"] = body["name"].strip()
    if "target_channel_id" in body:
        ch = await _resolve_channel(user, body["target_channel_id"])
        sets["target_channel_id"] = body["target_channel_id"]
        sets["target_channel_name"] = ch.get("name")
    if "outbound_webhook" in body:
        sets["outbound_webhook_enc"] = _fernet.encrypt(body["outbound_webhook"].encode()).decode() if body["outbound_webhook"] else ""
    if sets:
        await db.bots.update_one({"bot_id": bot_id}, {"$set": sets})
    return _public_bot(await db.bots.find_one({"bot_id": bot_id}))


@router.post("/bots/{bot_id}/rotate")
async def rotate_bot(bot_id: str, user: dict = Depends(get_current_user)):
    b = await db.bots.find_one({"bot_id": bot_id, "owner_id": user["user_id"]})
    if not b:
        raise HTTPException(status_code=404, detail="Bot not found")
    token = _new_token()
    await db.bots.update_one({"bot_id": bot_id}, {"$set": {
        "token_hash": _hash(token), "token_enc": _fernet.encrypt(token.encode()).decode()}})
    await log_activity(user["user_id"], "bot_rotate", {"bot_id": bot_id})
    return _public_bot(await db.bots.find_one({"bot_id": bot_id}))


@router.delete("/bots/{bot_id}")
async def delete_bot(bot_id: str, user: dict = Depends(get_current_user)):
    r = await db.bots.delete_one({"bot_id": bot_id, "owner_id": user["user_id"]})
    if not r.deleted_count:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"ok": True}


@router.post("/bots/{bot_id}/clone")
async def clone_bot(bot_id: str, body: dict = Body(...), user: dict = Depends(get_current_user)):
    src = await db.bots.find_one({"bot_id": bot_id, "shared": True})
    if not src:
        raise HTTPException(status_code=404, detail="Bot not found in the shared directory")
    channel_id = body.get("target_channel_id")
    ch = await _resolve_channel(user, channel_id)
    token = _new_token()
    name = (body.get("name") or f"{src['name']} (copy)").strip()[:120]
    doc = {
        "bot_id": f"bot_{uuid.uuid4().hex[:12]}", "owner_id": user["user_id"], "name": name,
        "enabled": True, "shared": False, "description": src.get("description", ""),
        "category": src.get("category", "general"),
        "cloned_from": src["bot_id"], "target_channel_id": channel_id, "target_channel_name": ch.get("name"),
        "token_hash": _hash(token), "token_enc": _fernet.encrypt(token.encode()).decode(),
        "outbound_webhook_enc": "", "message_count": 0, "daily": {}, "last_used_at": None, "created_at": now_iso(),
    }
    await db.bots.insert_one(doc)
    await log_activity(user["user_id"], "bot_clone", {"bot_id": doc["bot_id"], "from": src["bot_id"], "name": name})
    return _public_bot(doc)


# ---------------- Public ingest (bot-token auth, no user session) ----------------
async def _auth_bot(request: Request, body_token: str):
    token = None
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    token = token or body_token
    if not token:
        raise HTTPException(status_code=401, detail="Missing bot token")
    b = await db.bots.find_one({"token_hash": _hash(token)})
    if not b:
        raise HTTPException(status_code=401, detail="Invalid bot token")
    if not b.get("enabled", True):
        raise HTTPException(status_code=403, detail="This bot is disabled")
    return b


@router.post("/bots/ingest")
async def bot_ingest(request: Request, body: dict = Body(...)):
    b = await _auth_bot(request, body.get("token"))
    text = (body.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="'text' is required")
    sender = (body.get("sender_name") or "").strip()
    display = f"🤖 {b['name']}" + (f" · {sender}" if sender else "")
    bot_user = {"user_id": b["bot_id"], "name": display, "avatar": None}
    doc = await _create_message(b["target_channel_id"], bot_user, text[:4000])
    doc["is_bot"] = True
    await ws_manager.broadcast(b["target_channel_id"], {"type": "message", "message": doc})
    day = datetime.now(timezone.utc).date().isoformat()
    daily = b.get("daily") or {}
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=30)).isoformat()
    update = {"$set": {"last_used_at": now_iso()}, "$inc": {"message_count": 1, f"daily.{day}": 1}}
    stale = {f"daily.{k}": "" for k in daily if k < cutoff}
    if stale:
        update["$unset"] = stale
    await db.bots.update_one({"bot_id": b["bot_id"]}, update)
    return {"ok": True, "message_id": doc["message_id"], "channel_id": b["target_channel_id"]}
