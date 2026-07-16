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
     "description": "Connect your Google account in one click — no keys needed.", "oauth": True,
     "methods": [
        {"id": "oauth", "label": "Connect with Google (one click)",
         "help": "Click Connect and sign in with your Google account. We only request read-only access to browse and download your files.",
         "fields": []}]},
    {"type": "llm", "name": "AI LLM", "category": "AI", "actions": ["test"],
     "description": "Connect an external LLM provider API key for AI features.",
     "methods": [
        {"id": "api_key", "label": "API key",
         "help": "Get an API key from your provider's dashboard (e.g. platform.openai.com → API keys).",
         "fields": [{"key": "provider", "label": "Provider", "type": "text", "placeholder": "OpenAI / Anthropic / Gemini"},
                    {"key": "api_key", "label": "API key", "type": "password"},
                    {"key": "model", "label": "Default model", "type": "text", "placeholder": "gpt-4o"}]}]},
    {"type": "mcp", "name": "MCP Server", "category": "AI", "actions": ["mcp", "test"],
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
    await db.integration_runs.delete_many({"integration_id": integration_id})
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
        await _record_run(integration_id, user["user_id"], "run", False, f"Failed to reach N8N: {e}",
                          request=data.payload or {})
        raise HTTPException(status_code=502, detail=f"Failed to reach N8N: {e}")
    ok = r.status_code < 400
    await _record_run(integration_id, user["user_id"], "run", ok, r.text[:2000],
                      status_code=r.status_code, request=data.payload or {})
    await log_activity(user["user_id"], "integration_run", {"type": "n8n", "id": integration_id})
    return {"ok": ok, "status_code": r.status_code, "response": r.text[:2000]}


# ---------------- Run history ----------------
async def _record_run(integration_id, owner_id, kind, ok, detail, status_code=None, request=None):
    await db.integration_runs.insert_one({
        "run_id": f"run_{uuid.uuid4().hex[:12]}", "integration_id": integration_id,
        "owner_id": owner_id, "kind": kind, "ok": bool(ok),
        "status_code": status_code, "request": request,
        "detail": (detail or "")[:2000], "created_at": now_iso()})
    # keep only the latest 50 per integration
    old = await db.integration_runs.find({"integration_id": integration_id}, {"_id": 1, "created_at": 1}).sort("created_at", -1).to_list(1000)
    for doc in old[50:]:
        await db.integration_runs.delete_one({"_id": doc["_id"]})


@router.get("/integrations/{integration_id}/runs")
async def integration_runs(integration_id: str, user: dict = Depends(get_current_user)):
    await _get_owned_integration(integration_id, user)
    items = await db.integration_runs.find({"integration_id": integration_id}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return items


# ---------------- MCP (Model Context Protocol) ----------------
def _parse_jsonrpc(resp):
    ct = resp.headers.get("content-type", "")
    if "text/event-stream" in ct:
        for line in resp.text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                try:
                    return json.loads(line[5:].strip())
                except Exception:
                    continue
        return {}
    try:
        return resp.json()
    except Exception:
        return {}


async def _mcp_connect(cfg):
    import httpx
    url = cfg.get("server_url")
    if not url:
        raise HTTPException(status_code=400, detail="No MCP server URL configured.")
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if cfg.get("token"):
        headers["Authorization"] = f"Bearer {cfg['token']}"
    client = httpx.AsyncClient(timeout=20.0)
    init_body = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                 "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                            "clientInfo": {"name": "Stitches", "version": "1.0"}}}
    resp = await client.post(url, json=init_body, headers=headers)
    sid = resp.headers.get("mcp-session-id") or resp.headers.get("Mcp-Session-Id")
    if sid:
        headers["Mcp-Session-Id"] = sid
    try:
        await client.post(url, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=headers)
    except Exception:
        pass
    return client, url, headers


async def _mcp_rpc(cfg, method, params, rid=2):
    client, url, headers = await _mcp_connect(cfg)
    try:
        resp = await client.post(url, json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}, headers=headers)
        data = _parse_jsonrpc(resp)
    finally:
        await client.aclose()
    if data.get("error"):
        raise HTTPException(status_code=400, detail=data["error"].get("message", "MCP error"))
    return data.get("result", {})


@router.get("/integrations/{integration_id}/mcp/tools")
async def mcp_list_tools(integration_id: str, user: dict = Depends(get_current_user)):
    await ensure_feature("integrations")
    it = await _get_owned_integration(integration_id, user)
    if it.get("type") != "mcp":
        raise HTTPException(status_code=400, detail="Not an MCP integration")
    try:
        result = await _mcp_rpc(it.get("config", {}), "tools/list", {})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not reach MCP server: {str(e)[:200]}")
    tools = result.get("tools", []) if isinstance(result, dict) else []
    return {"tools": [{"name": t.get("name"), "description": t.get("description", ""),
                       "input_schema": t.get("inputSchema") or t.get("input_schema") or {}} for t in tools]}


@router.post("/integrations/{integration_id}/mcp/call")
async def mcp_call_tool(integration_id: str, data: McpToolCallInput, user: dict = Depends(get_current_user)):
    await ensure_feature("integrations")
    it = await _get_owned_integration(integration_id, user)
    if it.get("type") != "mcp":
        raise HTTPException(status_code=400, detail="Not an MCP integration")
    try:
        result = await _mcp_rpc(it.get("config", {}), "tools/call", {"name": data.name, "arguments": data.arguments or {}})
        ok = not (isinstance(result, dict) and result.get("isError"))
        parts = []
        for c in (result.get("content", []) if isinstance(result, dict) else []):
            if c.get("type") == "text":
                parts.append(c.get("text", ""))
            else:
                parts.append(json.dumps(c))
        detail = "\n".join(parts) if parts else json.dumps(result)[:2000]
    except HTTPException as e:
        await _record_run(integration_id, user["user_id"], "mcp_call", False, e.detail, request={"tool": data.name, "arguments": data.arguments})
        raise
    except Exception as e:
        await _record_run(integration_id, user["user_id"], "mcp_call", False, str(e)[:2000], request={"tool": data.name, "arguments": data.arguments})
        raise HTTPException(status_code=502, detail=f"MCP call failed: {str(e)[:200]}")
    await _record_run(integration_id, user["user_id"], "mcp_call", ok, detail, request={"tool": data.name, "arguments": data.arguments})
    await log_activity(user["user_id"], "integration_run", {"type": "mcp", "id": integration_id, "tool": data.name})
    return {"ok": ok, "result": detail}


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
            token = await _google_access_token(integration_id, cfg)
            async with httpx.AsyncClient() as client:
                r = await client.get("https://www.googleapis.com/drive/v3/files",
                                     params={"pageSize": 100, "fields": "files(id,name,size)"},
                                     headers={"Authorization": f"Bearer {token}"}, timeout=20.0)
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
            token = await _google_access_token(integration_id, cfg)
            async with httpx.AsyncClient() as client:
                r = await client.get("https://www.googleapis.com/drive/v3/about", params={"fields": "user"},
                                     headers={"Authorization": f"Bearer {token}"}, timeout=10.0)
            return {"ok": r.status_code == 200, "message": "Google Drive connected." if r.status_code == 200 else "Token invalid or expired."}
    except Exception as e:
        return {"ok": False, "message": str(e)[:300]}
    return {"ok": False, "message": "Unknown integration type"}


def _google_client_config(oc):
    return {"web": {"client_id": oc["client_id"], "client_secret": oc["client_secret"],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [oc["redirect_uri"]]}}


async def _google_access_token(integration_id, cfg):
    from fastapi.concurrency import run_in_threadpool
    from datetime import datetime as _dt

    def _refresh():
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GReq
        scopes = cfg.get("scopes")
        if isinstance(scopes, str):
            scopes = scopes.split()
        creds = Credentials(token=cfg.get("access_token") or None,
                            refresh_token=cfg.get("refresh_token") or None,
                            token_uri=cfg.get("token_uri") or "https://oauth2.googleapis.com/token",
                            client_id=cfg.get("client_id"), client_secret=cfg.get("client_secret"),
                            scopes=scopes)
        exp = cfg.get("expiry")
        if exp:
            try:
                creds.expiry = _dt.fromisoformat(exp).replace(tzinfo=None)
            except Exception:
                creds.expiry = None
        refreshed = False
        if creds.refresh_token and (not creds.token or creds.expiry is None or creds.expired):
            creds.refresh(GReq())
            refreshed = True
        return creds.token, (creds.expiry.isoformat() if creds.expiry else ""), refreshed

    token, expiry, refreshed = await run_in_threadpool(_refresh)
    if refreshed:
        newcfg = dict(cfg); newcfg["access_token"] = token; newcfg["expiry"] = expiry
        await db.integrations.update_one({"integration_id": integration_id}, {"$set": {"config": encrypt_config(newcfg)}})
    return token


@router.get("/integrations/google/authorize")
async def google_authorize(user: dict = Depends(get_current_user)):
    from google_auth_oauthlib.flow import Flow
    oc = await get_google_oauth_cfg()
    if not oc["client_id"]:
        raise HTTPException(status_code=400, detail="Google Drive isn't configured yet. Ask an admin to add the Google credentials.")
    flow = Flow.from_client_config(_google_client_config(oc),
                                   scopes=["https://www.googleapis.com/auth/drive.readonly"],
                                   redirect_uri=oc["redirect_uri"])
    state = create_access_token(user["user_id"], user.get("email", ""))
    url, _ = flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent", state=state)
    return {"authorization_url": url}


@router.get("/integrations/google/callback")
async def google_callback(code: str = Query(None), state: str = Query(None), error: str = Query(None)):
    from fastapi.responses import RedirectResponse
    from fastapi.concurrency import run_in_threadpool
    from google_auth_oauthlib.flow import Flow
    frontend = os.environ.get("FRONTEND_URL", "").rstrip("/")
    if error or not code or not state:
        return RedirectResponse(f"{frontend}/integrations?google=error")
    user = await resolve_user_from_token(state)
    if not user:
        return RedirectResponse(f"{frontend}/integrations?google=error")
    oc = await get_google_oauth_cfg()
    flow = Flow.from_client_config(_google_client_config(oc), scopes=None, redirect_uri=oc["redirect_uri"])
    try:
        await run_in_threadpool(lambda: flow.fetch_token(code=code))
        creds = flow.credentials
    except Exception:
        return RedirectResponse(f"{frontend}/integrations?google=error")
    cfg = {"access_token": creds.token, "refresh_token": creds.refresh_token or "",
           "token_uri": creds.token_uri, "client_id": creds.client_id, "client_secret": creds.client_secret,
           "scopes": list(creds.scopes or []), "expiry": creds.expiry.isoformat() if creds.expiry else ""}
    doc = {"integration_id": f"int_{uuid.uuid4().hex[:12]}", "type": "google_drive",
           "name": "Google Drive", "config": encrypt_config(cfg), "owner_id": user["user_id"],
           "auth_method": "oauth", "status": "connected", "created_at": now_iso()}
    await db.integrations.insert_one(doc)
    await log_activity(user["user_id"], "integration_connect", {"type": "google_drive"})
    return RedirectResponse(f"{frontend}/integrations?google=connected")


@router.get("/admin/integrations")
async def admin_list_integrations(user: dict = Depends(require_admin)):
    items = await db.integrations.find({}, {"_id": 0, "config": 0}).to_list(500)
    owners = {u["user_id"]: u.get("name") for u in await db.users.find({}, {"_id": 0, "user_id": 1, "name": 1}).to_list(1000)}
    for it in items:
        it["owner_name"] = owners.get(it.get("owner_id"), "Unknown")
    return items


@router.get("/admin/google-oauth")
async def get_google_oauth_admin(user: dict = Depends(require_admin)):
    oc = await get_google_oauth_cfg()
    return {"client_id": oc["client_id"], "client_secret": ("••••••" if oc["client_secret"] else ""),
            "redirect_uri": oc["redirect_uri"]}


@router.put("/admin/google-oauth")
async def set_google_oauth_admin(data: GoogleOAuthInput, user: dict = Depends(require_admin)):
    update = {}
    if data.client_id is not None:
        update["client_id"] = data.client_id
    if data.client_secret is not None and data.client_secret and "••" not in data.client_secret:
        update["client_secret"] = data.client_secret
    existing = await db.settings.find_one({"key": "google_oauth"})
    val = (existing or {}).get("value", {})
    val.update(update)
    await db.settings.update_one({"key": "google_oauth"}, {"$set": {"key": "google_oauth", "value": val}}, upsert=True)
    return {"ok": True}


