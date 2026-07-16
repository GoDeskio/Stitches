import os
import re
import uuid
from datetime import datetime, timezone, timedelta
import httpx
from urllib.parse import parse_qsl
from fastapi import APIRouter, Depends, Request, HTTPException
from core import db, require_admin, get_current_user, now_iso, log_activity, DEFAULT_FEATURES, get_user_entitlements, get_plan_gating, resolve_user_from_token

router = APIRouter()

NMI_TRANSACT_URL = os.environ.get("NMI_TRANSACT_URL", "https://secure.nmi.com/api/transact.php")
NMI_SECRET_KEY = os.environ.get("NMI_SECRET_KEY", "")
DEFAULT_CURRENCY = os.environ.get("NMI_CURRENCY", "USD")


def _public(t):
    t = dict(t)
    t.pop("_id", None)
    return t


async def _nmi_post(payload: dict) -> dict:
    payload = {"security_key": NMI_SECRET_KEY, **payload}
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(NMI_TRANSACT_URL, data=payload)
    return dict(parse_qsl(resp.text))


def _norm_exp(raw: str) -> str:
    # Accept MM/YY, MMYY, MM/YYYY -> return MMYY
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) == 6:  # MMYYYY
        digits = digits[:2] + digits[4:]
    return digits


@router.get("/admin/payments/config")
async def payments_config(user: dict = Depends(require_admin)):
    return {
        "configured": bool(NMI_SECRET_KEY),
        "sandbox": "sandbox.nmi.com" in NMI_TRANSACT_URL,
        "currency": DEFAULT_CURRENCY,
        "provider": "nmi",
        "mode": "direct_post",
    }


@router.get("/admin/payments/stats")
async def payments_stats(user: dict = Depends(require_admin)):
    agg = await db.payment_transactions.aggregate([
        {"$match": {"type": "sale", "status": "success"}},
        {"$group": {"_id": None, "sum": {"$sum": "$amount"}, "count": {"$sum": 1}}},
    ]).to_list(1)
    collected = (agg[0]["sum"] if agg else 0) or 0
    sale_count = (agg[0]["count"] if agg else 0) or 0
    failed = await db.payment_transactions.count_documents({"type": "sale", "status": "failed"})
    refunded = await db.payment_transactions.count_documents({"type": {"$in": ["refund", "void"]}, "status": "success"})
    return {"collected": round(collected, 2), "sales": sale_count, "failed": failed, "refunds": refunded}


@router.get("/admin/payments/transactions")
async def payments_list(user: dict = Depends(require_admin)):
    rows = await db.payment_transactions.find({}).sort("created_at", -1).limit(50).to_list(50)
    return {"transactions": [_public(t) for t in rows]}


@router.post("/admin/payments/charge")
async def payments_charge(request: Request, user: dict = Depends(require_admin)):
    if not NMI_SECRET_KEY:
        raise HTTPException(status_code=400, detail="Payment gateway is not configured")
    b = await request.json()
    ccnumber = re.sub(r"\s+", "", str(b.get("ccnumber") or ""))
    ccexp = _norm_exp(str(b.get("ccexp") or ""))
    cvv = re.sub(r"\D", "", str(b.get("cvv") or ""))
    if not ccnumber or len(ccexp) != 4:
        raise HTTPException(status_code=400, detail="Enter a valid card number and expiry (MM/YY)")
    try:
        amount = round(float(b.get("amount") or 0), 2)
    except Exception:
        amount = 0
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    order_id = f"ord_{uuid.uuid4().hex[:10]}"
    payload = {
        "type": "sale",
        "amount": f"{amount:.2f}",
        "ccnumber": ccnumber,
        "ccexp": ccexp,
        "orderid": order_id,
    }
    if cvv:
        payload["cvv"] = cvv
    if b.get("description"):
        payload["order_description"] = str(b["description"]).strip()[:250]

    try:
        res = await _nmi_post(payload)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gateway error: {e}")

    success = res.get("response") == "1"
    doc = {
        "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
        "type": "sale",
        "order_id": order_id,
        "amount": amount,
        "currency": DEFAULT_CURRENCY,
        "card_last4": ccnumber[-4:],
        "email": (b.get("email") or "").strip(),
        "description": (b.get("description") or "").strip(),
        "status": "success" if success else "failed",
        "nmi_transaction_id": res.get("transactionid", ""),
        "auth_code": res.get("authcode", ""),
        "response_text": res.get("responsetext", ""),
        "created_by": user.get("email"),
        "created_at": now_iso(),
    }
    await db.payment_transactions.insert_one(doc)
    await log_activity(user["user_id"], "payment_charge", {"amount": amount, "status": doc["status"]})
    if not success:
        return {"success": False, "error": doc["response_text"] or "Payment declined", "transaction": _public(doc)}
    return {"success": True, "transaction": _public(doc)}


