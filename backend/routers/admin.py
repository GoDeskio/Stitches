from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from models import *

router = APIRouter()


# ---------------- Notifications global (admin) ----------------
@router.get("/admin/notifications-global")
async def admin_get_notif_global(user: dict = Depends(require_admin)):
    return await get_notif_global()


@router.put("/admin/notifications-global")
async def admin_set_notif_global(data: NotifGlobalInput, user: dict = Depends(require_admin)):
    g = await get_notif_global()
    g.update(data.settings)
    await db.settings.update_one({"key": "notifications_global"}, {"$set": {"value": g}}, upsert=True)
    return g


# ---------------- Dashboard / Admin ----------------
@router.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    ws_count = await db.workspaces.count_documents({"members": user["user_id"]})
    proj_count = await db.projects.count_documents({"members": user["user_id"]})
    asset_count = await db.assets.count_documents({"owner_id": user["user_id"], "is_deleted": False})
    int_count = await db.integrations.count_documents({"owner_id": user["user_id"]})
    msg_count = await db.messages.count_documents({"user_id": user["user_id"]})
    recent_projects = await db.projects.find({"members": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(5)
    return {"workspaces": ws_count, "projects": proj_count, "assets": asset_count,
            "integrations": int_count, "messages": msg_count, "recent_projects": recent_projects}


@router.get("/admin/stats")
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
@router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    items = await db.notifications.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(100)
    unread = sum(1 for i in items if not i.get("read"))
    return {"notifications": items, "unread": unread}


@router.post("/notifications/{notification_id}/read")
async def read_notification(notification_id: str, user: dict = Depends(get_current_user)):
    await db.notifications.update_one({"notification_id": notification_id, "user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}


@router.post("/notifications/read-all")
async def read_all_notifications(user: dict = Depends(get_current_user)):
    await db.notifications.update_many({"user_id": user["user_id"]}, {"$set": {"read": True}})
    return {"ok": True}


# ---------------- Feature flags ----------------
@router.get("/features")
async def features(user: dict = Depends(get_current_user)):
    return await get_feature_flags()


@router.get("/admin/features")
async def admin_get_features(user: dict = Depends(require_admin)):
    return await get_feature_flags()


@router.put("/admin/features")
async def admin_set_features(data: FeatureFlagsInput, user: dict = Depends(require_admin)):
    flags = await get_feature_flags()
    flags.update(data.flags)
    await db.settings.update_one({"key": "feature_flags"}, {"$set": {"value": flags}}, upsert=True)
    return flags


# ---------------- SEO ----------------
@router.get("/seo")
async def seo_public():
    return await get_seo_settings()


@router.put("/admin/seo")
async def admin_set_seo(data: SeoInput, user: dict = Depends(require_admin)):
    seo = await get_seo_settings()
    seo.update({k: v for k, v in data.model_dump().items() if v is not None})
    await db.settings.update_one({"key": "seo"}, {"$set": {"value": seo}}, upsert=True)
    return seo


# ---------------- Monitoring & Heatmap ----------------
@router.get("/activity/me")
async def my_activity(user: dict = Depends(get_current_user)):
    logs = await db.activity_log.find({"user_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(300)
    return logs


@router.get("/admin/monitoring")
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


@router.get("/admin/heatmap")
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
@router.get("/admin/users")
async def admin_users(user: dict = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(500)
    return users


@router.put("/admin/users/{user_id}")
async def admin_update_user(user_id: str, data: UserAdminUpdate, user: dict = Depends(require_admin)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        await db.users.update_one({"user_id": user_id}, {"$set": updates})
    u = await db.users.find_one({"user_id": user_id}, {"_id": 0, "password_hash": 0})
    return u


@router.post("/admin/users/{user_id}/set-password")
async def admin_set_password(user_id: str, data: SetPasswordInput, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"user_id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one({"user_id": user_id}, {"$set": {"password_hash": hash_password(data.password)}})
    await log_activity(user["user_id"], "admin_reset_password", {"target": user_id})
    return {"ok": True, "message": "Password updated"}


@router.post("/admin/users/{user_id}/impersonate")
async def admin_impersonate(user_id: str, user: dict = Depends(require_admin)):
    target = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    token = create_access_token(target["user_id"], target["email"])
    await log_activity(user["user_id"], "impersonate", {"target": user_id})
    return {"token": token, "user": public_user(target)}


