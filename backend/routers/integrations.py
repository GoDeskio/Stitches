from fastapi import APIRouter
from core import *
from core import _create_message, _notify_mentions, ws_manager, _fernet
from models import *

router = APIRouter()


# ---------------- Integrations ----------------
INTEGRATION_CATALOG = [
    {"type": "n8n", "name": "N8N", "category": "Automation", "actions": ["run", "test"],
     "description": "Trigger your N8N automation workflows directly from Stitches.",
     "methods": [
        {"id": "url", "label": "Paste a link (easiest)",
         "help": "Open your workflow in N8N, click the Webhook step and copy its URL. No coding needed.",
         "fields": [{"key": "webhook_url", "label": "Workflow webhook link", "type": "url", "placeholder": "https://your-n8n.app/webhook/abc", "help": "In N8N: open the Webhook node → copy the 'Production URL'."}]},
        {"id": "basic", "label": "Link + username & password",
         "help": "Use this if your webhook is protected with a login.",
         "fields": [{"key": "webhook_url", "label": "Workflow webhook link", "type": "url"},
                    {"key": "basic_user", "label": "Username", "type": "text"},
                    {"key": "basic_pass", "label": "Password", "type": "password"}]}]},
    {"type": "email", "name": "Email (IMAP)", "category": "Communication", "actions": ["test"],
     "description": "Connect an email inbox with just your email address and password.",
     "methods": [
        {"id": "password", "label": "Email & password (easiest)",
         "help": "Just your normal email login. For Gmail or Outlook, create a free 'app password' in your account security settings.",
         "fields": [{"key": "imap_host", "label": "Mail server", "type": "text", "placeholder": "imap.gmail.com", "help": "Gmail: imap.gmail.com · Outlook: outlook.office365.com · Yahoo: imap.mail.yahoo.com"},
                    {"key": "email", "label": "Email address", "type": "text", "placeholder": "you@example.com"},
                    {"key": "password", "label": "Password", "type": "password", "help": "For Gmail/Outlook use an app password, not your main password."}]}]},
    {"type": "custom", "name": "Custom App", "category": "Other", "actions": ["test"],
     "description": "Connect almost any app with a username & password, or an API key if you have one.",
     "methods": [
        {"id": "basic", "label": "Username & password (easiest)",
         "help": "Works with any app that has a normal login.",
         "fields": [{"key": "base_url", "label": "App web address", "type": "url", "placeholder": "https://app.example.com"},
                    {"key": "username", "label": "Username or email", "type": "text"},
                    {"key": "password", "label": "Password", "type": "password"}]},
        {"id": "api_key", "label": "API key / token (advanced)",
         "help": "If the app gave you an API key, paste it here.",
         "fields": [{"key": "base_url", "label": "App web address", "type": "url"},
                    {"key": "api_key", "label": "API key", "type": "password"}]}]},
    {"type": "aws_s3", "name": "AWS S3", "category": "Storage", "actions": ["files", "test"],
     "description": "Browse and download files from an S3 (or S3-compatible) bucket.",
     "methods": [
        {"id": "keys", "label": "Access keys",
         "help": "In the AWS console go to IAM → Users → Security credentials → Create access key. Copy both values here.",
         "fields": [{"key": "access_key", "label": "Access Key ID", "type": "password", "help": "Starts with 'AKIA…'"},
                    {"key": "secret_key", "label": "Secret Access Key", "type": "password"},
                    {"key": "region", "label": "Region", "type": "text", "placeholder": "us-east-1"},
                    {"key": "bucket", "label": "Bucket name", "type": "text"}]}]},
    {"type": "dropbox", "name": "Dropbox", "category": "Storage", "actions": ["files", "test"],
     "description": "Browse and download files from your Dropbox.",
     "methods": [
        {"id": "token", "label": "Access token",
         "help": "Go to dropbox.com/developers/apps → your app → Settings → 'Generate access token' and paste it here.",
         "fields": [{"key": "access_token", "label": "Access token", "type": "password"}]}]},
    {"type": "google_drive", "name": "Google Drive", "category": "Storage", "actions": ["files", "test"],
     "description": "Browse and download files from Google Drive.",
     "methods": [
        {"id": "token", "label": "Access token",
         "help": "Paste an OAuth access token from Google's OAuth Playground (developers.google.com/oauthplayground) with Drive scope.",
         "fields": [{"key": "access_token", "label": "OAuth access token", "type": "password"}]}]},
    {"type": "llm", "name": "AI LLM", "category": "AI", "actions": ["test"],
     "description": "Connect an external LLM provider API key for AI features.",
     "methods": [
        {"id": "api_key", "label": "API key",
         "help": "Get an API key from your provider's dashboard (e.g. platform.openai.com → API keys).",
         "fields": [{"key": "provider", "label": "Provider", "type": "text", "placeholder": "OpenAI / Anthropic / Gemini"},
                    {"key": "api_key", "label": "API key", "type": "password"},
                    {"key": "model", "label": "Default model", "type": "text", "placeholder": "gpt-4o"}]}]},
    {"type": "mcp", "name": "MCP Server", "category": "AI", "actions": ["test"],
     "description": "Connect a Model Context Protocol server to extend AI tools.",
     "methods": [
        {"id": "token", "label": "Server URL + token",
         "help": "Enter your MCP server address and its auth token if it has one.",
         "fields": [{"key": "server_url", "label": "MCP server URL", "type": "url"},
                    {"key": "token", "label": "Auth token (optional)", "type": "password"}]}]},
]


