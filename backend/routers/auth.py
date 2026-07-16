from fastapi import APIRouter, Query
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from services.email_verify import create_and_send_verification, verify_token
from models import *

router = APIRouter()


# ---------------- Auth Routes ----------------
@router.post("/auth/register")
async def register(data: RegisterInput, response: Response, request: Request):
    email = data.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    doc = {
        "user_id": user_id, "email": email, "name": data.name,
        "password_hash": hash_password(data.password), "role": "user",
        "username": email.split("@")[0], "avatar": None, "phone": "", "address": "",
        "company": "", "company_role": "", "bio": "", "project_info": "",
        "theme": "dark", "ui_scale": 1.0, "auth_provider": "password",
        "is_active": True, "email_verified": False, "friends": [],
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    try:
        await create_and_send_verification(user_id, email, data.name)
    except Exception as e:
        logger.warning(f"verification email failed: {e}")
    jti = uuid.uuid4().hex
    token = create_access_token(user_id, email, jti=jti)
    await record_session(user_id, jti, request)
    set_auth_cookie(response, "access_token", token, 604800)
    await log_activity(user_id, "register")
    return {"user": public_user(doc), "token": token}


@router.get("/auth/verify-email")
async def verify_email_get(token: str = Query(None)):
    ok, message = await verify_token(token)
    return {"ok": ok, "message": message}


@router.post("/auth/verify-email")
async def verify_email_post(request: Request):
    body = await request.json()
    ok, message = await verify_token((body or {}).get("token"))
    return {"ok": ok, "message": message}


@router.post("/auth/resend-verification")
async def resend_verification(user: dict = Depends(get_current_user)):
    if user.get("email_verified"):
        return {"ok": True, "message": "Your email is already verified."}
    ok, detail, _ = await create_and_send_verification(user["user_id"], user["email"], user.get("name", ""))
    return {"ok": ok, "message": "Verification email sent." if ok else f"Could not send: {detail}"}


@router.post("/auth/login")
async def login(data: LoginInput, response: Response, request: Request):
    email = data.email.lower()
    ip = request.client.host if request.client else "unknown"
    identifier = f"{ip}:{email}"
    attempt = await db.login_attempts.find_one({"identifier": identifier})
    if attempt and attempt.get("count", 0) >= 5:
        locked_until = attempt.get("locked_until")
        if isinstance(locked_until, str):
            locked_until = datetime.fromisoformat(locked_until)
        if locked_until and locked_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            raise HTTPException(status_code=429, detail="Too many attempts. Try again later.")
    user = await db.users.find_one({"email": email})
    if not user or not user.get("password_hash") or not verify_password(data.password, user["password_hash"]):
        await db.login_attempts.update_one(
            {"identifier": identifier},
            {"$inc": {"count": 1}, "$set": {"locked_until": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()}},
            upsert=True)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if user.get("is_active") is False:
        raise HTTPException(status_code=403, detail="Your account has been disabled by an administrator")
    await db.login_attempts.delete_one({"identifier": identifier})
    jti = uuid.uuid4().hex
    token = create_access_token(user["user_id"], email, jti=jti)
    await record_session(user["user_id"], jti, request)
    set_auth_cookie(response, "access_token", token, 604800)
    await log_activity(user["user_id"], "login")
    return {"user": public_user(user), "token": token}


@router.post("/auth/google/session")
async def google_session(request: Request, response: Response):
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")
    resp = requests.get(os.environ.get("AUTH_SESSION_URL", "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"),
                        headers={"X-Session-ID": session_id}, timeout=30)
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid session")
    d = resp.json()
    email = d["email"].lower()
    user = await db.users.find_one({"email": email})
    if not user:
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        user = {
            "user_id": user_id, "email": email, "name": d.get("name", email),
            "role": "user", "username": email.split("@")[0], "avatar": d.get("picture"),
            "phone": "", "address": "", "company": "", "company_role": "", "bio": "",
            "project_info": "", "theme": "dark", "ui_scale": 1.0, "auth_provider": "google",
            "is_active": True, "email_verified": True, "friends": [],
            "created_at": now_iso(),
        }
        await db.users.insert_one(user)
    session_token = d.get("session_token") or secrets.token_urlsafe(32)
    await db.user_sessions.insert_one({
        "user_id": user["user_id"], "session_token": session_token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": now_iso(),
    })
    set_auth_cookie(response, "session_token", session_token, 604800)
    return {"user": public_user(user), "token": session_token}


@router.get("/auth/me")
async def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("session_token", path="/")
    return {"ok": True}


# ---------------- QR cross-device login ----------------
@router.post("/auth/qr/generate")
async def qr_generate(user: dict = Depends(get_current_user)):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=3)
    await db.qr_tokens.insert_one({
        "token": token, "user_id": user["user_id"], "email": user["email"],
        "claimed": False, "expires_at": expires_at, "created_at": now_iso(),
    })
    return {"token": token, "expires_in_seconds": 180}


@router.post("/auth/qr/claim")
async def qr_claim(request: Request, response: Response):
    body = await request.json()
    token = (body or {}).get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Missing token")
    now = datetime.now(timezone.utc)
    doc = await db.qr_tokens.find_one_and_update(
        {"token": token, "claimed": False, "expires_at": {"$gt": now}},
        {"$set": {"claimed": True, "claimed_at": now_iso()}},
    )
    if not doc:
        raise HTTPException(status_code=401, detail="This login code is invalid, expired or already used.")
    dbuser = await db.users.find_one({"user_id": doc["user_id"]})
    if not dbuser or dbuser.get("is_active") is False:
        raise HTTPException(status_code=403, detail="Account unavailable")
    jti = uuid.uuid4().hex
    access = create_access_token(dbuser["user_id"], dbuser["email"], jti=jti)
    await record_session(dbuser["user_id"], jti, request)
    set_auth_cookie(response, "access_token", access, 604800)
    await log_activity(dbuser["user_id"], "qr_login")
    return {"user": public_user(dbuser), "token": access}


# ---------------- Connected devices / sessions ----------------
@router.get("/auth/sessions")
async def list_sessions(request: Request, user: dict = Depends(get_current_user)):
    cur = jti_from_request(request)
    items = await db.sessions.find({"user_id": user["user_id"], "revoked": {"$ne": True}},
                                   {"_id": 0}).sort("last_seen", -1).to_list(100)
    for s in items:
        s["current"] = (s.get("jti") == cur)
    return items


@router.delete("/auth/sessions/{session_id}")
async def revoke_session(session_id: str, user: dict = Depends(get_current_user)):
    await db.sessions.update_one({"session_id": session_id, "user_id": user["user_id"]},
                                 {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc)}})
    return {"ok": True}


@router.post("/auth/sessions/revoke-others")
async def revoke_other_sessions(request: Request, response: Response, user: dict = Depends(get_current_user)):
    import time
    now_epoch = int(time.time())
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"sessions_valid_after": now_epoch}})
    await db.sessions.update_many({"user_id": user["user_id"]},
                                  {"$set": {"revoked": True, "revoked_at": datetime.now(timezone.utc)}})
    jti = uuid.uuid4().hex
    token = create_access_token(user["user_id"], user["email"], jti=jti)
    await record_session(user["user_id"], jti, request)
    set_auth_cookie(response, "access_token", token, 604800)
    await log_activity(user["user_id"], "revoke_other_sessions")
    return {"ok": True, "token": token}


