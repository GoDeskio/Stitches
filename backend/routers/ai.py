from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from services.agent_actions import build_agent_system, execute_agent_action
from models import *

router = APIRouter()


# ---------------- AI Memory Persistence ----------------
_MEM_DEFAULT = {"user_enabled": True, "workspace_enabled": False, "retention_days": 90, "max_items": 200}
_WORKSPACE_OWNER = "__workspace__"


async def _ai_memory_cfg():
    doc = await db.settings.find_one({"key": "ai_memory"})
    return {**_MEM_DEFAULT, **((doc or {}).get("value") or {})}


async def _user_auto_capture(user_id):
    """Per-user preference: may Stitch auto-learn new facts? Default True."""
    doc = await db.ai_user_prefs.find_one({"user_id": user_id})
    if not doc or doc.get("auto_capture") is None:
        return True
    return bool(doc.get("auto_capture"))


async def _load_memories(user, cfg):
    """Return a formatted memory block to inject into the assistant's system prompt."""
    lines = []
    if cfg["user_enabled"]:
        mine = await db.ai_memories.find({"scope": "user", "owner_id": user["user_id"]}, {"_id": 0, "content": 1}).sort("created_at", -1).to_list(cfg["max_items"])
        lines += [f"- {m['content']}" for m in reversed(mine)]
    if cfg["workspace_enabled"]:
        shared = await db.ai_memories.find({"scope": "workspace", "owner_id": _WORKSPACE_OWNER}, {"_id": 0, "content": 1}).sort("created_at", -1).to_list(cfg["max_items"])
        lines += [f"- (team) {m['content']}" for m in reversed(shared)]
    if not lines:
        return ""
    return "\n\nKnown facts to remember about the user and their team (use when relevant):\n" + "\n".join(lines)


async def _prune_memory(scope, owner_id, cfg):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=cfg["retention_days"])).isoformat()
    await db.ai_memories.delete_many({"scope": scope, "owner_id": owner_id, "created_at": {"$lt": cutoff}})
    total = await db.ai_memories.count_documents({"scope": scope, "owner_id": owner_id})
    if total > cfg["max_items"]:
        extra = await db.ai_memories.find({"scope": scope, "owner_id": owner_id}, {"_id": 1}).sort("created_at", 1).to_list(total - cfg["max_items"])
        await db.ai_memories.delete_many({"_id": {"$in": [e["_id"] for e in extra]}})


async def _extract_memory(user, user_text, assistant_text, cfg, auto_capture=True):
    """Background: distill durable facts from the exchange and persist them."""
    try:
        # Decide target scope, honoring the user's auto-capture preference.
        if cfg["user_enabled"] and auto_capture:
            scope, owner = "user", user["user_id"]
        elif cfg["workspace_enabled"]:
            scope, owner = "workspace", _WORKSPACE_OWNER
        else:
            return
        from emergentintegrations.llm.chat import LlmChat, UserMessage, StreamDone, TextDelta
        chat = LlmChat(api_key=EMERGENT_KEY, session_id=f"mem_{user['user_id']}_{uuid.uuid4().hex[:6]}",
                       system_message=("Extract durable, reusable facts about the user or their team from the exchange "
                                       "(preferences, roles, projects, tools, deadlines, stable context). "
                                       "Return ONLY a JSON array of short strings. No facts -> return []. Max 4 items.")).with_model("openai", "gpt-5.4-mini")
        full = ""
        async for event in chat.stream_message(UserMessage(text=f"User: {user_text}\nAssistant: {assistant_text}")):
            if isinstance(event, TextDelta):
                full += event.content
            elif isinstance(event, StreamDone):
                break
        raw = full.strip().strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end < 0:
            return
        facts = json.loads(raw[start:end + 1])
        for f in facts[:4]:
            f = str(f).strip()
            if not f:
                continue
            exists = await db.ai_memories.find_one({"scope": scope, "owner_id": owner, "content": f})
            if exists:
                continue
            await db.ai_memories.insert_one({"mem_id": f"mem_{uuid.uuid4().hex[:12]}", "scope": scope,
                                             "owner_id": owner, "content": f[:400], "created_at": now_iso(),
                                             "source": "auto"})
        await _prune_memory(scope, owner, cfg)
    except Exception as e:
        logger.error(f"memory extract error: {e}")