@router.get("/integrations/catalog")
async def integrations_catalog(user: dict = Depends(get_current_user)):
    return INTEGRATION_CATALOG


@router.get("/integrations")
async def list_integrations(user: dict = Depends(get_current_user)):
    items = await db.integrations.find({"owner_id": user["user_id"]}, {"_id": 0}).to_list(200)
    actions_by_type = {c["type"]: c.get("actions", []) for c in INTEGRATION_CATALOG}
    for it in items:
        cfg = decrypt_config(it.get("config", {}))
        it["config_masked"] = {k: ("••••••" if k in SECRET_FIELDS and v else v) for k, v in cfg.items()}
        it["actions"] = actions_by_type.get(it.get("type"), [])
        it.pop("config", None)
    return items


@router.post("/integrations")
async def create_integration(data: IntegrationInput, user: dict = Depends(get_current_user)):
    await ensure_feature("integrations")
    doc = {"integration_id": f"int_{uuid.uuid4().hex[:12]}", "type": data.type,
           "name": data.name, "config": encrypt_config(data.config), "owner_id": user["user_id"],
           "auth_method": data.auth_method, "status": "connected", "created_at": now_iso()}
    await db.integrations.insert_one(doc)
    await log_activity(user["user_id"], "integration_connect", {"type": data.type})
    doc.pop("_id", None)
    doc.pop("config", None)
    return doc


@router.delete("/integrations/{integration_id}")
async def delete_integration(integration_id: str, user: dict = Depends(get_current_user)):
    await db.integrations.delete_one({"integration_id": integration_id, "owner_id": user["user_id"]})
    return {"ok": True}


async def _get_owned_integration(integration_id: str, user: dict) -> dict:
    q = {"integration_id": integration_id}
    if user.get("role") != "admin":
        q["owner_id"] = user["user_id"]
    it = await db.integrations.find_one(q)
    if not it:
        raise HTTPException(status_code=404, detail="Integration not found")
    it["config"] = decrypt_config(it.get("config", {}))
    return it


def _s3_client(cfg: dict):
    import boto3
    from botocore.config import Config
    return boto3.client("s3", aws_access_key_id=cfg.get("access_key"),
                        aws_secret_access_key=cfg.get("secret_key"),
                        region_name=cfg.get("region") or "us-east-1",
                        config=Config(signature_version="s3v4"))


@router.post("/integrations/{integration_id}/run")
async def run_integration(integration_id: str, data: IntegrationRunInput, user: dict = Depends(get_current_user)):
    await ensure_feature("integrations")
    it = await _get_owned_integration(integration_id, user)
    if it.get("type") != "n8n":
        raise HTTPException(status_code=400, detail="Run is only supported for N8N integrations")
    cfg = it.get("config", {})
    url = cfg.get("webhook_url")
    if not url:
        raise HTTPException(status_code=400, detail="No webhook URL configured for this integration")
    headers = {}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    auth = None
    if cfg.get("basic_user") or cfg.get("basic_pass"):
        auth = (cfg.get("basic_user", ""), cfg.get("basic_pass", ""))
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            r = await client.post(url, json=data.payload or {}, headers=headers, auth=auth, timeout=30.0)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to reach N8N: {e}")
    await log_activity(user["user_id"], "integration_run", {"type": "n8n", "id": integration_id})
    return {"ok": r.status_code < 400, "status_code": r.status_code, "response": r.text[:2000]}


@router.get("/integrations/{integration_id}/files")
async def integration_files(integration_id: str, path: str = "", user: dict = Depends(get_current_user)):
    await ensure_feature("integrations")
    it = await _get_owned_integration(integration_id, user)
    cfg = it.get("config", {})
    t = it.get("type")
    from fastapi.concurrency import run_in_threadpool
    if t == "aws_s3":
        def _list():
            s3 = _s3_client(cfg)
            resp = s3.list_objects_v2(Bucket=cfg.get("bucket"), Prefix=path or "")
            return [{"name": o["Key"], "size": o.get("Size", 0), "key": o["Key"]} for o in resp.get("Contents", [])][:200]
        try:
            files = await run_in_threadpool(_list)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"S3 error: {e}")
    elif t == "dropbox":
        def _list():
            import dropbox
            dbx = dropbox.Dropbox(cfg.get("access_token"))
            res = dbx.files_list_folder(path or "")
            return [{"name": e.name, "size": getattr(e, "size", 0), "key": e.path_lower} for e in res.entries][:200]
        try:
            files = await run_in_threadpool(_list)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Dropbox error: {e}")
    elif t == "google_drive":
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get("https://www.googleapis.com/drive/v3/files",
                                     params={"pageSize": 100, "fields": "files(id,name,size)"},
                                     headers={"Authorization": f"Bearer {cfg.get('access_token')}"}, timeout=20.0)
            r.raise_for_status()
            files = [{"name": f["name"], "size": int(f.get("size", 0) or 0), "key": f["id"]} for f in r.json().get("files", [])]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Google Drive error: {e}")
    else:
        raise HTTPException(status_code=400, detail="This integration does not support file browsing")
    return {"files": files}


