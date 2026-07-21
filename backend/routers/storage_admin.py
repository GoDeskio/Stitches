from fastapi import APIRouter, HTTPException, Depends, Body
from core import *
from core import delete_object
from bson import ObjectId
import os
import re
import shutil
import asyncio
import datetime
from services.ops_alerts import get_ops_webhook, save_ops_webhook, public_ops_webhook, send_ops_alert

router = APIRouter()

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
DB_BACKUP_DIR = os.path.join(os.environ.get("BACKUP_DIR", "/app/backups"), "db_backups")
# Purging these preserves the ability to log back in / keep core config; still allowed but scoped.
PROTECTED = {"users"}


async def require_super_admin(user: dict = Depends(require_admin)) -> dict:
    if not ADMIN_EMAIL or (user.get("email", "").strip().lower() != ADMIN_EMAIL):
        raise HTTPException(status_code=403, detail="Super admin access required")
    return user


def _json_safe(d: dict) -> dict:
    import json
    return json.loads(json.dumps(d, default=str))


async def _ops(title: str, message: str, level: str = "warn"):
    try:
        await send_ops_alert(title, message, level)
    except Exception:
        pass


def _mongo_uri() -> str:
    return os.environ.get("MONGO_URL")


@router.get("/admin/superadmin/whoami")
async def superadmin_whoami(user: dict = Depends(require_admin)):
    return {"is_super_admin": bool(ADMIN_EMAIL and user.get("email", "").strip().lower() == ADMIN_EMAIL)}


# ------------------------- Database -------------------------
@router.get("/admin/db/overview")
async def db_overview(user: dict = Depends(require_super_admin)):
    stats = await db.command("dbstats")
    names = await db.list_collection_names()
    cols = []
    for n in sorted(names):
        try:
            cs = await db.command("collstats", n)
            cols.append({"name": n, "count": cs.get("count", 0), "size": cs.get("size", 0),
                         "storage_size": cs.get("storageSize", 0), "indexes": cs.get("nindexes", 0),
                         "index_size": cs.get("totalIndexSize", 0), "protected": n in PROTECTED})
        except Exception:
            c = await db[n].estimated_document_count()
            cols.append({"name": n, "count": c, "size": 0, "storage_size": 0,
                         "indexes": 0, "index_size": 0, "protected": n in PROTECTED})
    return {"db_name": db.name, "data_size": stats.get("dataSize", 0),
            "storage_size": stats.get("storageSize", 0), "index_size": stats.get("indexSize", 0),
            "objects": stats.get("objects", 0), "collections": cols}


