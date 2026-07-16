import os
from core import db, _fernet


async def get_livekit_cfg():
    doc = await db.settings.find_one({"key": "livekit"})
    val = (doc or {}).get("value", {})
    secret = ""
    if val.get("api_secret_enc"):
        try:
            secret = _fernet.decrypt(val["api_secret_enc"].encode()).decode()
        except Exception:
            secret = ""
    return {
        "enabled": bool(val.get("enabled")) if val else (os.environ.get("LIVEKIT_ENABLED", "false").lower() == "true"),
        "url": val.get("url") or os.environ.get("LIVEKIT_URL", ""),
        "api_key": val.get("api_key") or os.environ.get("LIVEKIT_API_KEY", ""),
        "api_secret": secret or os.environ.get("LIVEKIT_API_SECRET", ""),
    }