@router.post("/integrations/{integration_id}/download")
async def integration_download(integration_id: str, data: FileKeyInput, user: dict = Depends(get_current_user)):
    await ensure_feature("integrations")
    it = await _get_owned_integration(integration_id, user)
    cfg = it.get("config", {})
    t = it.get("type")
    from fastapi.concurrency import run_in_threadpool
    if t == "aws_s3":
        def _link():
            s3 = _s3_client(cfg)
            return s3.generate_presigned_url("get_object", Params={"Bucket": cfg.get("bucket"), "Key": data.key}, ExpiresIn=3600)
        try:
            url = await run_in_threadpool(_link)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"S3 error: {e}")
    elif t == "dropbox":
        def _link():
            import dropbox
            return dropbox.Dropbox(cfg.get("access_token")).files_get_temporary_link(data.key).link
        try:
            url = await run_in_threadpool(_link)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Dropbox error: {e}")
    elif t == "google_drive":
        url = f"https://drive.google.com/uc?id={data.key}&export=download"
    else:
        raise HTTPException(status_code=400, detail="Download not supported for this integration")
    return {"url": url}


@router.post("/integrations/{integration_id}/test")
async def test_integration(integration_id: str, user: dict = Depends(get_current_user)):
    it = await _get_owned_integration(integration_id, user)
    cfg = it.get("config", {})
    t = it.get("type")
    import httpx
    from fastapi.concurrency import run_in_threadpool
    try:
        if t == "n8n":
            ok = bool(cfg.get("webhook_url"))
            return {"ok": ok, "message": "Webhook URL saved — use Run to trigger the workflow." if ok else "No webhook URL configured."}
        if t == "llm":
            return {"ok": bool(cfg.get("api_key")), "message": "API key stored securely." if cfg.get("api_key") else "No API key."}
        if t == "email":
            def _t():
                import imaplib
                m = imaplib.IMAP4_SSL(cfg.get("imap_host"), timeout=10)
                m.login(cfg.get("email"), cfg.get("password"))
                m.logout()
                return True
            await run_in_threadpool(_t)
            return {"ok": True, "message": f"Connected to {cfg.get('email')}."}
        if t == "custom":
            base = cfg.get("base_url")
            if not base:
                return {"ok": False, "message": "No app URL configured."}
            if not (cfg.get("username") or cfg.get("password") or cfg.get("api_key")):
                return {"ok": False, "message": "Enter a username & password or an API key to connect."}
            auth = (cfg.get("username", ""), cfg.get("password", "")) if cfg.get("username") or cfg.get("password") else None
            headers = {"Authorization": f"Bearer {cfg['api_key']}"} if cfg.get("api_key") else {}
            async with httpx.AsyncClient() as client:
                r = await client.get(base, auth=auth, headers=headers, timeout=10.0)
            return {"ok": r.status_code < 400, "message": f"App responded with {r.status_code}."}
        if t == "mcp":
            async with httpx.AsyncClient() as client:
                r = await client.get(cfg.get("server_url"), timeout=10.0,
                                     headers={"Authorization": f"Bearer {cfg.get('token')}"} if cfg.get("token") else {})
            return {"ok": r.status_code < 500, "message": f"Server responded with {r.status_code}."}
        if t == "aws_s3":
            def _t():
                _s3_client(cfg).head_bucket(Bucket=cfg.get("bucket"))
                return True
            await run_in_threadpool(_t)
            return {"ok": True, "message": "Bucket reachable."}
        if t == "dropbox":
            def _t():
                import dropbox
                dropbox.Dropbox(cfg.get("access_token")).users_get_current_account()
                return True
            await run_in_threadpool(_t)
            return {"ok": True, "message": "Dropbox account connected."}
        if t == "google_drive":
            async with httpx.AsyncClient() as client:
                r = await client.get("https://www.googleapis.com/drive/v3/about", params={"fields": "user"},
                                     headers={"Authorization": f"Bearer {cfg.get('access_token')}"}, timeout=10.0)
            return {"ok": r.status_code == 200, "message": "Google Drive connected." if r.status_code == 200 else "Token invalid or expired."}
    except Exception as e:
        return {"ok": False, "message": str(e)[:300]}
    return {"ok": False, "message": "Unknown integration type"}


@router.get("/admin/integrations")
async def admin_list_integrations(user: dict = Depends(require_admin)):
    items = await db.integrations.find({}, {"_id": 0, "config": 0}).to_list(500)
    owners = {u["user_id"]: u.get("name") for u in await db.users.find({}, {"_id": 0, "user_id": 1, "name": 1}).to_list(1000)}
    for it in items:
        it["owner_name"] = owners.get(it.get("owner_id"), "Unknown")
    return items


