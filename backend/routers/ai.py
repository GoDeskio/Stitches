from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from services.agent_actions import build_agent_system, execute_agent_action
from models import *

router = APIRouter()


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


