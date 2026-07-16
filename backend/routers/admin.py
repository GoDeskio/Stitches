from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from services.site import get_site_config
from services.email import send_email_detailed
from services.digest import get_digest_config, save_digest_config, send_digest_now, send_report_now, render_digest, get_digest_history
from models import *

router = APIRouter()


@router.get("/site-config")
async def public_site_config():
    ann, support_email, clarity_id = await get_site_config()
    return {"announcement": ann, "support_email": support_email, "clarity_id": clarity_id}


@router.get("/admin/site-config")
async def admin_get_site_config(user: dict = Depends(require_admin)):
    ann, support_email, clarity_id = await get_site_config()
    require_verification = await get_require_verification()
    return {"announcement": ann, "support_email": support_email, "clarity_id": clarity_id,
            "require_verification": require_verification}


@router.put("/admin/site-config")
async def admin_set_site_config(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    ann = body.get("announcement")
    if isinstance(ann, dict):
        val = {"enabled": bool(ann.get("enabled")),
               "title": (ann.get("title") or "").strip()[:120],
               "message": (ann.get("message") or "").strip()[:1000],
               "signature": (ann.get("signature") or "").strip()[:120],
               "updated_at": now_iso()}
        await db.settings.update_one({"key": "announcement"}, {"$set": {"key": "announcement", "value": val}}, upsert=True)
    if "support_email" in body:
        await db.settings.update_one({"key": "support_email"},
                                     {"$set": {"key": "support_email", "value": {"email": (body.get("support_email") or "").strip()}}}, upsert=True)
    if "clarity_id" in body:
        await db.settings.update_one({"key": "clarity"},
                                     {"$set": {"key": "clarity", "value": {"id": (body.get("clarity_id") or "").strip()[:40]}}}, upsert=True)
    if "require_verification" in body:
        await db.settings.update_one({"key": "require_email_verification"},
                                     {"$set": {"key": "require_email_verification", "value": {"enabled": bool(body.get("require_verification"))}}}, upsert=True)
    return {"ok": True}


# ---------------- Notifications global (admin) ----------------
@router.get("/admin/notifications-global")
async def admin_get_notif_global(user: dict = Depends(require_admin)):
    return await get_notif_global()


# ---------------- Desktop release (downloads) ----------------
_PLATFORM_EXT = {"windows": (".exe",), "macos": (".dmg",), "linux": (".appimage",)}
_release_cache = {}
_RELEASE_TTL = 300  # seconds


@router.get("/downloads/release")
async def downloads_release(user: dict = Depends(get_current_user)):
    import time
    repo = await get_desktop_repo()
    result = {"repo": repo, "has_release": False, "tag": None,
              "releases_url": (f"https://github.com/{repo}/releases" if repo else ""),
              "assets": {"windows": None, "macos": None, "linux": None}}
    if not repo:
        return result
    cached = _release_cache.get(repo)
    if cached and (time.time() - cached[0]) < _RELEASE_TTL:
        return cached[1]
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"https://api.github.com/repos/{repo}/releases/latest",
                                 headers={"Accept": "application/vnd.github+json"}, timeout=12.0)
        if r.status_code == 200:
            rel = r.json()
            result["tag"] = rel.get("tag_name")
            result["releases_url"] = rel.get("html_url") or result["releases_url"]
            for a in rel.get("assets", []):
                name = (a.get("name") or "").lower()
                url = a.get("browser_download_url")
                for plat, exts in _PLATFORM_EXT.items():
                    if any(name.endswith(e) for e in exts) and not result["assets"][plat]:
                        result["assets"][plat] = url
            result["has_release"] = any(result["assets"].values())
    except Exception:
        pass
    _release_cache[repo] = (time.time(), result)
    return result


@router.get("/admin/downloads-config")
async def get_downloads_config(user: dict = Depends(require_admin)):
    return {"repo": await get_desktop_repo()}


