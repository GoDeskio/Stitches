from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from models import *

router = APIRouter()


# ---------------- Auth Routes ----------------
@router.post("/auth/register")
async def register(data: RegisterInput, response: Response):
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
        "is_active": True, "friends": [],
        "created_at": now_iso(),
    }
    await db.users.insert_one(doc)
    token = create_access_token(user_id, email)
    set_auth_cookie(response, "access_token", token, 604800)
    await log_activity(user_id, "register")
    return {"user": public_user(doc), "token": token}


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
    token = create_access_token(user["user_id"], email)
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
            "is_active": True, "friends": [],
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


