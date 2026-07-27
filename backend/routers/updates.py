import os
import re
import json
import uuid
import asyncio
import subprocess
from datetime import datetime, timezone, timedelta
import httpx
from fastapi import APIRouter, Depends, Request, HTTPException
from core import db, require_admin, now_iso, log_activity, create_notification, _fernet

router = APIRouter()

APP_DIR = os.environ.get("APP_DIR", "/app")
DEFAULT_REPO = "https://github.com/GoDeskio/Stitches.git"
UPDATE_SCRIPT = os.path.join(APP_DIR, "scripts", "update.sh")
RESTORE_SCRIPT = os.path.join(APP_DIR, "scripts", "restore.sh")
BACKUP_DIR = os.environ.get("BACKUP_DIR", os.path.join(APP_DIR, "backups"))


def _is_self_hosted() -> bool:
    if os.environ.get("SELF_HOSTED", "").lower() in ("1", "true", "yes"):
        return True
    # Managed Emergent environment ships a .emergent folder; treat that as NOT self-hosted.
    return not os.path.isdir(os.path.join(APP_DIR, ".emergent"))


def _local_sha() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=APP_DIR, capture_output=True, text=True, timeout=10)
        return r.stdout.strip()[:40]
    except Exception:
        return ""


def _read_version() -> str:
    try:
        with open(os.path.join(APP_DIR, "VERSION")) as f:
            return f.read().strip()
    except Exception:
        return ""


def _parse_repo(url: str):
    if not url:
        return None, None
    m = re.search(r"github\.com[/:]([^/]+)/([^/.]+)", url.strip())
    if not m:
        return None, None
    return m.group(1), m.group(2)


async def _get_config() -> dict:
    doc = await db.settings.find_one({"key": "update_config"})
    cfg = (doc or {}).get("value", {}) if doc else {}
    token = ""
    if cfg.get("token_enc"):
        try:
            token = _fernet.decrypt(cfg["token_enc"].encode()).decode()
        except Exception:
            token = ""
    elif cfg.get("token"):  # legacy plaintext fallback
        token = cfg.get("token", "")
    return {
        "repo_url": cfg.get("repo_url", DEFAULT_REPO),
        "branch": cfg.get("branch", "main"),
        "token": token,
        "enabled": cfg.get("enabled", True),
        "auto_apply": cfg.get("auto_apply", False),
        "auto_rollback": cfg.get("auto_rollback", False),
        "applied_sha": cfg.get("applied_sha", ""),
        "last_check": cfg.get("last_check"),
        "latest_sha": cfg.get("latest_sha", ""),
        "latest_message": cfg.get("latest_message", ""),
        "latest_date": cfg.get("latest_date", ""),
        "update_available": cfg.get("update_available", False),
    }


async def _save_config(patch: dict):
    sets = {}
    for k, v in patch.items():
        if k == "token":
            # Encrypt the PAT at rest; clear any legacy plaintext value.
            sets["value.token_enc"] = _fernet.encrypt(v.encode()).decode() if v else ""
            sets["value.token"] = ""
        else:
            sets[f"value.{k}"] = v
    await db.settings.update_one({"key": "update_config"}, {"$set": sets}, upsert=True)


async def _github_latest(owner: str, repo: str, branch: str, token: str) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "Stitches-Updater"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(timeout=20) as h:
        r = await h.get(f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}", headers=headers)
    if r.status_code == 404:
        raise HTTPException(status_code=400, detail="Repository or branch not found (check the URL/branch, or add a token for private repos)")
    if r.status_code in (401, 403):
        raise HTTPException(status_code=400, detail="GitHub denied access — add a valid token for private repos or check rate limits")
    if r.status_code >= 300:
        raise HTTPException(status_code=400, detail=f"GitHub error {r.status_code}")
    d = r.json()
    return {
        "sha": d.get("sha", ""),
        "message": (d.get("commit", {}).get("message") or "").split("\n")[0][:200],
        "date": d.get("commit", {}).get("committer", {}).get("date", ""),
        "author": d.get("commit", {}).get("author", {}).get("name", ""),
        "url": d.get("html_url", ""),
    }


def _public_cfg(cfg: dict) -> dict:
    c = dict(cfg)
    c["has_token"] = bool(c.get("token"))
    c.pop("token", None)
    c["current_sha"] = cfg.get("applied_sha") or _local_sha()
    c["version"] = _read_version()
    c["self_hosted"] = _is_self_hosted()
    return c


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/admin/updates/config")
async def get_update_config(user: dict = Depends(require_admin)):
    return _public_cfg(await _get_config())