@router.get("/admin/ai-memory/config")
async def get_ai_memory_config(user: dict = Depends(require_admin)):
    cfg = await _ai_memory_cfg()
    counts = {
        "user": await db.ai_memories.count_documents({"scope": "user"}),
        "workspace": await db.ai_memories.count_documents({"scope": "workspace"}),
    }
    return {**cfg, "counts": counts}


@router.put("/admin/ai-memory/config")
async def set_ai_memory_config(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    val = {
        "user_enabled": bool(body.get("user_enabled")),
        "workspace_enabled": bool(body.get("workspace_enabled")),
        "retention_days": max(1, min(3650, int(body.get("retention_days") or 90))),
        "max_items": max(10, min(5000, int(body.get("max_items") or 200))),
    }
    await db.settings.update_one({"key": "ai_memory"}, {"$set": {"key": "ai_memory", "value": val}}, upsert=True)
    return {"ok": True}


@router.get("/admin/ai-memory/list")
async def list_ai_memory(scope: str = "", q: str = "", user: dict = Depends(require_admin)):
    query = {}
    if scope in ("user", "workspace"):
        query["scope"] = scope
    if q:
        query["content"] = {"$regex": q, "$options": "i"}
    items = await db.ai_memories.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


@router.post("/admin/ai-memory")
async def add_ai_memory(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    scope = "workspace" if body.get("scope") == "workspace" else "user"
    owner = _WORKSPACE_OWNER if scope == "workspace" else (body.get("owner_id") or user["user_id"])
    mem = {"mem_id": f"mem_{uuid.uuid4().hex[:12]}", "scope": scope, "owner_id": owner,
           "content": content[:400], "created_at": now_iso()}
    await db.ai_memories.insert_one(mem)
    mem.pop("_id", None)
    return mem


@router.delete("/admin/ai-memory/{mem_id}")
async def delete_ai_memory(mem_id: str, user: dict = Depends(require_admin)):
    await db.ai_memories.delete_one({"mem_id": mem_id})
    return {"ok": True}


@router.delete("/admin/ai-memory")
async def clear_ai_memory(scope: str = "", user: dict = Depends(require_admin)):
    query = {"scope": scope} if scope in ("user", "workspace") else {}
    res = await db.ai_memories.delete_many(query)
    return {"ok": True, "deleted": res.deleted_count}


# ---- User-facing memory transparency ("What Stitch remembers about you") ----
@router.get("/ai/memory")
async def my_ai_memory(user: dict = Depends(get_current_user)):
    cfg = await _ai_memory_cfg()
    mine, shared = [], []
    if cfg["user_enabled"]:
        mine = await db.ai_memories.find({"scope": "user", "owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(cfg["max_items"])
    if cfg["workspace_enabled"]:
        shared = await db.ai_memories.find({"scope": "workspace", "owner_id": _WORKSPACE_OWNER}, {"_id": 0}).sort("created_at", -1).to_list(cfg["max_items"])
    return {"user_enabled": cfg["user_enabled"], "workspace_enabled": cfg["workspace_enabled"],
            "auto_capture": await _user_auto_capture(user["user_id"]),
            "user": mine, "workspace": shared}


@router.put("/ai/memory/prefs")
async def set_my_memory_prefs(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    await db.ai_user_prefs.update_one({"user_id": user["user_id"]},
                                      {"$set": {"user_id": user["user_id"], "auto_capture": bool(body.get("auto_capture"))}}, upsert=True)
    return {"ok": True, "auto_capture": bool(body.get("auto_capture"))}


@router.post("/ai/memory")
async def pin_my_memory(request: Request, user: dict = Depends(get_current_user)):
    cfg = await _ai_memory_cfg()
    if not cfg["user_enabled"]:
        raise HTTPException(status_code=400, detail="Memory is turned off by your admin")
    body = await request.json()
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    mem = {"mem_id": f"mem_{uuid.uuid4().hex[:12]}", "scope": "user", "owner_id": user["user_id"],
           "content": content[:400], "created_at": now_iso(), "source": "pinned"}
    await db.ai_memories.insert_one(mem)
    await _prune_memory("user", user["user_id"], cfg)
    mem.pop("_id", None)
    return mem


@router.delete("/ai/memory/{mem_id}")
async def forget_my_memory(mem_id: str, user: dict = Depends(get_current_user)):
    res = await db.ai_memories.delete_one({"mem_id": mem_id, "scope": "user", "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found or not yours to forget")
    return {"ok": True}


@router.patch("/ai/memory/{mem_id}")
async def edit_my_memory(mem_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    content = (body.get("content") or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="content required")
    res = await db.ai_memories.update_one(
        {"mem_id": mem_id, "scope": "user", "owner_id": user["user_id"]},
        {"$set": {"content": content[:400], "edited_at": now_iso()}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found or not yours to edit")
    return {"ok": True, "content": content[:400]}


# ---------------- AI Assistant ----------------
@router.get("/ai/conversations")
async def list_conversations(user: dict = Depends(get_current_user)):
    convs = await db.ai_conversations.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return convs


@router.get("/ai/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user: dict = Depends(get_current_user)):
    msgs = await db.ai_messages.find({"conversation_id": conversation_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return msgs


@router.post("/ai/chat")
async def ai_chat(data: AiInput, user: dict = Depends(get_current_user)):
    await ensure_feature("ai_assistant", user)
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

    mem_cfg = await _ai_memory_cfg()
    memory_block = await _load_memories(user, mem_cfg)
    system_msg = ("You are Stitch, the AI assistant inside Stitches, a collaboration workspace for business and creative teams. "
                  "Be concise, helpful and friendly." + memory_block)
    chat = LlmChat(api_key=EMERGENT_KEY, session_id=conversation_id,
                   system_message=system_msg).with_model(data.provider, data.model)
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
        if full and (mem_cfg["user_enabled"] or mem_cfg["workspace_enabled"]):
            _auto = await _user_auto_capture(user["user_id"])
            if (mem_cfg["user_enabled"] and _auto) or mem_cfg["workspace_enabled"]:
                asyncio.create_task(_extract_memory(user, data.message, full, mem_cfg, _auto))
        yield f"data: {json.dumps({'done': True})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/ai/agent")
async def ai_agent(data: AiInput, user: dict = Depends(get_current_user)):
    await ensure_feature("ai_assistant", user)
    from emergentintegrations.llm.chat import LlmChat, UserMessage, TextDelta, StreamDone
    await log_activity(user["user_id"], "ai_agent")
    chat = LlmChat(api_key=EMERGENT_KEY, session_id=f"agent_{user['user_id']}",
                   system_message=build_agent_system(user)).with_model(data.provider or "openai", data.model or "gpt-5.4")
    full = ""
    try:
        async for event in chat.stream_message(UserMessage(text=data.message)):
            if isinstance(event, TextDelta):
                full += event.content
            elif isinstance(event, StreamDone):
                break
    except Exception as e:
        logger.error(f"agent llm error: {e}")
        return {"reply": "Sorry, I couldn't reach the AI right now.", "action": None, "result": None}

    raw = full.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    raw = raw.strip()
    action, params, message, result = None, {}, "", None
    # Robustly extract JSON envelope: try decoding at every '{'; keep the LAST valid envelope dict.
    decoder = json.JSONDecoder()
    last = None
    for i, ch in enumerate(raw):
        if ch == "{":
            try:
                obj, _ = decoder.raw_decode(raw, i)
                if isinstance(obj, dict) and "action" in obj:
                    last = obj
            except Exception:
                continue
    if last is not None:
        action = last.get("action")
        params = last.get("params") or {}
        message = last.get("message") or ""
    else:
        message = raw or "Sorry, I didn't understand that."
    if action:
        result = await execute_agent_action(action, params, user)
        if result and not result.get("ok"):
            message = f"{message}\n\n⚠️ {result.get('error')}" if message else f"⚠️ {result.get('error')}"
    if not message:
        message = "Done."
    return {"reply": message, "action": action, "result": result}