@router.put("/admin/downloads-config")
async def set_downloads_config(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    repo = (body or {}).get("repo", "").strip().strip("/")
    await db.settings.update_one({"key": "desktop_release"},
                                 {"$set": {"key": "desktop_release", "value": {"repo": repo}}}, upsert=True)
    _release_cache.clear()
    return {"ok": True, "repo": repo}


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


@router.get("/admin/automation-alerts")
async def get_automation_alerts(user: dict = Depends(require_admin)):
    cfg = (await db.settings.find_one({"key": "automation_alerts"}) or {}).get("value", {})
    return {"enabled": bool(cfg.get("enabled")), "threshold": int(cfg.get("threshold") or 3),
            "email": cfg.get("email", ""), "webhook_url": cfg.get("webhook_url", "")}


@router.put("/admin/automation-alerts")
async def set_automation_alerts(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    try:
        threshold = int(body.get("threshold", 3))
    except (TypeError, ValueError):
        threshold = 3
    threshold = max(1, min(threshold, 20))
    val = {"enabled": bool(body.get("enabled")), "threshold": threshold,
           "email": (body.get("email") or "").strip(), "webhook_url": (body.get("webhook_url") or "").strip()}
    await db.settings.update_one({"key": "automation_alerts"}, {"$set": {"key": "automation_alerts", "value": val}}, upsert=True)
    return {"ok": True}


@router.get("/admin/automation-health")
async def admin_automation_health(user: dict = Depends(require_admin)):
    total = await db.integration_runs.count_documents({})
    ok = await db.integration_runs.count_documents({"ok": True})
    runs = await db.integration_runs.find({}, {"_id": 0, "integration_id": 1, "ok": 1}).sort("created_at", -1).to_list(2000)
    seen, failing = set(), 0
    for r in runs:
        iid = r.get("integration_id")
        if iid in seen:
            continue
        seen.add(iid)
        if not r.get("ok"):
            failing += 1
    rate = round(ok * 100 / total) if total else 100
    return {"total": total, "ok_count": ok, "fail_count": total - ok, "success_rate": rate, "failing": failing}


@router.get("/admin/support-requests")
async def admin_support_requests(status: str = "all", limit: int = 50, skip: int = 0,
                                 user: dict = Depends(require_admin)):
    limit = max(1, min(int(limit or 50), 200))
    skip = max(0, int(skip or 0))
    q = {}
    if status in ("open", "resolved"):
        q["status"] = status
    items = await db.support_requests.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    open_count = await db.support_requests.count_documents({"status": "open"})
    total = await db.support_requests.count_documents({})
    filtered_total = await db.support_requests.count_documents(q)
    return {"requests": items, "open_count": open_count, "total": total,
            "filtered_total": filtered_total, "skip": skip, "limit": limit,
            "has_more": skip + len(items) < filtered_total}


@router.post("/admin/support-requests/{request_id}/status")
async def admin_set_support_status(request_id: str, request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    status = "resolved" if body.get("resolved") else "open"
    res = await db.support_requests.update_one(
        {"request_id": request_id},
        {"$set": {"status": status, "resolved_at": now_iso() if status == "resolved" else None,
                  "resolved_by": user.get("name") if status == "resolved" else None}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Request not found")
    return {"ok": True, "status": status}


@router.get("/admin/integration-runs")
async def admin_integration_runs(kind: str = None, ok: str = None, owner_id: str = None,
                                 limit: int = 50, skip: int = 0,
                                 user: dict = Depends(require_admin)):
    limit = max(1, min(int(limit or 50), 200))
    skip = max(0, int(skip or 0))
    q = {}
    if kind:
        q["kind"] = kind
    if owner_id:
        q["owner_id"] = owner_id
    if ok in ("true", "false"):
        q["ok"] = (ok == "true")
    runs = await db.integration_runs.find(q, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    uids = list({r.get("owner_id") for r in runs if r.get("owner_id")})
    iids = list({r.get("integration_id") for r in runs if r.get("integration_id")})
    users = await db.users.find({"user_id": {"$in": uids}}, {"_id": 0, "user_id": 1, "name": 1, "email": 1}).to_list(500)
    ints = await db.integrations.find({"integration_id": {"$in": iids}}, {"_id": 0, "integration_id": 1, "name": 1, "type": 1}).to_list(500)
    umap = {u["user_id"]: u for u in users}
    imap = {i["integration_id"]: i for i in ints}
    for r in runs:
        u = umap.get(r.get("owner_id"))
        i = imap.get(r.get("integration_id"))
        r["owner_name"] = u["name"] if u else "Unknown"
        r["integration_name"] = i["name"] if i else "(deleted)"
        r["integration_type"] = i["type"] if i else ""
    total = await db.integration_runs.count_documents({})
    ok_count = await db.integration_runs.count_documents({"ok": True})
    filtered_total = await db.integration_runs.count_documents(q)
    return {"runs": runs, "total": total, "ok_count": ok_count, "fail_count": total - ok_count,
            "filtered_total": filtered_total, "skip": skip, "limit": limit,
            "has_more": skip + len(runs) < filtered_total}


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


# ---------------- Site-wide click / navigation heatmap ----------------
@router.post("/track")
async def track_events(request: Request):
    try:
        body = await request.json()
    except Exception:
        return {"ok": False, "stored": 0}
    events = (body or {}).get("events") or []
    visitor = str((body or {}).get("visitor_id") or "")[:64]
    now = datetime.now(timezone.utc)
    docs = []
    for e in events[:60]:
        t = e.get("type")
        if t not in ("click", "view"):
            continue
        doc = {"type": t, "path": str(e.get("path") or "/")[:200],
               "visitor_id": visitor, "label": str(e.get("label") or "")[:120],
               "created_at": now}
        if t == "click":
            try:
                doc["x"] = max(0.0, min(1.0, float(e.get("x"))))
                doc["y"] = max(0.0, min(1.0, float(e.get("y"))))
            except (TypeError, ValueError):
                continue
        docs.append(doc)
    if docs:
        await db.heat_events.insert_many(docs)
    return {"ok": True, "stored": len(docs)}


def _range_cutoff(rng):
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    return {"24h": now - timedelta(hours=24), "7d": now - timedelta(days=7),
            "30d": now - timedelta(days=30)}.get(rng)


@router.post("/admin/test-email")
async def admin_test_email(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    to = (body.get("to") or user.get("email") or "").strip()
    if not to:
        raise HTTPException(status_code=400, detail="No recipient email")
    html = ("<div style='font-family:sans-serif;max-width:520px'>"
            "<h2 style='color:#c0202e'>Stitches test email</h2>"
            "<p>If you're reading this, your email delivery is working. 🎉</p></div>")
    ok, detail = await send_email_detailed(to, "Stitches test email", html)
    return {"ok": ok, "detail": detail, "to": to}


# ---------------- Weekly / scheduled admin digest email ----------------
@router.get("/admin/digest-config")
async def admin_get_digest(user: dict = Depends(require_admin)):
    return await get_digest_config()


@router.put("/admin/digest-config")
async def admin_set_digest(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    patch = {}
    if "enabled" in body:
        patch["enabled"] = bool(body.get("enabled"))
    if body.get("frequency") in ("daily", "weekly", "monthly"):
        patch["frequency"] = body["frequency"]
    if "day_of_week" in body:
        patch["day_of_week"] = max(0, min(6, int(body.get("day_of_week") or 0)))
    if "day_of_month" in body:
        patch["day_of_month"] = max(1, min(28, int(body.get("day_of_month") or 1)))
    if "hour" in body:
        patch["hour"] = max(0, min(23, int(body.get("hour") or 0)))
    if "recipient" in body:
        patch["recipient"] = (body.get("recipient") or "").strip()[:200]
    cfg = await save_digest_config(patch)
    return cfg


@router.post("/admin/digest/send-now")
async def admin_send_digest_now(request: Request, user: dict = Depends(require_admin)):
    body = await request.json() if request.headers.get("content-length") else {}
    ok, detail = await send_digest_now(body.get("frequency"), body.get("recipient"))
    return {"ok": ok, "detail": detail}


@router.post("/admin/digest/send-report")
async def admin_send_report(request: Request, user: dict = Depends(require_admin)):
    body = await request.json() if request.headers.get("content-length") else {}
    ok, detail = await send_report_now(body.get("recipient"))
    return {"ok": ok, "detail": detail}


@router.get("/admin/digest/preview")
async def admin_digest_preview(frequency: str = "weekly", full: bool = False,
                               user: dict = Depends(require_admin)):
    freq = frequency if frequency in ("daily", "weekly", "monthly") else "weekly"
    html = await render_digest(freq, full=bool(full))
    return {"html": html}


@router.get("/admin/digest/history")
async def admin_digest_history(user: dict = Depends(require_admin)):
    return {"history": await get_digest_history(20)}


@router.get("/admin/heatmap/trend")
async def heatmap_trend(user: dict = Depends(require_admin)):
    from datetime import datetime, timezone, timedelta
    start = (datetime.now(timezone.utc) - timedelta(days=13)).replace(hour=0, minute=0, second=0, microsecond=0)
    agg = await db.heat_events.aggregate([
        {"$match": {"type": "click", "created_at": {"$gte": start}}},
        {"$group": {"_id": {"$dateToString": {"format": "%m-%d", "date": "$created_at"}}, "clicks": {"$sum": 1}}},
    ]).to_list(100)
    m = {a["_id"]: a["clicks"] for a in agg}
    out = [{"d": (start + timedelta(days=i)).strftime("%m-%d"), "clicks": m.get((start + timedelta(days=i)).strftime("%m-%d"), 0)} for i in range(14)]
    return {"days": out, "total": sum(x["clicks"] for x in out)}


@router.get("/admin/heatmap/paths")
async def heatmap_paths(range: str = "all", user: dict = Depends(require_admin)):
    cutoff = _range_cutoff(range)
    base = {"created_at": {"$gte": cutoff}} if cutoff else {}
    pipeline = [{"$match": base}] if base else []
    pipeline += [{"$group": {"_id": "$path",
                             "clicks": {"$sum": {"$cond": [{"$eq": ["$type", "click"]}, 1, 0]}},
                             "views": {"$sum": {"$cond": [{"$eq": ["$type", "view"]}, 1, 0]}}}},
                 {"$sort": {"clicks": -1, "views": -1}}, {"$limit": 200}]
    rows = await db.heat_events.aggregate(pipeline).to_list(200)
    paths = [{"path": r["_id"], "clicks": r["clicks"], "views": r["views"]} for r in rows if r["_id"]]
    visitors = len([v for v in await db.heat_events.distinct("visitor_id", base) if v])
    total_clicks = await db.heat_events.count_documents({**base, "type": "click"})
    total_views = await db.heat_events.count_documents({**base, "type": "view"})
    return {"paths": paths, "visitors": visitors, "total_clicks": total_clicks, "total_views": total_views}


@router.get("/admin/heatmap/clicks")
async def heatmap_clicks(path: str, range: str = "all", user: dict = Depends(require_admin)):
    cutoff = _range_cutoff(range)
    match = {"type": "click", "path": path}
    if cutoff:
        match["created_at"] = {"$gte": cutoff}
    pts = await db.heat_events.find(match, {"_id": 0, "x": 1, "y": 1, "label": 1}).sort("created_at", -1).to_list(3000)
    agg = await db.heat_events.aggregate([
        {"$match": {**match, "label": {"$nin": ["", None]}}},
        {"$group": {"_id": "$label", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}}, {"$limit": 15}]).to_list(15)
    top = [{"label": a["_id"], "count": a["count"]} for a in agg]
    return {"points": pts, "top_elements": top, "count": len(pts)}


# Reference background images (public pages only, for overlaying the click heatmap)
PUBLIC_REF_PATHS = {"/", "/login", "/qr-login/claim"}


@router.get("/track/reference")
async def track_reference_needed(path: str):
    if path not in PUBLIC_REF_PATHS:
        return {"needed": False}
    exists = await db.heat_refs.find_one({"path": path}, {"_id": 1})
    return {"needed": exists is None}


@router.post("/track/reference")
async def track_reference_upload(request: Request):
    body = await request.json()
    path = str((body or {}).get("path") or "")
    image = (body or {}).get("image") or ""
    if path not in PUBLIC_REF_PATHS:
        raise HTTPException(status_code=400, detail="Path not allowed for reference capture")
    if not isinstance(image, str) or not image.startswith("data:image") or len(image) > 1_600_000:
        raise HTTPException(status_code=400, detail="Invalid or oversized image")
    await db.heat_refs.update_one({"path": path},
                                  {"$set": {"path": path, "image": image, "updated_at": now_iso()}}, upsert=True)
    return {"ok": True}


@router.get("/admin/heatmap/reference")
async def admin_heatmap_reference(path: str, user: dict = Depends(require_admin)):
    doc = await db.heat_refs.find_one({"path": path}, {"_id": 0, "image": 1})
    return {"image": (doc or {}).get("image")}


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


