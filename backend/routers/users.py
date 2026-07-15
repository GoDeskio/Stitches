from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from models import *

router = APIRouter()


# ---------------- User / Profile ----------------
@router.put("/users/me")
async def update_profile(data: ProfileUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": updates})
    fresh = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return public_user(fresh)


@router.post("/users/me/avatar")
async def upload_avatar(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    ct = file.content_type or ""
    if not ct.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    ext = file.filename.split(".")[-1].lower() if "." in file.filename else "png"
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 5MB)")
    path = f"{APP_NAME}/avatars/{user['user_id']}/{uuid.uuid4()}.{ext}"
    result = put_object(path, data, ct or "image/png")
    base = os.environ.get("FRONTEND_URL", "").rstrip("/")
    avatar_url = f"{base}/api/users/{user['user_id']}/avatar-image?v={uuid.uuid4().hex[:8]}"
    await db.users.update_one({"user_id": user["user_id"]},
                              {"$set": {"avatar": avatar_url, "avatar_path": result["path"]}})
    await log_activity(user["user_id"], "avatar_update", {})
    return {"avatar": avatar_url}


@router.get("/users/{user_id}/avatar-image")
async def get_avatar_image(user_id: str):
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "avatar_path": 1})
    if not u or not u.get("avatar_path"):
        raise HTTPException(status_code=404, detail="No avatar")
    data, content_type = get_object(u["avatar_path"])
    return FastResponse(content=data, media_type=content_type or "image/png",
                        headers={"Cache-Control": "public, max-age=3600"})


@router.get("/users")
async def list_users(user: dict = Depends(get_current_user)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(500)
    return users


# ---------------- Friends ----------------
@router.get("/friends")
async def list_friends(user: dict = Depends(get_current_user)):
    me = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0, "friends": 1})
    ids = (me or {}).get("friends", [])
    friends = await db.users.find({"user_id": {"$in": ids}}, {"_id": 0, "password_hash": 0}).to_list(500)
    for f in friends:
        f["online"] = is_online(f.get("last_seen"))
    return friends


@router.post("/friends")
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


@router.delete("/friends/{friend_id}")
async def remove_friend(friend_id: str, user: dict = Depends(get_current_user)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$pull": {"friends": friend_id}})
    await db.users.update_one({"user_id": friend_id}, {"$pull": {"friends": user["user_id"]}})
    return {"ok": True}


# ---------------- Direct Messages ----------------
@router.post("/dms")
async def create_dm(data: UserIdInput, user: dict = Depends(get_current_user)):
    if data.user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="You cannot message yourself")
    other = await db.users.find_one({"user_id": data.user_id}, {"_id": 0, "password_hash": 0})
    if not other:
        raise HTTPException(status_code=404, detail="User not found")
    parts = sorted([user["user_id"], data.user_id])
    conv = await db.dm_conversations.find_one({"participants": parts}, {"_id": 0})
    if not conv:
        conv = {"dm_id": f"dm_{uuid.uuid4().hex[:12]}", "participants": parts, "created_at": now_iso()}
        await db.dm_conversations.insert_one(dict(conv))
    conv.pop("_id", None)
    conv["other"] = {**public_user(other), "online": is_online(other.get("last_seen"))}
    return conv


@router.get("/dms")
async def list_dms(user: dict = Depends(get_current_user)):
    convs = await db.dm_conversations.find({"participants": user["user_id"]}, {"_id": 0}).to_list(200)
    result = []
    for c in convs:
        others = [p for p in c["participants"] if p != user["user_id"]]
        other_id = others[0] if others else user["user_id"]
        other = await db.users.find_one({"user_id": other_id}, {"_id": 0, "password_hash": 0})
        last = await db.messages.find({"channel_id": c["dm_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1)
        c["other"] = {**public_user(other), "online": is_online(other.get("last_seen"))} if other else {}
        c["last_message"] = last[0]["text"] if last else ""
        c["last_at"] = last[0]["created_at"] if last else c["created_at"]
        result.append(c)
    result.sort(key=lambda x: x["last_at"], reverse=True)
    return result


@router.post("/channels/{channel_id}/read")
async def mark_read(channel_id: str, user: dict = Depends(get_current_user)):
    await db.read_state.update_one({"user_id": user["user_id"], "channel_id": channel_id},
                                   {"$set": {"last_read_at": now_iso()}}, upsert=True)
    return {"ok": True}


@router.get("/unreads")
async def get_unreads(user: dict = Depends(get_current_user)):
    ws_docs = await db.workspaces.find({"members": user["user_id"]}, {"_id": 0, "workspace_id": 1}).to_list(200)
    ws_ids = [w["workspace_id"] for w in ws_docs]
    channels = await db.channels.find({"workspace_id": {"$in": ws_ids}}, {"_id": 0, "channel_id": 1}).to_list(500)
    dms = await db.dm_conversations.find({"participants": user["user_id"]}, {"_id": 0, "dm_id": 1}).to_list(200)
    ids = [c["channel_id"] for c in channels] + [d["dm_id"] for d in dms]
    states = {s["channel_id"]: s.get("last_read_at")
              for s in await db.read_state.find({"user_id": user["user_id"]}, {"_id": 0}).to_list(2000)}
    result = {}
    total = 0
    for cid in ids:
        q = {"channel_id": cid, "user_id": {"$ne": user["user_id"]}}
        last = states.get(cid)
        if last:
            q["created_at"] = {"$gt": last}
        cnt = await db.messages.count_documents(q)
        if cnt > 0:
            result[cid] = cnt
            total += cnt
    return {"channels": result, "total": total}


# ---------------- Notes ----------------
@router.get("/notes")
async def list_notes(user: dict = Depends(get_current_user)):
    notes = await db.notes.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("updated_at", -1).to_list(500)
    return notes


@router.post("/notes")
async def create_note(data: NoteInput, user: dict = Depends(get_current_user)):
    doc = {"note_id": f"note_{uuid.uuid4().hex[:12]}", "owner_id": user["user_id"],
           "title": data.title or "Untitled", "content": data.content or "", "color": data.color or "default",
           "created_at": now_iso(), "updated_at": now_iso()}
    await db.notes.insert_one(doc)
    await log_activity(user["user_id"], "note_create")
    doc.pop("_id", None)
    return doc


@router.put("/notes/{note_id}")
async def update_note(note_id: str, data: NoteInput, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    updates["updated_at"] = now_iso()
    await db.notes.update_one({"note_id": note_id, "owner_id": user["user_id"]}, {"$set": updates})
    note = await db.notes.find_one({"note_id": note_id}, {"_id": 0})
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/notes/{note_id}")
async def delete_note(note_id: str, user: dict = Depends(get_current_user)):
    await db.notes.delete_one({"note_id": note_id, "owner_id": user["user_id"]})
    return {"ok": True}


@router.get("/")
async def root():
    return {"message": "Stitches API"}


