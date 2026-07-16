from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from services.site import get_site_config
from services.email import send_meeting_email
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


AGENT_ACTIONS_USER = """- create_project {"name": str, "description"?: str}: create a new project
- create_workspace {"name": str}: create a new workspace (auto-adds general & random channels)
- add_friend {"email": str}: add a connection by their email
- send_message {"workspace": str, "channel": str, "text": str}: post a message to a channel in one of your workspaces
- invite_to_workspace {"workspace": str, "email": str}: add a person (by email) to one of your workspaces
- invite_to_project {"project": str, "email": str}: add a person (by email) to one of your projects
- list_projects {}: list the user's projects
- list_workspaces {}: list the user's workspaces
- get_stats {}: get the user's dashboard counts (workspaces, projects, assets, integrations, messages)
- contact_support {"subject"?: str, "message": str}: when you genuinely cannot help, the request is outside your abilities, or the user asks for a human/support, forward their message to the site's support team"""

AGENT_ACTIONS_ADMIN = """- admin_stats {}: platform-wide totals (users, workspaces, projects, etc.)
- admin_list_users {}: list all members with role and status
- admin_toggle_feature {"feature": "chat|projects|assets|integrations|ai_assistant|friends", "enabled": bool}: turn a feature on/off for everyone
- admin_set_user_active {"email": str, "active": bool}: enable or disable a user's account"""


def build_agent_system(user):
    actions = AGENT_ACTIONS_USER
    if user.get("role") == "admin":
        actions += "\n" + AGENT_ACTIONS_ADMIN
    return (
        "You are Stitch, the built-in AI assistant for Stitches (a collaboration workspace). "
        "You take real actions on the user's account by returning a JSON command. Available actions:\n" + actions +
        "\n\nRESPONSE FORMAT — always reply with EXACTLY ONE strict minified JSON object and nothing else "
        "(no markdown, no code fences, no prose before/after):\n"
        '{"action":"<name-or-null>","params":{...},"message":"<short friendly first-person confirmation>"}\n\n'
        "RULES:\n"
        "1. If the request matches an action, use it. Prefer taking an action over answering in prose.\n"
        "2. contact_support is your escalation tool. You MUST use it whenever the user: reports a bug or something "
        "broken/crashing/not working, asks for help you cannot perform with the actions above, mentions a billing/account/"
        "payment issue, or asks to talk to a human / support / the team. Never just summarize or acknowledge such requests — "
        "always escalate with contact_support.\n"
        "3. Only use action null for pure informational questions you can fully answer yourself.\n\n"
        "EXAMPLES:\n"
        'User: "the video call crashes when I join" -> {"action":"contact_support","params":{"subject":"Video call crash","message":"The video call feature crashes when the user joins."},"message":"I couldn\'t fix that myself, so I\'ve sent it to our support team for you."}\n'
        'User: "I need to talk to a human about billing" -> {"action":"contact_support","params":{"subject":"Billing question","message":"User wants to speak with a human about a billing question."},"message":"I\'ve forwarded your request to our support team."}\n'
        'User: "create a project called Apollo" -> {"action":"create_project","params":{"name":"Apollo"},"message":"Creating your project \'Apollo\'."}\n'
        'User: "what is a workspace?" -> {"action":null,"message":"A workspace is a shared space where your team chats and collaborates on channels and projects."}\n'
    )


