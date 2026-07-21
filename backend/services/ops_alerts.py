from core import db, _fernet
import httpx


async def get_ops_webhook() -> dict:
    doc = await db.settings.find_one({"key": "ops_webhook"})
    v = (doc or {}).get("value", {}) if doc else {}
    url = ""
    if v.get("url_enc"):
        try:
            url = _fernet.decrypt(v["url_enc"].encode()).decode()
        except Exception:
            url = ""
    return {"enabled": v.get("enabled", False), "platform": v.get("platform", "auto"), "url": url}


def public_ops_webhook(cfg: dict) -> dict:
    return {"enabled": cfg["enabled"], "platform": cfg["platform"], "has_url": bool(cfg["url"])}


async def save_ops_webhook(patch: dict):
    sets = {}
    if "url" in patch:
        sets["value.url_enc"] = _fernet.encrypt(patch["url"].encode()).decode() if patch["url"] else ""
    if "enabled" in patch:
        sets["value.enabled"] = bool(patch["enabled"])
    if "platform" in patch:
        sets["value.platform"] = patch["platform"]
    if sets:
        await db.settings.update_one({"key": "ops_webhook"}, {"$set": sets}, upsert=True)


def _detect(url: str, platform: str) -> str:
    if platform and platform != "auto":
        return platform
    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return "discord"
    return "slack"


async def send_ops_alert(title: str, message: str, level: str = "info", url: str = None, platform: str = None):
    cfg = await get_ops_webhook()
    target = url if url is not None else cfg["url"]
    if not target:
        return False, "No webhook URL configured"
    if url is None and not cfg["enabled"]:
        return False, "Ops alerts are disabled"
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
