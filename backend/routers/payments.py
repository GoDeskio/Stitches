import os
import uuid
import httpx
from fastapi import APIRouter, Depends, Request, HTTPException
from core import db, require_admin, now_iso, log_activity

router = APIRouter()

NMI_API_BASE = os.environ.get("NMI_API_BASE", "https://secure.nmi.com/api/v5").rstrip("/")
NMI_SECRET_KEY = os.environ.get("NMI_SECRET_KEY", "")
NMI_TOKENIZATION_KEY = os.environ.get("NMI_TOKENIZATION_KEY", "")
DEFAULT_CURRENCY = os.environ.get("NMI_CURRENCY", "USD")


def _public(t):
    t = dict(t)
    t.pop("_id", None)
    return t


async def _nmi_post(path: str, body: dict) -> dict:
    headers = {"Authorization": NMI_SECRET_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=30) as http:
        resp = await http.post(f"{NMI_API_BASE}/{path.lstrip('/')}", json=body, headers=headers)
    try:
        return resp.json()
    except Exception:
        return {"response": "3", "response_text": f"Gateway HTTP {resp.status_code}: {resp.text[:200]}"}


@router.get("/admin/payments/config")
async def payments_config(user: dict = Depends(require_admin)):
    return {
        "configured": bool(NMI_SECRET_KEY and NMI_TOKENIZATION_KEY),
        "tokenization_key": NMI_TOKENIZATION_KEY,
        "sandbox": "sandbox" in NMI_TOKENIZATION_KEY.lower() or NMI_SECRET_KEY.startswith("v4_secret"),
        "currency": DEFAULT_CURRENCY,
        "provider": "nmi",
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
    token = (b.get("payment_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Missing payment token")
    try:
        amount = round(float(b.get("amount") or 0), 2)
    except Exception:
        amount = 0
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than 0")

    body = {
        "amount": amount,
        "currency": DEFAULT_CURRENCY,
        "payment_details": {"payment_token": token},
    }
    try:
        res = await _nmi_post("payments/sale", body)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gateway error: {e}")

    success = str(res.get("response")) == "1"
    doc = {
        "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
        "type": "sale",
        "amount": amount,
        "currency": DEFAULT_CURRENCY,
        "email": (b.get("email") or "").strip(),
        "description": (b.get("description") or "").strip(),
        "status": "success" if success else "failed",
        "nmi_transaction_id": str(res.get("id") or res.get("transactionid") or ""),
        "auth_code": str(res.get("auth_code") or res.get("authcode") or ""),
        "response_text": res.get("response_text") or res.get("responsetext") or "",
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
    # Try refund (settled); fall back to void (unsettled) if refund is rejected.
    res = await _nmi_post(f"payments/{nmi_id}/refund", {"amount": f"{amount:.2f}"})
    op = "refund"
    if str(res.get("response")) != "1":
        res = await _nmi_post(f"payments/{nmi_id}/void", {})
        op = "void"
    success = str(res.get("response")) == "1"

    doc = {
        "tx_id": f"tx_{uuid.uuid4().hex[:12]}",
        "type": op,
        "amount": amount,
        "currency": tx.get("currency", DEFAULT_CURRENCY),
        "email": tx.get("email", ""),
        "description": f"{op} of {tx_id}",
        "status": "success" if success else "failed",
        "nmi_transaction_id": str(res.get("id") or nmi_id),
        "response_text": res.get("response_text") or res.get("responsetext") or "",
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