@router.get("/admin/db/collections/{name}/docs")
async def db_docs(name: str, page: int = 1, user: dict = Depends(require_super_admin)):
    if name not in await db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    per = 20
    total = await db[name].estimated_document_count()
    docs = await db[name].find({}).sort("_id", -1).skip((page - 1) * per).limit(per).to_list(per)
    out = [_json_safe({**d, "_id": str(d.get("_id"))}) for d in docs]
    return {"docs": out, "page": page, "pages": max(1, (total + per - 1) // per), "total": total}


@router.post("/admin/db/collections/{name}/delete-doc")
async def db_delete_doc(name: str, body: dict = Body(...), user: dict = Depends(require_super_admin)):
    _id = body.get("id")
    if not _id:
        raise HTTPException(status_code=400, detail="Document id required")
    query = {"_id": ObjectId(_id)} if ObjectId.is_valid(_id) else {"_id": _id}
    if name == "users":
        doc = await db.users.find_one(query)
        if doc and doc.get("email", "").strip().lower() == ADMIN_EMAIL:
            raise HTTPException(status_code=400, detail="You can't delete the super admin account.")
    res = await db[name].delete_one(query)
    await log_activity(user["user_id"], "db_delete_doc", {"collection": name, "id": str(_id)})
    return {"ok": True, "deleted": res.deleted_count}


@router.post("/admin/db/collections/{name}/purge")
async def db_purge(name: str, user: dict = Depends(require_super_admin)):
    if name not in await db.list_collection_names():
        raise HTTPException(status_code=404, detail="Collection not found")
    if name == "users":
        # Never delete the super admin (prevents self-lockout).
        res = await db.users.delete_many({"email": {"$ne": ADMIN_EMAIL}})
    else:
        res = await db[name].delete_many({})
    await log_activity(user["user_id"], "db_purge", {"collection": name, "deleted": res.deleted_count})
    await _ops("Collection purged 🗑️", f"'{name}' emptied — {res.deleted_count} document(s) deleted by {user.get('email')}.", "warn")
    return {"ok": True, "deleted": res.deleted_count}


@router.post("/admin/db/backup")
async def db_backup(user: dict = Depends(require_super_admin)):
    if not shutil.which("mongodump"):
        raise HTTPException(status_code=400, detail="mongodump is not available on this server (install mongodb-database-tools).")
    os.makedirs(DB_BACKUP_DIR, exist_ok=True)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(DB_BACKUP_DIR, stamp)
    proc = await asyncio.create_subprocess_exec(
        "mongodump", f"--uri={_mongo_uri()}", f"--db={db.name}", f"--out={out}",
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=f"Backup failed: {err.decode()[:200]}")
    await log_activity(user["user_id"], "db_backup", {"stamp": stamp})
    return {"ok": True, "stamp": stamp}


@router.get("/admin/db/backups")
async def db_backups(user: dict = Depends(require_super_admin)):
    items = []
    if os.path.isdir(DB_BACKUP_DIR):
        for n in sorted(os.listdir(DB_BACKUP_DIR), reverse=True):
            dbdir = os.path.join(DB_BACKUP_DIR, n, db.name)
            if os.path.isdir(dbdir):
                size = sum(f.stat().st_size for f in os.scandir(dbdir) if f.is_file())
                items.append({"stamp": n, "size": size})
    return {"backups": items, "mongodump": bool(shutil.which("mongodump"))}


@router.post("/admin/db/restore/{stamp}")
async def db_restore(stamp: str, user: dict = Depends(require_super_admin)):
    if not re.fullmatch(r"[0-9_]+", stamp):
        raise HTTPException(status_code=400, detail="Bad backup id")
    src = os.path.join(DB_BACKUP_DIR, stamp, db.name)
    if not os.path.isdir(src):
        raise HTTPException(status_code=404, detail="Backup not found")
    if not shutil.which("mongorestore"):
        raise HTTPException(status_code=400, detail="mongorestore is not available on this server.")
    proc = await asyncio.create_subprocess_exec(
        "mongorestore", f"--uri={_mongo_uri()}", "--drop", f"--nsInclude={db.name}.*",
        os.path.join(DB_BACKUP_DIR, stamp),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(status_code=400, detail=f"Restore failed: {err.decode()[:200]}")
    await log_activity(user["user_id"], "db_restore", {"stamp": stamp})
    await _ops("Database restored ⏮️", f"DB restored from backup {stamp} by {user.get('email')} (collections dropped & replaced).", "error")
    return {"ok": True}


# ------------------------- Storage (files) -------------------------
@router.get("/admin/storage/overview")
async def storage_overview(user: dict = Depends(require_super_admin)):
    pipeline = [{"$group": {"_id": "$owner_id", "count": {"$sum": 1},
                            "bytes": {"$sum": {"$ifNull": ["$size", 0]}}}}]
    grouped = await db.assets.aggregate(pipeline).to_list(2000)
    uids = [g["_id"] for g in grouped if g["_id"]]
    umap = {}
    async for u in db.users.find({"user_id": {"$in": uids}}, {"user_id": 1, "name": 1, "email": 1}):
        umap[u["user_id"]] = {"name": u.get("name"), "email": u.get("email")}
    by_user = [{
        "owner_id": g["_id"], "count": g["count"], "bytes": g["bytes"],
        "name": umap.get(g["_id"], {}).get("name") or "Unknown / deleted user",
        "email": umap.get(g["_id"], {}).get("email") or "",
        "orphan": g["_id"] not in umap,
    } for g in grouped]
    by_user.sort(key=lambda x: x["bytes"], reverse=True)
    return {"total_count": sum(g["count"] for g in grouped),
            "total_bytes": sum(g["bytes"] for g in grouped), "by_user": by_user}


@router.get("/admin/storage/assets")
async def storage_assets(page: int = 1, owner_id: str = None, user: dict = Depends(require_super_admin)):
    per = 30
    q = {"owner_id": owner_id} if owner_id else {}
    total = await db.assets.count_documents(q)
    items = await db.assets.find(q, {"_id": 0}).sort("created_at", -1).skip((page - 1) * per).limit(per).to_list(per)
    return {"assets": items, "page": page, "pages": max(1, (total + per - 1) // per), "total": total}


async def _hard_delete_assets(query: dict) -> int:
    n = 0
    async for a in db.assets.find(query, {"storage_path": 1}):
        try:
            delete_object(a.get("storage_path"))
        except Exception:
            pass
        n += 1
    await db.assets.delete_many(query)
    return n


@router.delete("/admin/storage/assets/{asset_id}")
async def storage_delete_asset(asset_id: str, user: dict = Depends(require_super_admin)):
    n = await _hard_delete_assets({"asset_id": asset_id})
    await log_activity(user["user_id"], "storage_delete_asset", {"asset_id": asset_id})
    return {"ok": True, "deleted": n}


@router.post("/admin/storage/delete-by-user/{owner_id}")
async def storage_delete_by_user(owner_id: str, user: dict = Depends(require_super_admin)):
    n = await _hard_delete_assets({"owner_id": owner_id})
    await log_activity(user["user_id"], "storage_delete_by_user", {"owner_id": owner_id, "count": n})
    await _ops("Files deleted 🗑️", f"{n} file(s) for user {owner_id} deleted by {user.get('email')}.", "warn")
    return {"ok": True, "deleted": n}


@router.post("/admin/storage/delete-orphans")
async def storage_delete_orphans(user: dict = Depends(require_super_admin)):
    valid = [u["user_id"] async for u in db.users.find({}, {"user_id": 1})]
    n = await _hard_delete_assets({"owner_id": {"$nin": valid}})
    await log_activity(user["user_id"], "storage_delete_orphans", {"count": n})
    await _ops("Orphaned files deleted 🧹", f"{n} orphaned file(s) removed by {user.get('email')}.", "warn")
    return {"ok": True, "deleted": n}


@router.post("/admin/storage/delete-all")
async def storage_delete_all(user: dict = Depends(require_super_admin)):
    n = await _hard_delete_assets({})
    await log_activity(user["user_id"], "storage_delete_all", {"count": n})
    await _ops("ALL files deleted ⚠️", f"Every uploaded file ({n}) was deleted by {user.get('email')}.", "error")
    return {"ok": True, "deleted": n}


# ------------------------- Destructive-action audit trail -------------------------
AUDIT_ACTIONS = ["db_delete_doc", "db_purge", "db_backup", "db_restore",
                 "storage_delete_asset", "storage_delete_by_user",
                 "storage_delete_orphans", "storage_delete_all"]


@router.get("/admin/audit/destructive")
async def audit_destructive(user: dict = Depends(require_super_admin)):
    entries = await db.activity_log.find(
        {"action": {"$in": AUDIT_ACTIONS}}, {"_id": 0}
    ).sort("created_at", -1).limit(100).to_list(100)
    uids = list({e.get("user_id") for e in entries if e.get("user_id")})
    umap = {}
    async for u in db.users.find({"user_id": {"$in": uids}}, {"user_id": 1, "name": 1, "email": 1}):
        umap[u["user_id"]] = {"name": u.get("name"), "email": u.get("email")}
    for e in entries:
        info = umap.get(e.get("user_id"), {})
        e["actor_name"] = info.get("name") or e.get("user_id") or "system"
        e["actor_email"] = info.get("email") or ""
    return {"entries": entries}


# ------------------------- Ops alerts webhook (Slack/Discord) -------------------------
@router.get("/admin/ops-webhook")
async def ops_webhook_get(user: dict = Depends(require_super_admin)):
    return public_ops_webhook(await get_ops_webhook())


@router.post("/admin/ops-webhook")
async def ops_webhook_save(body: dict = Body(...), user: dict = Depends(require_super_admin)):
    keys = ("url", "enabled", "platform", "min_level", "quiet_enabled", "quiet_start", "quiet_end", "tz_offset")
    patch = {k: body[k] for k in keys if k in body}
    await save_ops_webhook(patch)
    await log_activity(user["user_id"], "ops_webhook_save", {"enabled": patch.get("enabled")})
    return public_ops_webhook(await get_ops_webhook())


@router.post("/admin/ops-webhook/test")
async def ops_webhook_test(body: dict = Body(default={}), user: dict = Depends(require_super_admin)):
    cfg = await get_ops_webhook()
    url = (body or {}).get("url") or cfg["url"]
    if not url:
        raise HTTPException(status_code=400, detail="Enter a webhook URL first (Save it, then Test).")
    ok, detail = await send_ops_alert(
        "Test alert", "Your ops webhook is connected — you'll be pinged on updates and auto-rollbacks.",
        "success", url=url, platform=(body or {}).get("platform") or cfg["platform"])
    return {"ok": ok, "detail": detail}