@router.post("/admin/payments/refund/{tx_id}")
async def payments_refund(tx_id: str, user: dict = Depends(require_admin)):
    tx = await db.payment_transactions.find_one({"tx_id": tx_id})
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.get("type") != "sale" or tx.get("status") != "success":
        raise HTTPException(status_code=400, detail="Only successful sales can be refunded")
    if tx.get("refunded"):
        raise HTTPException(status_code=400, detail="Transaction already refunded")
    nmi_id = tx.get("nmi_transaction_id")
    if not nmi_id:
        raise HTTPException(status_code=400, detail="Missing gateway transaction id")

    amount = float(tx.get("amount") or 0)
    # Refund works on settled transactions; void works on unsettled ones. Try refund, fall back to void.
    res = await _nmi_post({"type": "refund", "transactionid": nmi_id, "amount": f"{amount:.2f}"})
    op = "refund"
    if res.get("response") != "1":
        res = await _nmi_post({"type": "void", "transactionid": nmi_id})
        op = "void"
    success = res.get("response") == "1"

    doc = {
        "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
        "type": op,
        "order_id": tx.get("order_id"),
        "amount": amount,
        "currency": tx.get("currency", DEFAULT_CURRENCY),
        "email": tx.get("email", ""),
        "description": f"{op} of {tx_id}",
        "status": "success" if success else "failed",
        "nmi_transaction_id": res.get("transactionid", nmi_id),
        "response_text": res.get("responsetext", ""),
        "created_by": user.get("email"),
        "created_at": now_iso(),
    }
    await db.payment_transactions.insert_one(doc)
    if success:
        await db.payment_transactions.update_one({"tx_id": tx_id}, {"$set": {"refunded": True, "status": "refunded"}})
    await log_activity(user["user_id"], "payment_refund", {"tx_id": tx_id, "op": op, "status": doc["status"]})
    if not success:
        raise HTTPException(status_code=400, detail=doc["response_text"] or "Refund failed")
    return {"success": True, "op": op, "transaction": _public(doc)}


# ---------------- Pricing plans ----------------
INTERVALS = {"month", "year", "once"}


def _plan_public(p):
    p = dict(p)
    p.pop("_id", None)
    return p


def _plan_from_body(b: dict) -> dict:
    try:
        price = round(float(b.get("price") or 0), 2)
    except Exception:
        price = 0
    try:
        yearly = round(float(b.get("yearly_price") or 0), 2)
    except Exception:
        yearly = 0
    interval = b.get("interval") if b.get("interval") in INTERVALS else "month"
    features = [str(x).strip() for x in (b.get("features") or []) if str(x).strip()][:20]
    valid = set(DEFAULT_FEATURES.keys())
    fk = b.get("feature_keys")
    feature_keys = [k for k in fk if k in valid] if isinstance(fk, list) else None
    try:
        sort_order = int(b.get("sort_order") or 0)
    except Exception:
        sort_order = 0
    return {
        "name": (b.get("name") or "").strip()[:80],
        "description": (b.get("description") or "").strip()[:300],
        "price": price,
        "yearly_price": yearly,
        "interval": interval,
        "features": features,
        "feature_keys": feature_keys,
        "highlighted": bool(b.get("highlighted")),
        "cta": (b.get("cta") or "Get started").strip()[:40],
        "sort_order": sort_order,
        "active": b.get("active", True) if isinstance(b.get("active"), bool) else True,
    }


