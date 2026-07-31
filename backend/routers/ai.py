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


_MEM_CATEGORIES = ["preference", "project", "deadline", "tool", "general"]
_EXTRACT_PROMPT = ("Extract durable, reusable facts about the user or their team from the exchange "
                   "(preferences, roles, projects, tools, deadlines, stable context). "
                   "Return ONLY a JSON array of objects: {\"content\": short string, \"category\": one of "
                   "preference|project|deadline|tool|general}. No facts -> return []. Max 4 items.")


def _norm_category(c):
    c = str(c or "general").strip().lower()
    return c if c in _MEM_CATEGORIES else "general"


async def _distill_facts(user_id, user_text, assistant_text):
    """Run the LLM to extract candidate facts. Returns list of {content, category}."""
    from emergentintegrations.llm.chat import LlmChat, UserMessage, StreamDone, TextDelta
    chat = LlmChat(api_key=EMERGENT_KEY, session_id=f"mem_{user_id}_{uuid.uuid4().hex[:6]}",
                   system_message=_EXTRACT_PROMPT).with_model("openai", "gpt-5.4-mini")
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
        return []
    out = []
    for f in json.loads(raw[start:end + 1])[:4]:
        if isinstance(f, dict):
            content, cat = str(f.get("content", "")).strip(), _norm_category(f.get("category"))
        else:
            content, cat = str(f).strip(), "general"
        if content:
            out.append({"content": content[:400], "category": cat})
    return out


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
        for f in await _distill_facts(user["user_id"], user_text, assistant_text):
            exists = await db.ai_memories.find_one({"scope": scope, "owner_id": owner, "content": f["content"]})
            if exists:
                continue
            await db.ai_memories.insert_one({"mem_id": f"mem_{uuid.uuid4().hex[:12]}", "scope": scope,
                                             "owner_id": owner, "content": f["content"], "category": f["category"],
                                             "created_at": now_iso(), "source": "auto"})
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


@router.post("/admin/ai-memory/digest/test")
async def test_digest_delivery(request: Request, user: dict = Depends(require_admin)):
    """Send a one-off sample memory digest to any address to confirm email delivery."""
    from services.email import send_email_detailed
    body = await request.json()
    email = (body.get("email") or "").strip()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="valid email required")
    sample_groups = {
        "preference": ["Prefers concise, bullet-point answers", "Works best in the mornings"],
        "project": ["Leading the Q3 Launch project"],
        "deadline": ["Website relaunch due Sept 15"],
    }
    frontend = os.environ.get("FRONTEND_URL", "")
    html = _build_memory_digest_html("there", sample_groups, f"{frontend}/assistant?memory=open")
    ok, detail = await send_email_detailed(email, "[Test] What Stitch remembers about you", html)
    return {"ok": ok, "detail": detail}


