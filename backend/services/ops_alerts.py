from core import db, _fernet
from datetime import datetime, timezone
import httpx

_RANK = {"info": 0, "success": 0, "warn": 1, "error": 2}


async def get_ops_webhook() -> dict:
    doc = await db.settings.find_one({"key": "ops_webhook"})
    v = (doc or {}).get("value", {}) if doc else {}
    url = ""
    if v.get("url_enc"):
        try:
            url = _fernet.decrypt(v["url_enc"].encode()).decode()
        except Exception:
            url = ""
    return {
        "enabled": v.get("enabled", False), "platform": v.get("platform", "auto"), "url": url,
        "min_level": v.get("min_level", "info"),
        "quiet_enabled": v.get("quiet_enabled", False),
        "quiet_start": int(v.get("quiet_start", 22)),
        "quiet_end": int(v.get("quiet_end", 7)),
        "tz_offset": int(v.get("tz_offset", 0)),
    }


def public_ops_webhook(cfg: dict) -> dict:
    return {
        "enabled": cfg["enabled"], "platform": cfg["platform"], "has_url": bool(cfg["url"]),
        "min_level": cfg["min_level"], "quiet_enabled": cfg["quiet_enabled"],
        "quiet_start": cfg["quiet_start"], "quiet_end": cfg["quiet_end"], "tz_offset": cfg["tz_offset"],
    }


async def save_ops_webhook(patch: dict):
    sets = {}
    if "url" in patch:
        sets["value.url_enc"] = _fernet.encrypt(patch["url"].encode()).decode() if patch["url"] else ""
    if "enabled" in patch:
        sets["value.enabled"] = bool(patch["enabled"])
    if "platform" in patch:
        sets["value.platform"] = patch["platform"]
    if "min_level" in patch and patch["min_level"] in _RANK:
        sets["value.min_level"] = patch["min_level"]
    if "quiet_enabled" in patch:
        sets["value.quiet_enabled"] = bool(patch["quiet_enabled"])
    for k in ("quiet_start", "quiet_end", "tz_offset"):
        if k in patch:
            try:
                sets[f"value.{k}"] = int(patch[k])
            except Exception:
                pass
    if sets:
        await db.settings.update_one({"key": "ops_webhook"}, {"$set": sets}, upsert=True)


def _detect(url: str, platform: str) -> str:
    if platform and platform != "auto":
        return platform
    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return "discord"
    return "slack"


def _passes_filters(level: str, cfg: dict) -> bool:
    if _RANK.get(level, 0) < _RANK.get(cfg.get("min_level", "info"), 0):
        return False
    if cfg.get("quiet_enabled") and level != "error":
        hour = (datetime.now(timezone.utc).hour + int(cfg.get("tz_offset", 0))) % 24
        s, e = int(cfg.get("quiet_start", 22)), int(cfg.get("quiet_end", 7))
        in_quiet = (s <= hour < e) if s < e else (hour >= s or hour < e)
        if in_quiet:
            return False
    return True


async def send_ops_alert(title: str, message: str, level: str = "info", url: str = None, platform: str = None):
    cfg = await get_ops_webhook()
    target = url if url is not None else cfg["url"]
    if not target:
        return False, "No webhook URL configured"
    if url is None:
        # Real event (not a manual test): honour enable + severity/quiet-hours filters.
        if not cfg["enabled"]:
            return False, "Ops alerts are disabled"
        if not _passes_filters(level, cfg):
            return False, "Filtered by severity/quiet-hours settings"
    plat = _detect(target, platform if platform is not None else cfg["platform"])
    icon = {"error": "🔴", "warn": "🟠", "success": "🟢", "info": "🔵"}.get(level, "🔵")
    try:
        async with httpx.AsyncClient(timeout=10.0) as h:
            if plat == "discord":
                r = await h.post(target, json={"content": f"{icon} **Stitches — {title}**\n{message}"})
            else:
                r = await h.post(target, json={"text": f"{icon} *Stitches — {title}*\n{message}"})
        return (r.status_code < 300), f"{plat} · HTTP {r.status_code}"
    except Exception as e:
        return False, f"Could not reach webhook: {type(e).__name__}"
