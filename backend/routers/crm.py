import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from core import db, require_admin, now_iso

router = APIRouter()

STAGES = ["new", "contacted", "qualified", "proposal", "won", "lost"]


def _public(c):
    c = dict(c)
    c.pop("_id", None)
    return c


async def _touch(contact_id):
    await db.crm_contacts.update_one({"contact_id": contact_id}, {"$set": {"updated_at": now_iso()}})


@router.get("/admin/crm/stats")
async def crm_stats(user: dict = Depends(require_admin)):
    # Funnel: visitors (unique heatmap sessions) -> leads -> users
    since = datetime.now(timezone.utc) - timedelta(days=30)
    try:
        sessions = await db.heat_events.distinct("session_id", {"created_at": {"$gte": since}})
        visitors = len([s for s in sessions if s])
    except Exception:
        visitors = 0
    if not visitors:
        visitors = await db.heat_events.count_documents({})
    leads = await db.crm_contacts.count_documents({"type": "lead"})
    users = await db.users.count_documents({})
    by_stage = {}
    for s in STAGES:
        by_stage[s] = await db.crm_contacts.count_documents({"type": "lead", "stage": s})
    won = by_stage.get("won", 0)
    return {"visitors": visitors, "leads": leads, "users": users, "customers": won,
            "by_stage": by_stage,
            "visitor_to_lead": round(leads * 100 / visitors) if visitors else 0,
            "lead_to_customer": round(won * 100 / leads) if leads else 0}