# ---- User-facing memory transparency ("What Stitch remembers about you") ----
@router.get("/ai/memory")
async def my_ai_memory(user: dict = Depends(get_current_user)):
    cfg = await _ai_memory_cfg()
    mine, shared = [], []
    if cfg["user_enabled"]:
        mine = await db.ai_memories.find({"scope": "user", "owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(cfg["max_items"])
    if cfg["workspace_enabled"]:
        shared = await db.ai_memories.find({"scope": "workspace", "owner_id": _WORKSPACE_OWNER}, {"_id": 0}).sort("created_at", -1).to_list(cfg["max_items"])
    prefs_doc = await db.ai_user_prefs.find_one({"user_id": user["user_id"]}) or {}
    cadence = prefs_doc.get("digest_cadence") or ("monthly" if prefs_doc.get("memory_digest") else "off")
    return {"user_enabled": cfg["user_enabled"], "workspace_enabled": cfg["workspace_enabled"],
            "auto_capture": await _user_auto_capture(user["user_id"]),
            "digest_cadence": cadence,
            "user": mine, "workspace": shared}


@router.put("/ai/memory/prefs")
async def set_my_memory_prefs(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    updates = {"user_id": user["user_id"]}
    if "auto_capture" in body:
        updates["auto_capture"] = bool(body.get("auto_capture"))
    if "digest_cadence" in body:
        cad = str(body.get("digest_cadence") or "off").lower()
        updates["digest_cadence"] = cad if cad in ("off", "weekly", "monthly") else "off"
    if not updates.get("digest_cadence") and "memory_digest" in body:
        updates["digest_cadence"] = "monthly" if body.get("memory_digest") else "off"
    await db.ai_user_prefs.update_one({"user_id": user["user_id"]}, {"$set": updates}, upsert=True)
    return {"ok": True, **{k: v for k, v in updates.items() if k != "user_id"}}


@router.post("/ai/memory/bulk-category")
async def bulk_recategorize(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    ids = [str(i) for i in (body.get("ids") or [])]
    category = _norm_category(body.get("category"))
    if not ids:
        raise HTTPException(status_code=400, detail="no memories selected")
    res = await db.ai_memories.update_many(
        {"mem_id": {"$in": ids}, "scope": "user", "owner_id": user["user_id"]},
        {"$set": {"category": category, "edited_at": now_iso()}})
    return {"ok": True, "updated": res.modified_count, "category": category}


@router.post("/ai/memory/bulk-delete")
async def bulk_forget(request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    ids = [str(i) for i in (body.get("ids") or [])]
    if not ids:
        raise HTTPException(status_code=400, detail="no memories selected")
    res = await db.ai_memories.delete_many(
        {"mem_id": {"$in": ids}, "scope": "user", "owner_id": user["user_id"]})
    return {"ok": True, "deleted": res.deleted_count}


@router.post("/ai/memory/restore")
async def restore_memories(request: Request, user: dict = Depends(get_current_user)):
    """Re-insert user-scoped memories (used by the Undo action after a forget)."""
    body = await request.json()
    mems = body.get("memories") or []
    restored = 0
    for m in mems:
        if not m.get("mem_id") or not m.get("content"):
            continue
        exists = await db.ai_memories.find_one({"mem_id": m["mem_id"]})
        if exists:
            continue
        await db.ai_memories.insert_one({
            "mem_id": m["mem_id"], "scope": "user", "owner_id": user["user_id"],
            "content": str(m["content"])[:400], "category": _norm_category(m.get("category")),
            "created_at": m.get("created_at") or now_iso(), "source": m.get("source") or "pinned",
            **({"edited_at": m["edited_at"]} if m.get("edited_at") else {})})
        restored += 1
    return {"ok": True, "restored": restored}


@router.get("/ai/memory/export")
async def export_memories(format: str = "json", user: dict = Depends(get_current_user)):
    from fastapi.responses import Response
    mems = await db.ai_memories.find({"scope": "user", "owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    if format == "csv":
        import csv, io
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["category", "content", "source", "created_at", "edited_at"])
        for m in mems:
            w.writerow([m.get("category", "general"), m.get("content", ""), m.get("source", ""), m.get("created_at", ""), m.get("edited_at", "")])
        return Response(content=buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=stitch-memories.csv"})
    return Response(content=json.dumps(mems, indent=2), media_type="application/json",
                    headers={"Content-Disposition": "attachment; filename=stitch-memories.json"})


@router.post("/ai/memory/import")
async def import_memories(request: Request, user: dict = Depends(get_current_user)):
    """Restore/import a previously exported memory set (JSON/CSV parsed to a list). New IDs, own scope."""
    cfg = await _ai_memory_cfg()
    if not cfg["user_enabled"]:
        raise HTTPException(status_code=400, detail="Memory is turned off by your admin")
    body = await request.json()
    rows = body.get("memories") or []
    if not isinstance(rows, list):
        raise HTTPException(status_code=400, detail="expected a list of memories")
    imported = 0
    for r in rows[:2000]:
        content = str((r or {}).get("content", "")).strip() if isinstance(r, dict) else str(r).strip()
        if not content:
            continue
        exists = await db.ai_memories.find_one({"scope": "user", "owner_id": user["user_id"], "content": content})
        if exists:
            continue
        await db.ai_memories.insert_one({
            "mem_id": f"mem_{uuid.uuid4().hex[:12]}", "scope": "user", "owner_id": user["user_id"],
            "content": content[:400], "category": _norm_category((r or {}).get("category") if isinstance(r, dict) else None),
            "created_at": now_iso(), "source": "imported"})
        imported += 1
    await _prune_memory("user", user["user_id"], cfg)
    return {"ok": True, "imported": imported}


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
           "content": content[:400], "category": _norm_category(body.get("category")),
           "created_at": now_iso(), "source": body.get("source") or "pinned"}
    await db.ai_memories.insert_one(mem)
    await _prune_memory("user", user["user_id"], cfg)
    mem.pop("_id", None)
    return mem


@router.post("/ai/memory/suggest")
async def suggest_memory(request: Request, user: dict = Depends(get_current_user)):
    """After a chat, propose one durable fact for the user to accept or dismiss (no auto-store)."""
    cfg = await _ai_memory_cfg()
    if not cfg["user_enabled"]:
        return {"suggestion": None}
    body = await request.json()
    user_text = (body.get("user_text") or "")[:2000]
    assistant_text = (body.get("assistant_text") or "")[:2000]
    if not user_text and not assistant_text:
        return {"suggestion": None}
    try:
        facts = await _distill_facts(user["user_id"], user_text, assistant_text)
    except Exception as e:
        logger.error(f"suggest error: {e}")
        return {"suggestion": None}
    for f in facts:
        exists = await db.ai_memories.find_one({"scope": "user", "owner_id": user["user_id"], "content": f["content"]})
        if not exists:
            return {"suggestion": f["content"], "category": f["category"]}
    return {"suggestion": None}


@router.delete("/ai/memory/{mem_id}")
async def forget_my_memory(mem_id: str, user: dict = Depends(get_current_user)):
    res = await db.ai_memories.delete_one({"mem_id": mem_id, "scope": "user", "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not found or not yours to forget")
    return {"ok": True}


@router.patch("/ai/memory/{mem_id}")
async def edit_my_memory(mem_id: str, request: Request, user: dict = Depends(get_current_user)):
    body = await request.json()
    updates = {}
    if "content" in body:
        content = (body.get("content") or "").strip()
        if not content:
            raise HTTPException(status_code=400, detail="content cannot be empty")
        updates["content"] = content[:400]
    if "category" in body:
        updates["category"] = _norm_category(body.get("category"))
    if not updates:
        raise HTTPException(status_code=400, detail="nothing to update")
    updates["edited_at"] = now_iso()
    res = await db.ai_memories.update_one(
        {"mem_id": mem_id, "scope": "user", "owner_id": user["user_id"]}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Not found or not yours to edit")
    return {"ok": True, **updates}


# ---- Monthly "what Stitch remembers" digest ----
def _build_memory_digest_html(name, groups, prune_url):
    rows = ""
    for cat in _MEM_CATEGORIES:
        items = groups.get(cat) or []
        if not items:
            continue
        lis = "".join(f"<li style='margin:4px 0;color:#1f2937'>{m}</li>" for m in items)
        rows += (f"<div style='margin:16px 0'><div style='font-size:12px;font-weight:700;text-transform:uppercase;"
                 f"letter-spacing:.05em;color:#7c3aed;margin-bottom:6px'>{cat.title()}</div>"
                 f"<ul style='margin:0;padding-left:18px'>{lis}</ul></div>")
    if not rows:
        rows = "<p style='color:#6b7280'>Stitch hasn't remembered anything about you yet.</p>"
    return (f"<div style='font-family:system-ui,Arial,sans-serif;max-width:560px;margin:auto;padding:24px;"
            f"background:#faf5ff;border-radius:16px'>"
            f"<h2 style='color:#111827;margin:0 0 4px'>What Stitch remembers about you</h2>"
            f"<p style='color:#6b7280;margin:0 0 12px'>Hi {name or 'there'}, here's your monthly memory summary. "
            f"You're always in control.</p>{rows}"
            f"<a href='{prune_url}' style='display:inline-block;margin-top:16px;background:#7c3aed;color:#fff;"
            f"text-decoration:none;padding:12px 20px;border-radius:12px;font-weight:600'>Review &amp; prune memories</a>"
            f"<p style='color:#9ca3af;font-size:12px;margin-top:16px'>Manage this summary in Stitch AI &rarr; Memory.</p></div>")


async def _send_memory_digest(user_doc, cfg):
    from services.email import send_email_detailed
    uid = user_doc["user_id"]
    mems = await db.ai_memories.find({"scope": "user", "owner_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(cfg["max_items"])
    groups = {}
    for m in mems:
        groups.setdefault(_norm_category(m.get("category")), []).append(m["content"])
    frontend = os.environ.get("FRONTEND_URL", "")
    html = _build_memory_digest_html(user_doc.get("name"), groups, f"{frontend}/assistant?memory=open")
    to = user_doc.get("email")
    if not to:
        return False, "no email on file"
    ok, detail = await send_email_detailed(to, "What Stitch remembers about you", html)
    await db.ai_user_prefs.update_one({"user_id": uid}, {"$set": {"last_digest": now_iso()}}, upsert=True)
    return ok, detail


@router.post("/ai/memory/digest/send-now")
async def send_memory_digest_now(user: dict = Depends(get_current_user)):
    cfg = await _ai_memory_cfg()
    doc = await db.users.find_one({"user_id": user["user_id"]}) or user
    ok, detail = await _send_memory_digest(doc, cfg)
    return {"ok": ok, "detail": detail}


@router.get("/ai/memory/digest/preview")
async def preview_memory_digest(user: dict = Depends(get_current_user)):
    cfg = await _ai_memory_cfg()
    doc = await db.users.find_one({"user_id": user["user_id"]}) or user
    uid = user["user_id"]
    mems = await db.ai_memories.find({"scope": "user", "owner_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(cfg["max_items"])
    groups = {}
    for m in mems:
        groups.setdefault(_norm_category(m.get("category")), []).append(m["content"])
    frontend = os.environ.get("FRONTEND_URL", "")
    html = _build_memory_digest_html(doc.get("name"), groups, f"{frontend}/assistant?memory=open")
    return {"html": html, "count": len(mems)}


async def scan_memory_digests():
    """Weekly/monthly: email a memory summary to users per their chosen cadence."""
    try:
        cfg = await _ai_memory_cfg()
        if not cfg["user_enabled"]:
            return 0
        now = datetime.now(timezone.utc)
        weekly_cut = (now - timedelta(days=7)).isoformat()
        monthly_cut = (now - timedelta(days=30)).isoformat()
        prefs = await db.ai_user_prefs.find({"$or": [{"digest_cadence": {"$in": ["weekly", "monthly"]}},
                                                     {"memory_digest": True}]}).to_list(2000)
        sent = 0
        for p in prefs:
            cadence = p.get("digest_cadence") or ("monthly" if p.get("memory_digest") else "off")
            if cadence not in ("weekly", "monthly"):
                continue
            cut = weekly_cut if cadence == "weekly" else monthly_cut
            if p.get("last_digest") and p["last_digest"] > cut:
                continue
            doc = await db.users.find_one({"user_id": p["user_id"]})
            if not doc:
                continue
            ok, _ = await _send_memory_digest(doc, cfg)
            if ok:
                sent += 1
        return sent
    except Exception as e:
        logger.error(f"memory digest scan error: {e}")
        return 0


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


