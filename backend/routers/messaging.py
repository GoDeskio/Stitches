from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from models import *

router = APIRouter()


# ---------------- Workspaces ----------------
@router.get("/workspaces")
async def list_workspaces(user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find({"members": user["user_id"]}, {"_id": 0}).to_list(200)
    return ws


@router.post("/workspaces")
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


@router.post("/workspaces/{workspace_id}/join")
async def join_workspace(workspace_id: str, user: dict = Depends(get_current_user)):
    await db.workspaces.update_one({"workspace_id": workspace_id},
                                   {"$addToSet": {"members": user["user_id"]}})
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.get("/workspaces/{workspace_id}/members")
async def workspace_members(workspace_id: str, user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id}, {"_id": 0})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    members = await db.users.find({"user_id": {"$in": ws.get("members", [])}},
                                  {"_id": 0, "password_hash": 0}).to_list(500)
    for m in members:
        m["is_owner"] = m["user_id"] == ws.get("owner_id")
    return members


@router.post("/workspaces/{workspace_id}/invite")
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
@router.get("/workspaces/{workspace_id}/channels")
async def list_channels(workspace_id: str, user: dict = Depends(get_current_user)):
    chs = await db.channels.find({"workspace_id": workspace_id}, {"_id": 0}).to_list(200)
    return chs


@router.post("/channels")
async def create_channel(data: ChannelInput, user: dict = Depends(get_current_user)):
    ch_id = f"ch_{uuid.uuid4().hex[:12]}"
    doc = {"channel_id": ch_id, "workspace_id": data.workspace_id, "name": data.name,
           "type": data.type, "description": data.description, "created_at": now_iso()}
    await db.channels.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/channels/{channel_id}/messages")
async def get_messages(channel_id: str, before: str = None, limit: int = 50, user: dict = Depends(get_current_user)):
    limit = max(1, min(limit, 200))
    q = {"channel_id": channel_id}
    if before:
        q["created_at"] = {"$lt": before}
    msgs = await db.messages.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    msgs.reverse()
    return msgs
@router.post("/messages")
async def post_message(data: MessageInput, user: dict = Depends(get_current_user)):
    await ensure_feature("chat", user)
    doc = await _create_message(data.channel_id, user, data.text, data.parent_id, data.mentions)
    await ws_manager.broadcast(data.channel_id, {"type": "message", "message": doc})
    await _notify_mentions(doc, user)
    await log_activity(user["user_id"], "message", {"channel_id": data.channel_id})
    return doc


@router.post("/messages/{message_id}/react")
async def react_message(message_id: str, data: ReactInput, user: dict = Depends(get_current_user)):
    msg = await db.messages.find_one({"message_id": message_id})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    reactions = msg.get("reactions") or {}
    users = reactions.get(data.emoji, [])
    if user["user_id"] in users:
        users = [u for u in users if u != user["user_id"]]
    else:
        users = users + [user["user_id"]]
    if users:
        reactions[data.emoji] = users
    else:
        reactions.pop(data.emoji, None)
    await db.messages.update_one({"message_id": message_id}, {"$set": {"reactions": reactions}})
    await ws_manager.broadcast(msg["channel_id"], {"type": "reaction", "message_id": message_id, "reactions": reactions})
    return {"ok": True, "reactions": reactions}