@router.post("/admin/updates/config")
async def set_update_config(request: Request, user: dict = Depends(require_admin)):
    b = await request.json()
    patch = {}
    if "repo_url" in b:
        patch["repo_url"] = (b.get("repo_url") or DEFAULT_REPO).strip()
    if "branch" in b:
        patch["branch"] = (b.get("branch") or "main").strip()
    if "token" in b and b.get("token") is not None:
        patch["token"] = str(b.get("token")).strip()
    if "enabled" in b:
        patch["enabled"] = bool(b.get("enabled"))
    if "auto_apply" in b:
        patch["auto_apply"] = bool(b.get("auto_apply"))
    if "auto_rollback" in b:
        patch["auto_rollback"] = bool(b.get("auto_rollback"))
    owner, repo = _parse_repo(patch.get("repo_url", (await _get_config())["repo_url"]))
    if not owner:
        raise HTTPException(status_code=400, detail="Enter a valid GitHub repository URL")
    await _save_config(patch)
    await log_activity(user["user_id"], "update_config", {k: v for k, v in patch.items() if k != "token"})
    return _public_cfg(await _get_config())


async def _do_check(cfg: dict) -> dict:
    owner, repo = _parse_repo(cfg["repo_url"])
    if not owner:
        raise HTTPException(status_code=400, detail="No repository configured")
    latest = await _github_latest(owner, repo, cfg["branch"], cfg.get("token", ""))
    current = cfg.get("applied_sha") or _local_sha()
    available = bool(latest["sha"] and current and latest["sha"][:12] != current[:12])
    await _save_config({
        "last_check": now_iso(), "latest_sha": latest["sha"], "latest_message": latest["message"],
        "latest_date": latest["date"], "update_available": available,
    })
    return {"current_sha": current, "update_available": available, "latest": latest}


@router.post("/admin/updates/check")
async def check_updates(user: dict = Depends(require_admin)):
    return await _do_check(await _get_config())


@router.get("/admin/updates/available")
async def updates_available(user: dict = Depends(require_admin)):
    cfg = await _get_config()
    return {"update_available": bool(cfg.get("update_available")), "latest_message": cfg.get("latest_message", ""),
            "latest_date": cfg.get("latest_date", ""), "self_hosted": _is_self_hosted()}


@router.get("/admin/updates/status")
async def update_status(user: dict = Depends(require_admin)):
    job = await db.update_jobs.find_one({}, sort=[("started_at", -1)])
    if not job:
        return {"job": None}
    stamp = job.get("stamp")
    if stamp:
        d = os.path.join(BACKUP_DIR, stamp)
        lf = os.path.join(d, "update.log")
        if os.path.exists(lf):
            try:
                with open(lf) as f:
                    job["logs"] = f.read().splitlines()[-200:]
            except Exception:
                pass
        rf = os.path.join(d, "result.json")
        if os.path.exists(rf) and job.get("status") == "running":
            try:
                with open(rf) as f:
                    res = json.load(f)
                job["status"] = res.get("status", "success")
                await db.update_jobs.update_one({"job_id": job["job_id"]},
                    {"$set": {"status": job["status"], "rolled_back": res.get("rolled_back", False),
                              "finished_at": res.get("finished_at", now_iso())}})
                await _alert_admins_job(job, res.get("rolled_back", False))
            except Exception:
                pass
    job.pop("_id", None)
    return {"job": job}


async def _alert_admins_job(job: dict, rolled_back: bool):
    if job.get("alerted") or job.get("type") != "update":
        return
    if job.get("status") not in ("failed", "rolled_back"):
        return
    if rolled_back:
        title = "Update auto-rolled back"
        msg = "A site update failed its health check and was automatically rolled back to the previous working version. Your site is back online."
    else:
        title = "Update failed"
        msg = "A site update did not complete successfully and was NOT rolled back. Review the update log in Admin → Updates."
    async for a in db.users.find({"role": "admin"}, {"user_id": 1}):
        try:
            await create_notification(a["user_id"], "system", title, msg, "/admin")
        except Exception:
            pass
    try:
        from services.ops_alerts import send_ops_alert
        await send_ops_alert(title, msg, "warn" if rolled_back else "error", event="update")
    except Exception:
        pass
    await db.update_jobs.update_one({"job_id": job["job_id"]}, {"$set": {"alerted": True}})