@router.get("/plans")
async def public_plans():
    rows = await db.plans.find({"active": True}).sort([("sort_order", 1), ("price", 1)]).to_list(50)
    return {"plans": [_plan_public(p) for p in rows]}


@router.get("/admin/plans")
async def admin_plans(user: dict = Depends(require_admin)):
    rows = await db.plans.find({}).sort([("sort_order", 1), ("price", 1)]).to_list(100)
    return {"plans": [_plan_public(p) for p in rows]}


@router.post("/admin/plans")
async def admin_create_plan(request: Request, user: dict = Depends(require_admin)):
    b = await request.json()
    doc = _plan_from_body(b)
    if not doc["name"]:
        raise HTTPException(status_code=400, detail="Plan name is required")
    doc.update({"plan_id": f"plan_{uuid.uuid4().hex[:10]}", "created_at": now_iso(), "updated_at": now_iso()})
    await db.plans.insert_one(doc)
    return _plan_public(doc)


@router.put("/admin/plans/{plan_id}")
async def admin_update_plan(plan_id: str, request: Request, user: dict = Depends(require_admin)):
    b = await request.json()
    upd = _plan_from_body(b)
    upd["updated_at"] = now_iso()
    r = await db.plans.update_one({"plan_id": plan_id}, {"$set": upd})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="Plan not found")
    p = await db.plans.find_one({"plan_id": plan_id})
    return _plan_public(p)


@router.delete("/admin/plans/{plan_id}")
async def admin_delete_plan(plan_id: str, user: dict = Depends(require_admin)):
    await db.plans.delete_one({"plan_id": plan_id})
    return {"ok": True}


async def _crm_mark_won(email: str, name: str, company: str, value: float, plan_name: str, ip: str):
    email = (email or "").strip().lower()
    if not email:
        return
    now = now_iso()
    note = {"text": f"Purchased {plan_name} (${value:.2f}) via pricing page", "author": "checkout", "created_at": now}
    existing = await db.crm_contacts.find_one({"email": email})
    if existing:
        await db.crm_contacts.update_one({"email": email}, {
            "$set": {"stage": "won", "value": value, "updated_at": now,
                     "name": existing.get("name") or name, "company": existing.get("company") or company},
            "$push": {"notes": note}})
    else:
        await db.crm_contacts.insert_one({
            "contact_id": f"crm_{uuid.uuid4().hex[:12]}", "type": "lead", "name": (name or "").strip(),
            "email": email, "company": (company or "").strip(), "phone": "", "stage": "won",
            "source": "pricing", "value": value, "tags": ["pricing"], "notes": [note],
            "user_id": None, "capture_ip": ip, "created_at": now, "updated_at": now})