@router.get("/admin/crm/contacts")
async def crm_list(type: str = Query(None), stage: str = Query(None), q: str = Query(None),
                   page: int = Query(1), user: dict = Depends(require_admin)):
    query = {}
    if type in ("lead", "user", "visitor"):
        query["type"] = type
    if stage in STAGES:
        query["stage"] = stage
    if q:
        query["$or"] = [{"name": {"$regex": q, "$options": "i"}},
                        {"email": {"$regex": q, "$options": "i"}},
                        {"company": {"$regex": q, "$options": "i"}}]
    per = 25
    skip = max(0, (page - 1)) * per
    total = await db.crm_contacts.count_documents(query)
    rows = await db.crm_contacts.find(query).sort("updated_at", -1).skip(skip).limit(per).to_list(per)
    return {"contacts": [_public(c) for c in rows], "total": total, "page": page, "pages": (total + per - 1) // per}


@router.post("/admin/crm/contacts")
async def crm_create(request: Request, user: dict = Depends(require_admin)):
    b = await request.json()
    email = (b.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if await db.crm_contacts.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="A contact with this email already exists")
    now = now_iso()
    doc = {"contact_id": f"crm_{uuid.uuid4().hex[:12]}", "type": b.get("type", "lead"),
           "name": (b.get("name") or "").strip(), "email": email,
           "company": (b.get("company") or "").strip(), "phone": (b.get("phone") or "").strip(),
           "stage": b.get("stage") if b.get("stage") in STAGES else "new",
           "source": (b.get("source") or "manual").strip(), "value": float(b.get("value") or 0),
           "tags": b.get("tags") or [], "notes": [], "user_id": None,
           "created_at": now, "updated_at": now}
    await db.crm_contacts.insert_one(doc)
    return _public(doc)


@router.get("/admin/crm/contacts/{contact_id}")
async def crm_get(contact_id: str, user: dict = Depends(require_admin)):
    c = await db.crm_contacts.find_one({"contact_id": contact_id})
    if not c:
        raise HTTPException(status_code=404, detail="Not found")
    return _public(c)


@router.put("/admin/crm/contacts/{contact_id}")
async def crm_update(contact_id: str, request: Request, user: dict = Depends(require_admin)):
    b = await request.json()
    upd = {}
    for f in ("name", "company", "phone", "source"):
        if f in b:
            upd[f] = (b.get(f) or "").strip()
    if "stage" in b and b["stage"] in STAGES:
        upd["stage"] = b["stage"]
    if "type" in b and b["type"] in ("lead", "user", "visitor"):
        upd["type"] = b["type"]
    if "value" in b:
        upd["value"] = float(b.get("value") or 0)
    if "tags" in b:
        upd["tags"] = b.get("tags") or []
    if not upd:
        raise HTTPException(status_code=400, detail="Nothing to update")
    upd["updated_at"] = now_iso()
    r = await db.crm_contacts.update_one({"contact_id": contact_id}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Not found")
    return await crm_get(contact_id, user)


@router.post("/admin/crm/contacts/{contact_id}/notes")
async def crm_add_note(contact_id: str, request: Request, user: dict = Depends(require_admin)):
    b = await request.json()
    text = (b.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Note text required")
    note = {"text": text[:2000], "author": user.get("name") or user.get("email"), "created_at": now_iso()}
    r = await db.crm_contacts.update_one({"contact_id": contact_id},
                                         {"$push": {"notes": note}, "$set": {"updated_at": now_iso()}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Not found")
    return note


@router.delete("/admin/crm/contacts/{contact_id}")
async def crm_delete(contact_id: str, user: dict = Depends(require_admin)):
    await db.crm_contacts.delete_one({"contact_id": contact_id})
    return {"ok": True}


@router.post("/admin/crm/sync-users")
async def crm_sync_users(user: dict = Depends(require_admin)):
    added = 0
    async for u in db.users.find({}, {"_id": 0, "user_id": 1, "name": 1, "email": 1, "company": 1, "created_at": 1}):
        email = (u.get("email") or "").lower()
        if not email:
            continue
        existing = await db.crm_contacts.find_one({"email": email})
        now = now_iso()
        if existing:
            await db.crm_contacts.update_one({"email": email},
                                             {"$set": {"type": "user", "user_id": u.get("user_id"),
                                                       "name": existing.get("name") or u.get("name", ""),
                                                       "updated_at": now}})
        else:
            await db.crm_contacts.insert_one({
                "contact_id": f"crm_{uuid.uuid4().hex[:12]}", "type": "user",
                "name": u.get("name", ""), "email": email, "company": u.get("company", ""),
                "phone": "", "stage": "won", "source": "signup", "value": 0, "tags": [],
                "notes": [], "user_id": u.get("user_id"),
                "created_at": u.get("created_at") or now, "updated_at": now})
            added += 1
    total = await db.crm_contacts.count_documents({"type": "user"})
    return {"ok": True, "added": added, "total_users": total}


# ---------------- Public lead capture ----------------
@router.post("/leads")
async def capture_lead(request: Request):
    b = await request.json()
    email = (b.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else "")) or "unknown"
    recent = await db.crm_contacts.count_documents(
        {"capture_ip": ip, "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()}})
    if recent >= 5:
        raise HTTPException(status_code=429, detail="Too many submissions. Please try again later.")
    now = now_iso()
    existing = await db.crm_contacts.find_one({"email": email})
    if existing:
        return {"ok": True, "duplicate": True}
    await db.crm_contacts.insert_one({
        "contact_id": f"crm_{uuid.uuid4().hex[:12]}", "type": "lead",
        "name": (b.get("name") or "").strip(), "email": email,
        "company": (b.get("company") or "").strip(), "phone": (b.get("phone") or "").strip(),
        "stage": "new", "source": (b.get("source") or "website").strip()[:60], "value": 0,
        "tags": [], "notes": [{"text": (b.get("message") or "").strip()[:2000], "author": "visitor", "created_at": now}] if b.get("message") else [],
        "user_id": None, "capture_ip": ip, "created_at": now, "updated_at": now})
    # notify admins (best-effort)
    try:
        from services.email import send_email_detailed
        admins = await db.users.find({"role": "admin"}, {"_id": 0, "email": 1}).to_list(20)
        html = (f"<div style='font-family:-apple-system,Segoe UI,sans-serif;max-width:520px;margin:0 auto;background:#f6f6f6;padding:24px'>"
                f"<h2 style='color:#c0202e;font-size:18px;margin:0 0 8px'>New lead captured</h2>"
                f"<p style='font-size:14px;color:#333'><b>{(b.get('name') or 'Someone')}</b> ({email})"
                f"{(' · ' + b['company']) if b.get('company') else ''} requested a demo.</p>"
                f"{('<p style=font-size:13px;color:#555>“' + b['message'][:400] + '”</p>') if b.get('message') else ''}"
                f"<p style='font-size:12px;color:#999'>View them in Admin → CRM.</p></div>")
        for a in admins:
            if a.get("email"):
                await send_email_detailed(a["email"], f"New lead: {b.get('name') or email}", html)
    except Exception:
        pass
    return {"ok": True}