async def execute_agent_action(action, params, user):
    is_admin = user.get("role") == "admin"
    p = params or {}
    try:
        if action == "create_project":
            if not p.get("name"):
                return {"ok": False, "error": "A project name is required"}
            doc = {"project_id": f"proj_{uuid.uuid4().hex[:12]}", "name": p["name"],
                   "description": p.get("description", ""), "status": "active", "workspace_id": None,
                   "owner_id": user["user_id"], "members": [user["user_id"]], "created_at": now_iso()}
            await db.projects.insert_one(doc)
            await log_activity(user["user_id"], "project_create", {"name": p["name"], "via": "ai"})
            return {"ok": True, "summary": f"Created project '{p['name']}'"}
        if action == "create_workspace":
            if not p.get("name"):
                return {"ok": False, "error": "A workspace name is required"}
            ws_id = f"ws_{uuid.uuid4().hex[:12]}"
            await db.workspaces.insert_one({"workspace_id": ws_id, "name": p["name"], "description": "",
                                            "icon": None, "owner_id": user["user_id"], "members": [user["user_id"]],
                                            "created_at": now_iso()})
            for cname in ["general", "random"]:
                await db.channels.insert_one({"channel_id": f"ch_{uuid.uuid4().hex[:12]}", "workspace_id": ws_id,
                                              "name": cname, "type": "channel", "description": "", "created_at": now_iso()})
            return {"ok": True, "summary": f"Created workspace '{p['name']}' with #general and #random"}
        if action == "add_friend":
            friend = await db.users.find_one({"email": (p.get("email") or "").lower()})
            if not friend:
                return {"ok": False, "error": "No Stitches user found with that email"}
            await db.users.update_one({"user_id": user["user_id"]}, {"$addToSet": {"friends": friend["user_id"]}})
            await db.users.update_one({"user_id": friend["user_id"]}, {"$addToSet": {"friends": user["user_id"]}})
            return {"ok": True, "summary": f"Added {friend.get('name')} as a connection"}
        if action == "send_message":
            wss = await db.workspaces.find({"members": user["user_id"]}, {"_id": 0}).to_list(200)
            ws = next((w for w in wss if w["name"].lower() == (p.get("workspace") or "").lower()), None)
            if not ws:
                return {"ok": False, "error": f"You are not in a workspace named '{p.get('workspace')}'"}
            chans = await db.channels.find({"workspace_id": ws["workspace_id"]}, {"_id": 0}).to_list(200)
            ch = next((c for c in chans if c["name"].lower() == (p.get("channel") or "").lower().lstrip("#")), None)
            if not ch:
                return {"ok": False, "error": f"No channel '{p.get('channel')}' in {ws['name']}"}
            if not (p.get("text") or "").strip():
                return {"ok": False, "error": "Message text is required"}
            msg = await _create_message(ch["channel_id"], user, p["text"].strip())
            await ws_manager.broadcast(ch["channel_id"], {"type": "message", "message": msg})
            return {"ok": True, "summary": f"Posted to #{ch['name']} in {ws['name']}"}
        if action == "invite_to_workspace":
            wss = await db.workspaces.find({"members": user["user_id"]}, {"_id": 0}).to_list(200)
            ws = next((w for w in wss if w["name"].lower() == (p.get("workspace") or "").lower()), None)
            if not ws:
                return {"ok": False, "error": f"You are not in a workspace named '{p.get('workspace')}'"}
            invitee = await db.users.find_one({"email": (p.get("email") or "").lower()})
            if not invitee:
                return {"ok": False, "error": "No Stitches user found with that email"}
            await db.workspaces.update_one({"workspace_id": ws["workspace_id"]}, {"$addToSet": {"members": invitee["user_id"]}})
            await create_notification(invitee["user_id"], "workspace", "Added to a workspace",
                                      f"{user.get('name')} added you to '{ws['name']}'", "/messages")
            return {"ok": True, "summary": f"Added {invitee.get('name')} to {ws['name']}"}
        if action == "invite_to_project":
            projs = await db.projects.find({"members": user["user_id"]}, {"_id": 0}).to_list(200)
            pr = next((x for x in projs if x["name"].lower() == (p.get("project") or "").lower()), None)
            if not pr:
                return {"ok": False, "error": f"No project named '{p.get('project')}'"}
            invitee = await db.users.find_one({"email": (p.get("email") or "").lower()})
            if not invitee:
                return {"ok": False, "error": "No Stitches user found with that email"}
            await db.projects.update_one({"project_id": pr["project_id"]}, {"$addToSet": {"members": invitee["user_id"]}})
            await create_notification(invitee["user_id"], "project", "Added to a project",
                                      f"{user.get('name')} added you to '{pr['name']}'", "/projects")
            return {"ok": True, "summary": f"Added {invitee.get('name')} to {pr['name']}"}
        if action == "list_projects":
            projs = await db.projects.find({"members": user["user_id"]}, {"_id": 0, "name": 1, "status": 1}).to_list(100)
            return {"ok": True, "summary": f"{len(projs)} project(s)", "items": [f"{x['name']} ({x['status']})" for x in projs]}
        if action == "list_workspaces":
            ws = await db.workspaces.find({"members": user["user_id"]}, {"_id": 0, "name": 1}).to_list(100)
            return {"ok": True, "summary": f"{len(ws)} workspace(s)", "items": [x["name"] for x in ws]}
        if action == "get_stats":
            return {"ok": True, "summary": "Your dashboard", "items": [
                f"Workspaces: {await db.workspaces.count_documents({'members': user['user_id']})}",
                f"Projects: {await db.projects.count_documents({'members': user['user_id']})}",
                f"Assets: {await db.assets.count_documents({'owner_id': user['user_id'], 'is_deleted': False})}",
                f"Integrations: {await db.integrations.count_documents({'owner_id': user['user_id']})}"]}
        if action == "contact_support":
            msg = (p.get("message") or "").strip()
            if not msg:
                return {"ok": False, "error": "Please tell me what the support team should know"}
            subject = (p.get("subject") or "Support request from Stitches").strip()[:140]
            _, support_email = await get_site_config()
            await db.support_requests.insert_one({
                "request_id": f"sup_{uuid.uuid4().hex[:12]}", "user_id": user["user_id"],
                "user_email": user.get("email"), "user_name": user.get("name"),
                "subject": subject, "message": msg[:2000], "status": "open", "created_at": now_iso()})
            admins = await db.users.find({"role": "admin"}, {"_id": 0, "user_id": 1}).to_list(100)
            for a in admins:
                await create_notification(a["user_id"], "support", f"Support request: {subject}",
                                          f"From {user.get('name')}: {msg[:120]}", "/admin")
            sent = False
            if support_email:
                html = (f"<div style='font-family:sans-serif;max-width:520px'>"
                        f"<h2 style='color:#c0202e'>{subject}</h2><p>{msg}</p>"
                        f"<p style='color:#888;font-size:13px'>From {user.get('name')} &lt;{user.get('email')}&gt;</p></div>")
                sent = await send_meeting_email(support_email, f"[Stitches Support] {subject}", html, sender_user_id=user["user_id"])
            if support_email:
                note = f"I've forwarded your message to our support team at {support_email}."
                if not sent:
                    note += " They'll also see it in the admin dashboard."
            else:
                note = "I've logged your request for our team and they'll follow up soon."
            return {"ok": True, "summary": note, "items": [f"Subject: {subject}", f"Message: {msg[:200]}"]}
        # admin actions
        if action in ("admin_stats", "admin_list_users", "admin_toggle_feature", "admin_set_user_active"):
            if not is_admin:
                return {"ok": False, "error": "This action requires administrator access"}
            if action == "admin_stats":
                return {"ok": True, "summary": "Platform totals", "items": [
                    f"Users: {await db.users.count_documents({})}",
                    f"Workspaces: {await db.workspaces.count_documents({})}",
                    f"Projects: {await db.projects.count_documents({})}",
                    f"Messages: {await db.messages.count_documents({})}"]}
            if action == "admin_list_users":
                users = await db.users.find({}, {"_id": 0, "name": 1, "email": 1, "role": 1, "is_active": 1}).to_list(200)
                return {"ok": True, "summary": f"{len(users)} member(s)",
                        "items": [f"{u['name']} <{u['email']}> — {u['role']}{'' if u.get('is_active', True) else ' (disabled)'}" for u in users]}
            if action == "admin_toggle_feature":
                feat = p.get("feature")
                if feat not in DEFAULT_FEATURES:
                    return {"ok": False, "error": f"Unknown feature '{feat}'"}
                flags = await get_feature_flags()
                flags[feat] = bool(p.get("enabled", True))
                await db.settings.update_one({"key": "feature_flags"}, {"$set": {"value": flags}}, upsert=True)
                return {"ok": True, "summary": f"Feature '{feat}' is now {'ON' if flags[feat] else 'OFF'} for all users"}
            if action == "admin_set_user_active":
                target = await db.users.find_one({"email": (p.get("email") or "").lower()})
                if not target:
                    return {"ok": False, "error": "User not found"}
                await db.users.update_one({"user_id": target["user_id"]}, {"$set": {"is_active": bool(p.get("active", True))}})
                return {"ok": True, "summary": f"{target.get('name')} is now {'active' if p.get('active', True) else 'disabled'}"}
        return {"ok": False, "error": f"Unknown action '{action}'"}
    except Exception as e:
        logger.error(f"agent action error: {e}")
        return {"ok": False, "error": str(e)}


@router.post("/ai/agent")
async def ai_agent(data: AiInput, user: dict = Depends(get_current_user)):
    await ensure_feature("ai_assistant")
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