@router.post("/checkout/plan")
async def checkout_plan(request: Request):
    if not NMI_SECRET_KEY:
        raise HTTPException(status_code=400, detail="Payments are not available right now")
    b = await request.json()
    plan_id = (b.get("plan_id") or "").strip()
    plan = await db.plans.find_one({"plan_id": plan_id, "active": True})
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    billing = "year" if (b.get("billing") == "year" and float(plan.get("yearly_price") or 0) > 0) else "month"
    if billing == "year":
        amount = round(float(plan.get("yearly_price") or 0), 2)
        interval = "year"
    else:
        amount = round(float(plan.get("price") or 0), 2)
        interval = plan.get("interval") or "month"
    if amount <= 0:
        raise HTTPException(status_code=400, detail="This plan is free — just sign up.")

    email = (b.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    ip = (request.headers.get("x-forwarded-for", "").split(",")[0].strip()
          or (request.client.host if request.client else "")) or "unknown"
    recent = await db.payment_transactions.count_documents(
        {"capture_ip": ip, "created_at": {"$gte": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()}})
    if recent >= 6:
        raise HTTPException(status_code=429, detail="Too many attempts. Please try again shortly.")

    ccnumber = re.sub(r"\s+", "", str(b.get("ccnumber") or ""))
    ccexp = _norm_exp(str(b.get("ccexp") or ""))
    cvv = re.sub(r"\D", "", str(b.get("cvv") or ""))
    if not ccnumber or len(ccexp) != 4:
        raise HTTPException(status_code=400, detail="Enter a valid card number and expiry (MM/YY)")

    order_id = f"sub_{uuid.uuid4().hex[:10]}"
    payload = {"type": "sale", "amount": f"{amount:.2f}", "ccnumber": ccnumber, "ccexp": ccexp,
               "orderid": order_id, "order_description": f"{plan.get('name')} plan"}
    if cvv:
        payload["cvv"] = cvv
    try:
        res = await _nmi_post(payload)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gateway error: {e}")

    success = res.get("response") == "1"
    doc = {
        "tx_id": f"tx_{uuid.uuid4().hex[:12]}", "type": "sale", "order_id": order_id,
        "amount": amount, "currency": DEFAULT_CURRENCY, "card_last4": ccnumber[-4:],
        "email": email, "description": f"{plan.get('name')} plan", "plan_id": plan_id,
        "plan_name": plan.get("name"), "plan_interval": interval, "billing": billing,
        "status": "success" if success else "failed", "nmi_transaction_id": res.get("transactionid", ""),
        "auth_code": res.get("authcode", ""), "response_text": res.get("responsetext", ""),
        "source": "pricing", "capture_ip": ip, "created_by": "checkout", "created_at": now_iso(),
    }
    await db.payment_transactions.insert_one(doc)
    if not success:
        return {"success": False, "error": doc["response_text"] or "Payment declined"}
    await _crm_mark_won(email, b.get("name") or "", b.get("company") or "", amount, plan.get("name"), ip)
    token = request.cookies.get("session_token") or request.cookies.get("access_token")
    if not token:
        h = request.headers.get("Authorization", "")
        if h.startswith("Bearer "):
            token = h[7:]
    buyer = await resolve_user_from_token(token) if token else None
    if buyer:
        await db.users.update_one({"user_id": buyer["user_id"]},
            {"$set": {"plan_id": plan_id, "plan_billing": billing, "plan_since": now_iso()}})
    return {"success": True, "transaction_id": doc["nmi_transaction_id"], "plan": plan.get("name")}


# ---------------- Entitlements & plan gating ----------------
@router.get("/me/entitlements")
async def my_entitlements(user: dict = Depends(get_current_user)):
    return await get_user_entitlements(user)


@router.get("/admin/plan-gating")
async def admin_get_gating(user: dict = Depends(require_admin)):
    return {"enabled": await get_plan_gating()}


@router.post("/admin/plan-gating")
async def admin_set_gating(request: Request, user: dict = Depends(require_admin)):
    b = await request.json()
    enabled = bool(b.get("enabled"))
    await db.settings.update_one({"key": "plan_gating"}, {"$set": {"value": {"enabled": enabled}}}, upsert=True)
    await log_activity(user["user_id"], "plan_gating_toggle", {"enabled": enabled})
    return {"enabled": enabled}


@router.post("/admin/users/{user_id}/plan")
async def admin_set_user_plan(user_id: str, request: Request, user: dict = Depends(require_admin)):
    b = await request.json()
    pid = (b.get("plan_id") or "").strip() or None
    if pid and not await db.plans.find_one({"plan_id": pid}):
        raise HTTPException(status_code=404, detail="Plan not found")
    r = await db.users.update_one({"user_id": user_id}, {"$set": {"plan_id": pid, "plan_since": now_iso()}})
    if not r.matched_count:
        raise HTTPException(status_code=404, detail="User not found")
    return {"ok": True, "plan_id": pid}
