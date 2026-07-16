from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from models import *

router = APIRouter()


# ---------------- Projects ----------------
@router.get("/projects")
async def list_projects(user: dict = Depends(get_current_user)):
    projs = await db.projects.find({"members": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return projs


@router.post("/projects")
async def create_project(data: ProjectInput, user: dict = Depends(get_current_user)):
    await ensure_feature("projects", user)
    doc = {"project_id": f"proj_{uuid.uuid4().hex[:12]}", "name": data.name,
           "description": data.description, "status": data.status,
           "workspace_id": data.workspace_id, "owner_id": user["user_id"],
           "members": [user["user_id"]], "created_at": now_iso()}
    await db.projects.insert_one(doc)
    await log_activity(user["user_id"], "project_create", {"name": data.name})
    doc.pop("_id", None)
    return doc


@router.put("/projects/{project_id}")
async def update_project(project_id: str, data: ProjectUpdate, user: dict = Depends(get_current_user)):
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        await db.projects.update_one({"project_id": project_id}, {"$set": updates})
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    return p


@router.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    res = await db.projects.delete_one({"project_id": project_id, "owner_id": user["user_id"]})
    if res.deleted_count:
        await db.tasks.delete_many({"project_id": project_id})
    return {"ok": True}


async def _require_project_member(project_id: str, user: dict) -> dict:
    proj = await db.projects.find_one({"project_id": project_id})
    if not proj:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.get("role") != "admin" and user["user_id"] not in proj.get("members", []):
        raise HTTPException(status_code=403, detail="You are not a member of this project")
    return proj


async def _task_for_member(task_id: str, user: dict) -> dict:
    t = await db.tasks.find_one({"task_id": task_id})
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    await _require_project_member(t["project_id"], user)
    return t


async def _enrich_tasks(tasks):
    ids = list({t.get("assignee_id") for t in tasks if t.get("assignee_id")})
    names = {}
    if ids:
        for u in await db.users.find({"user_id": {"$in": ids}}, {"_id": 0, "user_id": 1, "name": 1}).to_list(500):
            names[u["user_id"]] = u.get("name")
    for t in tasks:
        t["assignee_name"] = names.get(t.get("assignee_id"))
    return tasks


@router.get("/tasks/mine")
async def my_tasks(user: dict = Depends(get_current_user)):
    projs = await db.projects.find({"members": user["user_id"]}, {"_id": 0, "project_id": 1, "name": 1}).to_list(500)
    pmap = {p["project_id"]: p["name"] for p in projs}
    if not pmap:
        return []
    tasks = await db.tasks.find({"project_id": {"$in": list(pmap.keys())}}, {"_id": 0}).sort("created_at", -1).to_list(500)
    for t in tasks:
        t["project_name"] = pmap.get(t["project_id"])
    await _enrich_tasks(tasks)
    return tasks


@router.get("/projects/{project_id}/tasks")
async def list_tasks(project_id: str, user: dict = Depends(get_current_user)):
    await _require_project_member(project_id, user)
    tasks = await db.tasks.find({"project_id": project_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    await _enrich_tasks(tasks)
    return tasks


@router.post("/projects/{project_id}/tasks")
async def create_task(project_id: str, data: TaskInput, user: dict = Depends(get_current_user)):
    await ensure_feature("projects", user)
    await _require_project_member(project_id, user)
    doc = {"task_id": f"task_{uuid.uuid4().hex[:12]}", "project_id": project_id,
           "title": data.title, "description": data.description or "",
           "status": data.status or "todo", "assignee_id": data.assignee_id or "",
           "due_date": data.due_date or "", "owner_id": user["user_id"], "created_at": now_iso()}
    await db.tasks.insert_one(doc)
    await log_activity(user["user_id"], "task_create", {"project_id": project_id})
    doc.pop("_id", None)
    return doc


@router.put("/tasks/{task_id}")
async def update_task(task_id: str, data: TaskUpdate, user: dict = Depends(get_current_user)):
    await _task_for_member(task_id, user)
    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if updates:
        if "due_date" in updates or "assignee_id" in updates:
            updates["reminded"] = False
        await db.tasks.update_one({"task_id": task_id}, {"$set": updates})
    t = await db.tasks.find_one({"task_id": task_id}, {"_id": 0})
    return t


@router.post("/tasks/scan-reminders")
async def scan_reminders(user: dict = Depends(require_admin)):
    n = await scan_due_reminders()
    return {"reminded": n}


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    await _task_for_member(task_id, user)
    await db.tasks.delete_one({"task_id": task_id})
    return {"ok": True}


# ---------------- Project members ----------------
@router.get("/projects/{project_id}/members")
async def project_members(project_id: str, user: dict = Depends(get_current_user)):
    p = await db.projects.find_one({"project_id": project_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    members = await db.users.find({"user_id": {"$in": p.get("members", [])}}, {"_id": 0, "password_hash": 0}).to_list(500)
    for m in members:
        m["is_owner"] = m["user_id"] == p.get("owner_id")
    return members


@router.post("/projects/{project_id}/invite")
async def project_invite(project_id: str, data: EmailInput, user: dict = Depends(get_current_user)):
    p = await db.projects.find_one({"project_id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    invitee = await db.users.find_one({"email": data.email.lower()})
    if not invitee:
        raise HTTPException(status_code=404, detail="No Stitches user found with that email")
    if invitee["user_id"] in p.get("members", []):
        raise HTTPException(status_code=400, detail="User is already a member")
    await db.projects.update_one({"project_id": project_id}, {"$addToSet": {"members": invitee["user_id"]}})
    await create_notification(invitee["user_id"], "project", "Added to a project",
                              f"{user.get('name')} added you to '{p.get('name')}'", "/projects")
    return {"ok": True, "member": public_user(invitee)}


@router.post("/projects/{project_id}/remove")
async def project_remove(project_id: str, data: UserIdInput, user: dict = Depends(get_current_user)):
    p = await db.projects.find_one({"project_id": project_id})
    if not p:
        raise HTTPException(status_code=404, detail="Project not found")
    if data.user_id == p.get("owner_id"):
        raise HTTPException(status_code=400, detail="Cannot remove the project owner")
    await db.projects.update_one({"project_id": project_id}, {"$pull": {"members": data.user_id}})
    return {"ok": True}


@router.post("/workspaces/{workspace_id}/remove")
async def workspace_remove(workspace_id: str, data: UserIdInput, user: dict = Depends(get_current_user)):
    ws = await db.workspaces.find_one({"workspace_id": workspace_id})
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    if data.user_id == ws.get("owner_id"):
        raise HTTPException(status_code=400, detail="Cannot remove the workspace owner")
    await db.workspaces.update_one({"workspace_id": workspace_id}, {"$pull": {"members": data.user_id}})
    return {"ok": True}


@router.get("/admin/users/{user_id}/activity")
async def admin_user_activity(user_id: str, user: dict = Depends(require_admin)):
    logs = await db.activity_log.find({"user_id": user_id}, {"_id": 0}).sort("created_at", -1).to_list(300)
    return logs


@router.get("/admin/activity/export")
async def admin_activity_export(authorization: str = Header(None), auth: str = Query(None)):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:]
    elif auth:
        token = auth
    admin = await resolve_user_from_token(token)
    if not admin or admin.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    import csv, io
    logs = await db.activity_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(10000)
    uids = list({l.get("user_id") for l in logs if l.get("user_id")})
    users = await db.users.find({"user_id": {"$in": uids}}, {"_id": 0, "user_id": 1, "email": 1, "name": 1}).to_list(2000)
    umap = {u["user_id"]: u for u in users}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "user_id", "name", "email", "action", "meta"])
    for l in logs:
        u = umap.get(l.get("user_id"), {})
        w.writerow([l.get("created_at"), l.get("user_id"), u.get("name", ""), u.get("email", ""),
                    l.get("action"), json.dumps(l.get("meta", {}))])
    return FastResponse(content=buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=stitches_activity.csv"})


PRESENCE_WINDOW = 90


def is_online(last_seen):
    if not last_seen:
        return False
    try:
        dt = datetime.fromisoformat(last_seen)
    except Exception:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).total_seconds() < PRESENCE_WINDOW


@router.post("/presence/ping")
async def presence_ping(user: dict = Depends(get_current_user)):
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"last_seen": now_iso()}})
    return {"ok": True}


