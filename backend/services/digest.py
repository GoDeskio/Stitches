import os
from datetime import datetime, timezone, timedelta
from core import db, logger, now_iso
from services.email import send_email_detailed

DEFAULT_DIGEST = {
    "enabled": False,
    "frequency": "weekly",   # daily | weekly | monthly
    "day_of_week": 0,        # 0=Monday ... 6=Sunday (weekly)
    "day_of_month": 1,       # 1..28 (monthly)
    "hour": 9,               # 0..23 (UTC)
    "recipient": "admin@godesk.io",
    "last_sent": "",
}

_WINDOW_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}
_FREQ_LABEL = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly"}


async def get_digest_config():
    doc = await db.settings.find_one({"key": "digest_config"})
    cfg = dict(DEFAULT_DIGEST)
    if doc:
        cfg.update(doc.get("value", {}))
    return cfg


async def save_digest_config(patch: dict):
    cfg = await get_digest_config()
    cfg.update(patch)
    await db.settings.update_one({"key": "digest_config"},
                                 {"$set": {"key": "digest_config", "value": cfg}}, upsert=True)
    return cfg


async def _collect(frequency: str):
    days = _WINDOW_DAYS.get(frequency, 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    signups = await db.users.find({"created_at": {"$gte": cutoff_iso}},
                                  {"_id": 0, "name": 1, "email": 1, "created_at": 1}).sort("created_at", -1).to_list(50)
    open_count = await db.support_requests.count_documents({"status": "open"})
    open_reqs = await db.support_requests.find({"status": "open"}, {"_id": 0, "subject": 1, "user_email": 1, "created_at": 1}).sort("created_at", -1).to_list(10)

    top_paths = await db.heat_events.aggregate([
        {"$match": {"type": "click", "created_at": {"$gte": cutoff}}},
        {"$group": {"_id": "$path", "clicks": {"$sum": 1}}},
        {"$sort": {"clicks": -1}}, {"$limit": 8},
    ]).to_list(8)

    total_runs = await db.integration_runs.count_documents({"created_at": {"$gte": cutoff_iso}})
    ok_runs = await db.integration_runs.count_documents({"created_at": {"$gte": cutoff_iso}, "ok": True})
    rate = round(ok_runs * 100 / total_runs) if total_runs else 100

    return {"days": days, "signups": signups, "open_count": open_count, "open_reqs": open_reqs,
            "top_paths": top_paths, "total_runs": total_runs, "ok_runs": ok_runs,
            "fail_runs": total_runs - ok_runs, "success_rate": rate}


def _fmt_date(iso):
    try:
        return datetime.fromisoformat(iso).strftime("%b %d")
    except Exception:
        return ""


def build_digest_html(frequency: str, data: dict):
    label = _FREQ_LABEL.get(frequency, "Weekly")
    d = data["days"]
    rows = []

    def card(title, inner):
        return (f"<div style='background:#fff;border:1px solid #eee;border-radius:14px;padding:18px 20px;margin:0 0 14px'>"
                f"<h3 style='margin:0 0 10px;font-size:15px;color:#c0202e'>{title}</h3>{inner}</div>")

    # Signups
    if data["signups"]:
        items = "".join(f"<li style='margin:2px 0'>{(s.get('name') or 'User')} &lt;{s.get('email','')}&gt; "
                        f"<span style='color:#999'>· {_fmt_date(s.get('created_at',''))}</span></li>" for s in data["signups"][:12])
        rows.append(card(f"New signups ({len(data['signups'])})", f"<ul style='margin:0;padding-left:18px;font-size:13px;color:#333'>{items}</ul>"))
    else:
        rows.append(card("New signups", "<p style='margin:0;font-size:13px;color:#999'>No new signups in this period.</p>"))

    # Support
    if data["open_reqs"]:
        items = "".join(f"<li style='margin:2px 0'>{(r.get('subject') or 'Request')} "
                        f"<span style='color:#999'>· {r.get('user_email','')}</span></li>" for r in data["open_reqs"])
        rows.append(card(f"Open support requests ({data['open_count']})", f"<ul style='margin:0;padding-left:18px;font-size:13px;color:#333'>{items}</ul>"))
    else:
        rows.append(card("Open support requests", "<p style='margin:0;font-size:13px;color:#2e9e5b'>All caught up — no open requests.</p>"))

    # Top pages
    if data["top_paths"]:
        items = "".join(f"<li style='margin:2px 0'><code>{p['_id'] or '/'}</code> "
                        f"<span style='color:#999'>· {p['clicks']} clicks</span></li>" for p in data["top_paths"])
        rows.append(card("Top-clicked pages", f"<ul style='margin:0;padding-left:18px;font-size:13px;color:#333'>{items}</ul>"))

    # Automation
    rows.append(card("Automation health",
                     f"<p style='margin:0;font-size:13px;color:#333'>{data['ok_runs']}/{data['total_runs']} runs succeeded "
                     f"(<b>{data['success_rate']}%</b>) · {data['fail_runs']} failures</p>"))

    body = "".join(rows)
    return (f"<div style='font-family:-apple-system,Segoe UI,sans-serif;max-width:600px;margin:0 auto;background:#f6f6f6;padding:24px'>"
            f"<h1 style='font-size:22px;color:#c0202e;margin:0 0 4px'>Stitches {label} Digest</h1>"
            f"<p style='color:#777;font-size:13px;margin:0 0 20px'>Summary of the last {d} day(s) · generated {datetime.now(timezone.utc).strftime('%b %d, %Y %H:%M UTC')}</p>"
            f"{body}"
            f"<p style='color:#aaa;font-size:11px;text-align:center;margin-top:20px'>You receive this because digest emails are enabled in the Stitches admin dashboard.</p>"
            f"</div>")


async def send_digest_now(frequency: str = None, recipient: str = None):
    cfg = await get_digest_config()
    freq = frequency or cfg.get("frequency", "weekly")
    to = (recipient or cfg.get("recipient") or "").strip()
    if not to:
        return False, "No recipient configured"
    data = await _collect(freq)
    html = build_digest_html(freq, data)
    subject = f"Stitches {_FREQ_LABEL.get(freq, 'Weekly')} Digest — {datetime.now(timezone.utc).strftime('%b %d')}"
    return await send_email_detailed(to, subject, html)


def _is_due(cfg: dict, now: datetime) -> bool:
    if not cfg.get("enabled"):
        return False
    if now.hour != int(cfg.get("hour", 9)):
        return False
    freq = cfg.get("frequency", "weekly")
    if freq == "weekly" and now.weekday() != int(cfg.get("day_of_week", 0)):
        return False
    if freq == "monthly" and now.day != int(cfg.get("day_of_month", 1)):
        return False
    # once-per-day guard
    if (cfg.get("last_sent") or "")[:10] == now.date().isoformat():
        return False
    return True


async def scan_digest():
    cfg = await get_digest_config()
    now = datetime.now(timezone.utc)
    if not _is_due(cfg, now):
        return
    ok, detail = await send_digest_now(cfg.get("frequency"), cfg.get("recipient"))
    await save_digest_config({"last_sent": now_iso()})
    logger.info(f"digest sent ok={ok} detail={detail}")
