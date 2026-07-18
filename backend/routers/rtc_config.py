from fastapi import APIRouter
from core import *
from services.livekit import get_livekit_cfg
import socket
import asyncio
import httpx

router = APIRouter()


# ---------------- WebRTC / TURN configuration ----------------
async def _get_turn_cfg():
    doc = await db.settings.find_one({"key": "turn"})
    val = (doc or {}).get("value", {})
    return {
        "urls": val.get("urls") or os.environ.get("TURN_URLS", ""),
        "username": val.get("username") or os.environ.get("TURN_USERNAME", ""),
        "credential": val.get("credential") or os.environ.get("TURN_CREDENTIAL", ""),
    }


def _build_ice(turn):
    ice = [{"urls": "stun:stun.l.google.com:19302"}, {"urls": "stun:global.stun.twilio.com:3478"}]
    if turn.get("urls"):
        entry = {"urls": [u.strip() for u in turn["urls"].split(",") if u.strip()]}
        if turn.get("username"):
            entry["username"] = turn["username"]
        if turn.get("credential"):
            entry["credential"] = turn["credential"]
        ice.append(entry)
    return ice


@router.get("/rtc/config")
async def rtc_config(user: dict = Depends(get_current_user)):
    lk = await get_livekit_cfg()
    sfu_on = lk["enabled"] and bool(lk["url"] and lk["api_key"] and lk["api_secret"])
    return {"iceServers": _build_ice(await _get_turn_cfg()), "sfu": {"enabled": sfu_on, "url": lk["url"] if sfu_on else ""}}


@router.get("/admin/rtc-config")
async def admin_get_rtc(user: dict = Depends(require_admin)):
    t = await _get_turn_cfg()
    return {"urls": t.get("urls", ""), "username": t.get("username", ""), "has_credential": bool(t.get("credential"))}


@router.put("/admin/rtc-config")
async def admin_set_rtc(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    existing = await db.settings.find_one({"key": "turn"})
    prev = (existing or {}).get("value", {})
    cred = body.get("credential", "")
    urls = (body.get("urls") or "").strip()
    val = {"urls": urls,
           "username": (body.get("username") or "").strip(),
           "credential": ("" if not urls else (cred if cred else prev.get("credential", "")))}
    await db.settings.update_one({"key": "turn"}, {"$set": {"key": "turn", "value": val}}, upsert=True)
    return {"ok": True}


@router.delete("/admin/rtc-config")
async def admin_clear_rtc(user: dict = Depends(require_admin)):
    await db.settings.delete_one({"key": "turn"})
    return {"ok": True}


async def _test_livekit(lk):
    if not (lk.get("url") and lk.get("api_key") and lk.get("api_secret")):
        return {"ok": False, "detail": "SFU not fully configured — enter URL, API key and secret, then Save before testing."}
    url = lk["url"].strip().rstrip("/")
    http = url.replace("wss://", "https://").replace("ws://", "http://")
    try:
        async with httpx.AsyncClient(timeout=8.0) as h:
            r = await h.get(http + "/")
        # LiveKit answers a plain GET on / with 200 "OK".
        return {"ok": r.status_code < 500, "detail": f"Reached LiveKit at {http} (HTTP {r.status_code})."}
    except Exception as e:
        return {"ok": False, "detail": f"Could not reach {http}: {type(e).__name__}. Check the URL, TLS and that the server is running."}


def _test_turn_sync(turn):
    urls = (turn.get("urls") or "").strip()
    if not urls:
        return {"ok": False, "detail": "No TURN server configured — calls use public STUN only."}
    results = []
    for raw in [u.strip() for u in urls.split(",") if u.strip()]:
        base = raw.split("?")[0]
        parts = base.split(":")
        if len(parts) >= 3:
            host, port = parts[1], parts[2]
        elif len(parts) == 2:
            host, port = parts[1], "3478"
        else:
            results.append(f"{raw}: unparseable (use turn:host:port)")
            continue
        try:
            port_i = int(port)
        except Exception:
            port_i = 3478
        try:
            ip = socket.gethostbyname(host)
        except Exception:
            results.append(f"{raw}: DNS resolve FAILED for '{host}'")
            continue
        try:
            s = socket.create_connection((ip, port_i), timeout=5)
            s.close()
            results.append(f"{raw}: {host} → {ip}, TCP {port_i} open ✔")
        except Exception:
            results.append(f"{raw}: {host} → {ip} resolves, but TCP {port_i} unreachable (UDP-only TURN can't be probed from the server — verify UDP/firewall)")
    ok = any("✔" in r for r in results)
    return {"ok": ok, "detail": " | ".join(results)}


@router.post("/admin/rtc/test")
async def admin_test_rtc(user: dict = Depends(require_admin)):
    lk = await get_livekit_cfg()
    turn = await _get_turn_cfg()
    sfu_res = await _test_livekit(lk)
    turn_res = await asyncio.to_thread(_test_turn_sync, turn)
    return {"sfu": sfu_res, "turn": turn_res}