def _launch_update_script(script: str, stamp: str, cfg: dict, extra_env: dict):
    env = os.environ.copy()
    env.update({
        "REPO_URL": cfg["repo_url"], "BRANCH": cfg["branch"], "REPO_TOKEN": cfg.get("token", ""),
        "APP_DIR": APP_DIR, "BACKUP_DIR": BACKUP_DIR, "STAMP": stamp,
        "AUTO_ROLLBACK": "true" if cfg.get("auto_rollback") else "false",
        "HEALTH_URL": os.environ.get("HEALTH_URL", "http://localhost:8001/api/health"),
    })
    env.update(extra_env or {})
    os.makedirs(os.path.join(BACKUP_DIR, stamp), exist_ok=True)
    # Detached (own session) so the script survives the backend restart it triggers.
    subprocess.Popen(["bash", script], cwd=APP_DIR, env=env,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


async def _start_apply(cfg: dict, started_by: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    job_id = f"upd_{uuid.uuid4().hex[:12]}"
    await db.update_jobs.insert_one({"job_id": job_id, "status": "running", "logs": [], "type": "update",
                                     "stamp": stamp, "repo_url": cfg["repo_url"], "branch": cfg["branch"],
                                     "started_by": started_by, "started_at": now_iso(), "finished_at": None})
    _launch_update_script(UPDATE_SCRIPT, stamp, cfg, {})
    return job_id


@router.post("/admin/updates/apply")
async def apply_update(user: dict = Depends(require_admin)):
    cfg = await _get_config()
    if not _is_self_hosted():
        return {"applied": False, "managed": True,
                "message": "This instance runs on the Emergent platform, where deploys are managed for you. Use the platform's Deploy flow to ship updates. True auto-apply runs on a self-hosted server (set SELF_HOSTED=true)."}
    if await db.update_jobs.find_one({"status": "running"}):
        raise HTTPException(status_code=409, detail="An update is already in progress")
    if not os.path.exists(UPDATE_SCRIPT):
        raise HTTPException(status_code=400, detail="Update script missing (scripts/update.sh)")
    job_id = await _start_apply(cfg, user.get("email"))
    await log_activity(user["user_id"], "update_apply", {"repo": cfg["repo_url"]})
    return {"applied": True, "job_id": job_id}


async def scan_updates():
    cfg = await _get_config()
    if not cfg.get("enabled"):
        return
    last = cfg.get("last_check")
    if last:
        try:
            lt = datetime.fromisoformat(last)
            if lt.tzinfo is None:
                lt = lt.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - lt < timedelta(minutes=25):
                return
        except Exception:
            pass
    was_available = cfg.get("update_available")
    try:
        res = await _do_check(cfg)
    except Exception:
        return
    if res["update_available"] and not was_available:
        async for a in db.users.find({"role": "admin"}, {"user_id": 1}):
            try:
                await create_notification(a["user_id"], "system", "New site version available",
                                          res["latest"]["message"] or "A new version is ready to install.", "/admin")
            except Exception:
                pass
        if cfg.get("auto_apply") and _is_self_hosted() and os.path.exists(UPDATE_SCRIPT):
            if not await db.update_jobs.find_one({"status": "running"}):
                await _start_apply(cfg, "auto")


# ---------------- Backups & rollback ----------------
@router.get("/admin/updates/backups")
async def list_backups(user: dict = Depends(require_admin)):
    items = []
    if os.path.isdir(BACKUP_DIR):
        for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
            d = os.path.join(BACKUP_DIR, name)
            if not os.path.isdir(d):
                continue
            man = {"stamp": name, "created_at": "", "pre_sha": "", "has_db": False}
            mf = os.path.join(d, "manifest.json")
            if os.path.exists(mf):
                try:
                    with open(mf) as f:
                        man.update(json.load(f))
                except Exception:
                    pass
            man["has_env"] = os.path.exists(os.path.join(d, "backend", ".env"))
            items.append(man)
    return {"backups": items[:50], "self_hosted": _is_self_hosted()}


async def _run_restore(job_id: str, stamp: str):
    async def logline(msg):
        await db.update_jobs.update_one({"job_id": job_id}, {"$push": {"logs": f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}"}})
    env = os.environ.copy()
    env["STAMP"] = stamp
    env["APP_DIR"] = APP_DIR
    env["BACKUP_DIR"] = BACKUP_DIR
    try:
        await logline(f"Restoring from backup {stamp}")
        proc = await asyncio.create_subprocess_exec(
            "bash", RESTORE_SCRIPT, cwd=APP_DIR, env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            await logline(line.decode(errors="ignore").rstrip()[:500])
        rc = await proc.wait()
        status = "success" if rc == 0 else "failed"
        if rc == 0:
            await _save_config({"applied_sha": _local_sha(), "update_available": False})
        await db.update_jobs.update_one({"job_id": job_id}, {"$set": {"status": status, "finished_at": now_iso()}})
        await logline("Restore complete ✔" if rc == 0 else f"Restore failed (exit {rc})")
    except Exception as e:
        await db.update_jobs.update_one({"job_id": job_id}, {"$set": {"status": "failed", "finished_at": now_iso()}})
        await logline(f"Error: {e}")


@router.post("/admin/updates/restore/{stamp}")
async def restore_backup(stamp: str, user: dict = Depends(require_admin)):
    if not re.fullmatch(r"[0-9_]+", stamp) or not os.path.isdir(os.path.join(BACKUP_DIR, stamp)):
        raise HTTPException(status_code=404, detail="Backup not found")
    if not _is_self_hosted():
        return {"restored": False, "managed": True,
                "message": "Rollback runs on a self-hosted server (SELF_HOSTED=true). On this managed instance, use the platform's rollback/deploy tools."}
    if await db.update_jobs.find_one({"status": "running"}):
        raise HTTPException(status_code=409, detail="An update/restore is already in progress")
    if not os.path.exists(RESTORE_SCRIPT):
        raise HTTPException(status_code=400, detail="Restore script missing (scripts/restore.sh)")
    job_id = f"rst_{uuid.uuid4().hex[:12]}"
    await db.update_jobs.insert_one({"job_id": job_id, "status": "running", "logs": [], "type": "restore",
                                     "stamp": stamp, "started_by": user.get("email"), "started_at": now_iso(), "finished_at": None})
    asyncio.create_task(_run_restore(job_id, stamp))
    await log_activity(user["user_id"], "update_restore", {"stamp": stamp})
    return {"restored": True, "job_id": job_id}
