import io
import re
import asyncio
import zipfile
import secrets as pysecrets
from email.utils import format_datetime
from xml.sax.saxutils import escape as _xesc
from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse
from core import *
from core import _fernet

router = APIRouter()

# ---------------- Deployment Center ----------------
# Generates ready-to-run deploy artifacts (compose, secrets, coturn/livekit config,
# clone + install scripts) for the self-hosted infrastructure a Stitches operator needs.
# The preview pod cannot run Docker itself, so this produces a downloadable bundle the
# operator runs on their own VM. Services already provided by Stitches are flagged.

CATALOG = [
    {"id": "coturn", "name": "coturn", "category": "Calls", "repo": "https://github.com/coturn/coturn.git", "branch": "master", "required": True, "provided": False,
     "description": "STUN/TURN relay so calls connect through strict NATs and firewalls."},
    {"id": "livekit", "name": "LiveKit", "category": "Calls", "repo": "https://github.com/livekit/livekit.git", "branch": "master", "required": True, "provided": False,
     "description": "WebRTC SFU for large group meetings and screen share."},
    {"id": "traefik", "name": "Traefik", "category": "Gateway", "repo": "https://github.com/traefik/traefik.git", "branch": "master", "required": True, "provided": False,
     "description": "TLS termination, routing and automatic Let's Encrypt certificates."},
    {"id": "prometheus", "name": "Prometheus", "category": "Monitoring", "repo": "https://github.com/prometheus/prometheus.git", "branch": "main", "required": False, "provided": False,
     "description": "Metrics collection and service health monitoring."},
    {"id": "grafana", "name": "Grafana", "category": "Monitoring", "repo": "https://github.com/grafana/grafana.git", "branch": "main", "required": False, "provided": False,
     "description": "Operational dashboards and alert visualization."},
    {"id": "loki", "name": "Loki", "category": "Logging", "repo": "https://github.com/grafana/loki.git", "branch": "main", "required": False, "provided": False,
     "description": "Centralized application and infrastructure logs."},
    {"id": "minio", "name": "MinIO", "category": "Object Storage", "repo": "https://github.com/minio/minio.git", "branch": "master", "required": False, "provided": True,
     "description": "S3-compatible storage. Stitches already ships object storage — self-host only if you want full control."},
    {"id": "valkey", "name": "Valkey", "category": "Cache", "repo": "https://github.com/valkey-io/valkey.git", "branch": "unstable", "required": False, "provided": False,
     "description": "Redis-compatible cache for sessions, presence and rate limits."},
    {"id": "nats", "name": "NATS", "category": "Event Bus", "repo": "https://github.com/nats-io/nats-server.git", "branch": "main", "required": False, "provided": False,
     "description": "Messaging backbone for service events and job fan-out."},
    {"id": "opensearch", "name": "OpenSearch", "category": "Search", "repo": "https://github.com/opensearch-project/OpenSearch.git", "branch": "main", "required": False, "provided": False,
     "description": "Full-text search across messages, files and audit events."},
    {"id": "clamav", "name": "ClamAV", "category": "Security", "repo": "https://github.com/Cisco-Talos/clamav.git", "branch": "main", "required": False, "provided": False,
     "description": "Malware scanning for uploaded files and attachments."},
    {"id": "keycloak", "name": "Keycloak", "category": "Identity", "repo": "https://github.com/keycloak/keycloak.git", "branch": "main", "required": False, "provided": True,
     "description": "OIDC/SAML identity. Stitches already has built-in auth — redundant unless you need enterprise SSO."},
    {"id": "postgres", "name": "PostgreSQL", "category": "Database", "repo": "https://github.com/postgres/postgres.git", "branch": "master", "required": False, "provided": True,
     "description": "Relational DB. Stitches runs on MongoDB — only needed by Synapse/Keycloak."},
    {"id": "synapse", "name": "Element Synapse", "category": "Messaging", "repo": "https://github.com/element-hq/synapse.git", "branch": "develop", "required": False, "provided": True,
     "description": "Matrix homeserver. Stitches already provides messaging — redundant unless you want Matrix federation."},
    {"id": "element-web", "name": "Element Web", "category": "Web Client", "repo": "https://github.com/element-hq/element-web.git", "branch": "develop", "required": False, "provided": True,
     "description": "Matrix web client. Stitches is your client — redundant."},
]
_CAT_BY_ID = {c["id"]: c for c in CATALOG}
_DEFAULT_SELECTED = [c["id"] for c in CATALOG if c["required"]] + ["prometheus", "grafana"]


async def _load_cfg():
    doc = await db.settings.find_one({"key": "deploy_center"})
    val = (doc or {}).get("value", {})
    return {
        "domain": val.get("domain", ""),
        "public_ip": val.get("public_ip", ""),
        "selected": val.get("selected", _DEFAULT_SELECTED),
        "github_token_enc": val.get("github_token_enc", ""),
        "secrets": val.get("secrets", {}),
        "presets": val.get("presets", []),
    }


def _gen_secrets():
    return {
        "turn_user": "stitches",
        "turn_secret": pysecrets.token_urlsafe(24),
        "livekit_api_key": "API" + pysecrets.token_hex(6),
        "livekit_api_secret": pysecrets.token_urlsafe(32),
        "postgres_password": pysecrets.token_urlsafe(18),
        "keycloak_admin_password": pysecrets.token_urlsafe(18),
        "minio_root_password": pysecrets.token_urlsafe(18),
        "grafana_admin_password": pysecrets.token_urlsafe(14),
    }


@router.get("/admin/deploy/catalog")
async def deploy_catalog(user: dict = Depends(require_admin)):
    cfg = await _load_cfg()
    return {
        "catalog": CATALOG,
        "domain": cfg["domain"],
        "public_ip": cfg["public_ip"],
        "selected": cfg["selected"],
        "presets": cfg["presets"],
        "has_github_token": bool(cfg["github_token_enc"]),
        "has_generated": bool(cfg["secrets"]),
        "secrets_preview": _paste_values(cfg) if cfg["secrets"] else None,
    }


@router.put("/admin/deploy/config")
async def deploy_config(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    cfg = await _load_cfg()
    tok = (body.get("github_token") or "").strip()
    token_enc = cfg["github_token_enc"]
    if tok:
        token_enc = _fernet.encrypt(tok.encode()).decode()
    elif body.get("clear_token"):
        token_enc = ""
    val = {
        "domain": (body.get("domain") or "").strip(),
        "public_ip": (body.get("public_ip") or "").strip(),
        "selected": [s for s in (body.get("selected") or []) if s in _CAT_BY_ID],
        "github_token_enc": token_enc,
        "secrets": cfg["secrets"],
        "presets": cfg["presets"],
    }
    await db.settings.update_one({"key": "deploy_center"}, {"$set": {"key": "deploy_center", "value": val}}, upsert=True)
    return {"ok": True}


@router.post("/admin/deploy/presets")
async def deploy_save_preset(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    cfg = await _load_cfg()
    ids = [s for s in (body.get("selected") or cfg["selected"]) if s in _CAT_BY_ID]
    if not ids:
        raise HTTPException(status_code=400, detail="select at least one service")
    presets = [p for p in cfg["presets"] if p.get("name") != name]
    preset = {"id": f"preset_{uuid.uuid4().hex[:8]}", "name": name[:40], "ids": ids}
    presets.append(preset)
    await db.settings.update_one({"key": "deploy_center"},
                                 {"$set": {"key": "deploy_center", "value": {**cfg, "presets": presets}}}, upsert=True)
    return preset


@router.delete("/admin/deploy/presets/{preset_id}")
async def deploy_delete_preset(preset_id: str, user: dict = Depends(require_admin)):
    cfg = await _load_cfg()
    presets = [p for p in cfg["presets"] if p.get("id") != preset_id]
    await db.settings.update_one({"key": "deploy_center"},
                                 {"$set": {"key": "deploy_center", "value": {**cfg, "presets": presets}}}, upsert=True)
    return {"ok": True}


@router.post("/admin/deploy/generate")
async def deploy_generate(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    cfg = await _load_cfg()
    if not cfg["secrets"] or body.get("regenerate"):
        cfg["secrets"] = _gen_secrets()
        await db.settings.update_one({"key": "deploy_center"},
                                     {"$set": {"key": "deploy_center", "value": {**cfg, "secrets": cfg["secrets"]}}}, upsert=True)
    files = _build_files(cfg)
    await log_activity(user["user_id"], "deploy_generate")
    return {"files": files, "paste": _paste_values(cfg)}


@router.get("/admin/deploy/download")
async def deploy_download(user: dict = Depends(require_admin)):
    cfg = await _load_cfg()
    if not cfg["secrets"]:
        cfg["secrets"] = _gen_secrets()
        await db.settings.update_one({"key": "deploy_center"},
                                     {"$set": {"key": "deploy_center", "value": {**cfg, "secrets": cfg["secrets"]}}}, upsert=True)
    files = _build_files(cfg)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.writestr(f"stitches-deploy/{f['name']}", f["content"])
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": "attachment; filename=stitches-deploy.zip"})


@router.post("/admin/deploy/apply-calls")
async def deploy_apply_calls(user: dict = Depends(require_admin)):
    """Wire the generated coturn + LiveKit credentials straight into the Meetings config."""
    cfg = await _load_cfg()
    if not cfg["secrets"]:
        return {"ok": False, "error": "Generate the bundle first."}
    domain = cfg["domain"] or cfg["public_ip"] or "your-host"
    s = cfg["secrets"]
    turn_val = {"urls": f"turn:{domain}:3478", "username": s["turn_user"], "credential": s["turn_secret"]}
    await db.settings.update_one({"key": "turn"}, {"$set": {"key": "turn", "value": turn_val}}, upsert=True)
    if "livekit" in cfg["selected"]:
        lk_val = {"enabled": True, "url": f"wss://livekit.{domain}",
                  "api_key": s["livekit_api_key"],
                  "api_secret_enc": _fernet.encrypt(s["livekit_api_secret"].encode()).decode()}
        await db.settings.update_one({"key": "livekit"}, {"$set": {"key": "livekit", "value": lk_val}}, upsert=True)
    await log_activity(user["user_id"], "deploy_apply_calls")
    return {"ok": True, "turn_urls": turn_val["urls"]}


def _paste_values(cfg):
    s = cfg["secrets"]
    domain = cfg["domain"] or cfg["public_ip"] or "your-host"
    return {
        "turn_urls": f"turn:{domain}:3478",
        "turn_username": s.get("turn_user", "stitches"),
        "turn_credential": s.get("turn_secret", ""),
        "livekit_url": f"wss://livekit.{domain}",
        "livekit_api_key": s.get("livekit_api_key", ""),
        "livekit_api_secret": s.get("livekit_api_secret", ""),
    }


def _build_files(cfg):
    sel = [s for s in cfg["selected"] if s in _CAT_BY_ID]
    domain = cfg["domain"] or "your-domain.com"
    public_ip = cfg["public_ip"] or "YOUR.PUBLIC.IP"
    s = cfg["secrets"]
    files = []

    # ---- clone-repos.sh (grab the source from GitHub) ----
    clone = ["#!/usr/bin/env bash", "set -euo pipefail",
             "# Clones the source of every selected service from GitHub.",
             'TOKEN="${GITHUB_TOKEN:-}"', 'mkdir -p repos && cd repos', ""]
    for sid in sel:
        c = _CAT_BY_ID[sid]
        clone.append(f'echo "== {c["name"]} =="')
        clone.append(f'REPO_URL="{c["repo"]}"')
        clone.append('if [ -n "$TOKEN" ]; then REPO_URL="${REPO_URL/https:\\/\\//https:\\/\\/$TOKEN@}"; fi')
        clone.append(f'if [ -d "{sid}/.git" ]; then git -C {sid} pull --ff-only; '
                     f'else git clone --depth 1 --branch {c["branch"]} "$REPO_URL" {sid}; fi')
        clone.append("")
    files.append({"name": "clone-repos.sh", "language": "bash", "content": "\n".join(clone) + "\n"})

    # ---- .env ----
    env_lines = [f"DOMAIN={domain}", f"PUBLIC_IP={public_ip}",
                 f"TURN_USER={s['turn_user']}", f"TURN_SECRET={s['turn_secret']}",
                 f"LIVEKIT_API_KEY={s['livekit_api_key']}", f"LIVEKIT_API_SECRET={s['livekit_api_secret']}",
                 f"POSTGRES_PASSWORD={s['postgres_password']}", f"KEYCLOAK_ADMIN_PASSWORD={s['keycloak_admin_password']}",
                 f"MINIO_ROOT_PASSWORD={s['minio_root_password']}", f"GRAFANA_ADMIN_PASSWORD={s['grafana_admin_password']}"]
    files.append({"name": ".env", "language": "dotenv", "content": "\n".join(env_lines) + "\n"})

    # ---- coturn config ----
    if "coturn" in sel:
        files.append({"name": "coturn/turnserver.conf", "language": "ini", "content":
            f"""listening-port=3478
tls-listening-port=5349
min-port=49160
max-port=49260
fingerprint
lt-cred-mech
realm={domain}
server-name={domain}
user={s['turn_user']}:{s['turn_secret']}
external-ip={public_ip}
no-cli
no-multicast-peers
stale-nonce=600
log-file=stdout
simple-log
# cert=/etc/coturn/certs/fullchain.pem
# pkey=/etc/coturn/certs/privkey.pem
"""})

    # ---- livekit config ----
    if "livekit" in sel:
        files.append({"name": "livekit/livekit.yaml", "language": "yaml", "content":
            f"""port: 7880
rtc:
  tcp_port: 7881
  port_range_start: 50000
  port_range_end: 50100
  use_external_ip: true
keys:
  {s['livekit_api_key']}: {s['livekit_api_secret']}
turn:
  enabled: false
"""})

    # ---- docker-compose ----
    files.append({"name": "compose.yml", "language": "yaml", "content": _build_compose(sel, domain)})

    # ---- firewall ----
    fw = ["#!/usr/bin/env bash", "set -euo pipefail", "# Open ports required by the selected services.",
          "sudo ufw allow 80/tcp", "sudo ufw allow 443/tcp"]
    if "coturn" in sel:
        fw += ["sudo ufw allow 3478/tcp", "sudo ufw allow 3478/udp", "sudo ufw allow 5349/tcp",
               "sudo ufw allow 5349/udp", "sudo ufw allow 49160:49260/udp"]
    if "livekit" in sel:
        fw += ["sudo ufw allow 7880/tcp", "sudo ufw allow 7881/tcp", "sudo ufw allow 50000:50100/udp"]
    files.append({"name": "firewall.sh", "language": "bash", "content": "\n".join(fw) + "\n"})

    # ---- install.sh ----
    files.append({"name": "install.sh", "language": "bash", "content":
        f"""#!/usr/bin/env bash
set -euo pipefail
# One-command installer. Run on a fresh Ubuntu/Debian VM with a public IP.
if [ "$(id -u)" -ne 0 ]; then echo "Run with sudo."; exit 1; fi

# 1. Docker
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi

# 2. Grab source from GitHub (optional — images are used by compose)
bash ./clone-repos.sh || true

# 3. Open firewall ports
bash ./firewall.sh || true

# 4. Bring the stack up
docker compose --env-file .env -f compose.yml pull
docker compose --env-file .env -f compose.yml up -d
docker compose -f compose.yml ps

echo ""
echo "Stack is up. Now open Stitches -> Admin -> Meetings and paste:"
echo "  TURN URLs      : turn:{domain}:3478"
echo "  TURN Username  : {s['turn_user']}"
echo "  TURN Credential: {s['turn_secret']}"
echo "  LiveKit URL    : wss://livekit.{domain}"
echo "  LiveKit Key    : {s['livekit_api_key']}"
echo "  LiveKit Secret : {s['livekit_api_secret']}"
"""})

    # ---- DEPLOY.md ----
    dns = [f"{domain}            -> {public_ip}",
           f"www.{domain}        -> {public_ip}"]
    if "livekit" in sel:
        dns.append(f"livekit.{domain}    -> {public_ip}")
    if "coturn" in sel:
        dns.append(f"turn.{domain}       -> {public_ip}")
    if "grafana" in sel:
        dns.append(f"grafana.{domain}    -> {public_ip}")
    files.append({"name": "DEPLOY.md", "language": "markdown", "content":
        f"""# Stitches Deployment Bundle

Selected services: {', '.join(_CAT_BY_ID[i]['name'] for i in sel)}

## 1. DNS records
```
{chr(10).join(dns)}
```

## 2. Deploy (on your VM)
```bash
unzip stitches-deploy.zip && cd stitches-deploy
sudo bash install.sh
```

## 3. Connect calls to Stitches
After the stack is up, open **Admin -> Meetings** in Stitches and either click
**"Apply generated call credentials"** (auto-fills everything) or paste manually:

| Field | Value |
|-------|-------|
| TURN URLs | `turn:{domain}:3478` |
| TURN Username | `{s['turn_user']}` |
| TURN Credential | `{s['turn_secret']}` |
| LiveKit URL | `wss://livekit.{domain}` |
| LiveKit API Key | `{s['livekit_api_key']}` |
| LiveKit API Secret | `{s['livekit_api_secret']}` |

Then hit **Test connectivity** to confirm the relay is reachable.

> Note: services marked "already provided by Stitches" (messaging, auth, DB, storage)
> are included only if you explicitly selected them and are usually redundant.
"""})

    return files


async def _run_diagnostics(autofix: bool, trigger: str = "manual"):
    checks = []
    fixed = []

    def add(cid, label, status, detail, needs_admin=False, fix_hint="", autofixed=False):
        checks.append({"id": cid, "label": label, "status": status, "detail": detail,
                       "needs_admin": needs_admin, "fix_hint": fix_hint, "autofixed": autofixed})

    try:
        await db.command("ping")
        add("mongo", "Database connectivity", "ok", "MongoDB is reachable.")
    except Exception as e:
        add("mongo", "Database connectivity", "fail", f"MongoDB ping failed: {e}", needs_admin=True,
            fix_hint="Check MONGO_URL in backend/.env and that MongoDB is running.")

    if os.environ.get("EMERGENT_LLM_KEY"):
        add("llm", "AI (Emergent LLM key)", "ok", "LLM key present — AI assistant and memory work.")
    else:
        add("llm", "AI (Emergent LLM key)", "fail", "EMERGENT_LLM_KEY not set.", needs_admin=True,
            fix_hint="Add EMERGENT_LLM_KEY to backend/.env (Profile -> Manage plan -> Universal Key).")

    add("frontendurl", "Frontend -> backend URL", "ok", "Frontend uses REACT_APP_BACKEND_URL for API calls.")

    from services.email import get_email_provider_cfg, get_smtp_cfg, get_email_health
    prov = await get_email_provider_cfg()
    smtp = await get_smtp_cfg()
    health = await get_email_health()
    email_ready = bool((prov.get("provider") and prov.get("provider") != "gmail") or smtp.get("host"))
    if health and health.get("ok"):
        add("email", "Email delivery", "ok", "Last email send succeeded.")
    elif email_ready:
        add("email", "Email delivery", "warn", f"Email is configured but last send may have failed: {(health or {}).get('detail','no recent send')}",
            needs_admin=True, fix_hint="Verify the key/credentials in Admin -> Email, then send a test digest.")
    else:
        add("email", "Email delivery", "fail", "No working email provider configured.", needs_admin=True,
            fix_hint="Add a Mailgun/Resend key or SMTP credentials in Admin -> Email. Digests and invites need this.")

    turn = ((await db.settings.find_one({"key": "turn"})) or {}).get("value", {})
    if turn.get("urls"):
        add("turn", "Calls - TURN server", "ok", f"TURN configured: {turn.get('urls')}")
    else:
        add("turn", "Calls - TURN server", "warn", "No TURN server set - calls behind strict NATs may fail.",
            needs_admin=True, fix_hint="Deploy coturn from the Deployment Center, then Apply generated call credentials.")

    lk = ((await db.settings.find_one({"key": "livekit"})) or {}).get("value", {})
    if lk.get("enabled") and lk.get("url"):
        add("livekit", "Calls - LiveKit SFU", "ok", f"LiveKit configured: {lk.get('url')}")
    else:
        add("livekit", "Calls - LiveKit SFU", "warn", "LiveKit not configured - large group meetings unavailable.",
            needs_admin=True, fix_hint="Deploy LiveKit from the Deployment Center, then Apply generated call credentials.")

    cfg = await _load_cfg()
    if cfg["secrets"]:
        add("deploysecrets", "Deployment secrets", "ok", "Deploy bundle secrets are generated.")
    elif autofix:
        cfg["secrets"] = _gen_secrets()
        await db.settings.update_one({"key": "deploy_center"},
                                     {"$set": {"key": "deploy_center", "value": {**cfg, "secrets": cfg["secrets"]}}}, upsert=True)
        fixed.append("Generated deployment bundle secrets")
        add("deploysecrets", "Deployment secrets", "ok", "Deploy secrets were missing - auto-generated.", autofixed=True)
    else:
        add("deploysecrets", "Deployment secrets", "warn", "No deploy secrets yet.",
            fix_hint="Click 'Generate bundle' in the Deployment Center (or re-run with auto-fix).")

    if cfg["domain"] and cfg["public_ip"]:
        add("deploytarget", "Deployment target", "ok", f"Domain {cfg['domain']} / IP {cfg['public_ip']} set.")
    else:
        add("deploytarget", "Deployment target", "warn", "Domain and/or public IP not set.",
            needs_admin=True, fix_hint="Enter your domain and server public IP in the Deployment Center.")

    mem_doc = await db.settings.find_one({"key": "ai_memory"})
    if mem_doc:
        add("aimemory", "AI memory settings", "ok", "AI memory configuration present.")
    elif autofix:
        await db.settings.update_one({"key": "ai_memory"},
                                     {"$set": {"key": "ai_memory", "value": {"user_enabled": True, "workspace_enabled": False, "retention_days": 90, "max_items": 200}}}, upsert=True)
        fixed.append("Initialised default AI memory settings")
        add("aimemory", "AI memory settings", "ok", "No memory config found - initialised defaults.", autofixed=True)
    else:
        add("aimemory", "AI memory settings", "warn", "No AI memory config found.",
            fix_hint="Open Admin -> AI Memory and save settings (or re-run with auto-fix).")

    admin_count = await db.users.count_documents({"role": {"$in": ["admin", "super_admin"]}})
    if admin_count:
        add("admin", "Admin account", "ok", f"{admin_count} admin account(s) present.")
    else:
        add("admin", "Admin account", "fail", "No admin account found.", needs_admin=True, fix_hint="Seed an admin account.")

    nbots = await db.bots.count_documents({})
    add("bots", "Bot integrations", "ok",
        "No bots registered (nothing to check)." if nbots == 0 else f"{nbots} bot(s) registered. See Admin -> Bot Actions for callback health.")

    if autofix:
        try:
            await db.ai_memories.create_index([("scope", 1), ("owner_id", 1), ("created_at", -1)])
            await db.bot_actions.create_index([("bot_id", 1), ("created_at", -1)])
            fixed.append("Ensured database indexes for memory & bot actions")
            add("indexes", "Database indexes", "ok", "Key indexes ensured.", autofixed=True)
        except Exception as e:
            add("indexes", "Database indexes", "warn", f"Could not ensure indexes: {e}")
    else:
        add("indexes", "Database indexes", "warn", "Index check skipped (run with auto-fix to ensure).",
            fix_hint="Re-run diagnostics with auto-fix enabled.")

    summary = {"ok": sum(1 for c in checks if c["status"] == "ok"),
               "warn": sum(1 for c in checks if c["status"] == "warn"),
               "fail": sum(1 for c in checks if c["status"] == "fail")}
    report = {"generated_at": now_iso(), "autofix": autofix, "summary": summary,
              "auto_fixed": fixed, "checks": checks}
    await db.settings.update_one({"key": "last_diagnostics"},
                                 {"$set": {"key": "last_diagnostics", "value": report}}, upsert=True)
    # Append to scan history (compact) and prune to last 100
    await db.diagnostics_history.insert_one({
        "run_id": f"run_{uuid.uuid4().hex[:10]}", "generated_at": report["generated_at"],
        "trigger": trigger, "summary": summary, "auto_fixed": len(fixed),
        "statuses": {c["id"]: c["status"] for c in checks}})
    old = await db.diagnostics_history.find({}, {"_id": 1}).sort("generated_at", -1).skip(100).to_list(500)
    if old:
        await db.diagnostics_history.delete_many({"_id": {"$in": [o["_id"] for o in old]}})
    await _sync_public_incidents(report)
    return report


def _diag_markdown(report):
    icon = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}
    lines = ["# Stitches Diagnostics Report", f"_Generated: {report['generated_at']}_", "",
             f"**Summary:** {report['summary']['ok']} OK - {report['summary']['warn']} warnings - {report['summary']['fail']} failing", ""]
    if report.get("auto_fixed"):
        lines += ["## Auto-fixed by System AI"] + [f"- {f}" for f in report["auto_fixed"]] + [""]
    lines.append("## Checks")
    for c in report["checks"]:
        lines.append(f"### {icon.get(c['status'],'')} {c['label']} - {c['status'].upper()}")
        lines.append(c["detail"])
        if c.get("needs_admin"):
            lines.append(f"> **Needs admin:** {c.get('fix_hint','')}")
        elif c.get("fix_hint") and not c.get("autofixed"):
            lines.append(f"> Suggested: {c.get('fix_hint')}")
        lines.append("")
    return "\n".join(lines)


@router.post("/admin/deploy/diagnose")
async def deploy_diagnose(request: Request, user: dict = Depends(require_admin)):
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    report = await _run_diagnostics(bool(body.get("autofix", True)))
    await log_activity(user["user_id"], "deploy_diagnose")
    return report


@router.get("/admin/deploy/diagnose/download")
async def deploy_diagnose_download(user: dict = Depends(require_admin)):
    doc = await db.settings.find_one({"key": "last_diagnostics"})
    report = (doc or {}).get("value")
    if not report:
        report = await _run_diagnostics(False)
    md = _diag_markdown(report)
    return StreamingResponse(io.BytesIO(md.encode()), media_type="text/markdown",
                             headers={"Content-Disposition": "attachment; filename=stitches-diagnostics.md"})


_RANK = {"ok": 0, "warn": 1, "fail": 2}


async def scan_auto_diagnostics():
    """Scheduled: re-scan the app and alert admins about anything that newly broke."""
    try:
        auto = ((await db.settings.find_one({"key": "diagnostics_auto"})) or {}).get("value", {})
        if not auto.get("enabled", False):
            return 0
        prev_doc = await db.settings.find_one({"key": "last_diagnostics"})
        prev = {c["id"]: c["status"] for c in ((prev_doc or {}).get("value", {}) or {}).get("checks", [])}
        cooldown_min = int(auto.get("cooldown_min", 60))
        cooldown_cut = (datetime.now(timezone.utc) - timedelta(minutes=cooldown_min)).isoformat()
        report = await _run_diagnostics(True, trigger="auto")
        maint_keys = await _active_maintenance_group_keys()
        new_alerts = 0
        broke = []
        recovered = []
        for c in report["checks"]:
            was = prev.get(c["id"], "ok")
            if _RANK.get(c["status"], 0) > _RANK.get(was, 0):  # regressed
                # Silence: planned maintenance is in progress for this component
                if _GROUP_KEY_BY_ID.get(c["id"]) in maint_keys:
                    continue
                # Throttle: skip if we alerted on this check within the cooldown window
                recent = await db.diagnostics_alerts.find_one({"check_id": c["id"], "kind": {"$ne": "recovery"}, "created_at": {"$gte": cooldown_cut}})
                if recent:
                    continue
                await db.diagnostics_alerts.insert_one({
                    "alert_id": f"dga_{uuid.uuid4().hex[:10]}", "check_id": c["id"], "label": c["label"], "kind": "regression",
                    "from_status": was, "to_status": c["status"], "detail": c["detail"],
                    "fix_hint": c.get("fix_hint", ""), "created_at": now_iso(), "seen": False})
                broke.append(f"{c['label']} ({c['status']})")
                new_alerts += 1
            elif was in ("warn", "fail") and c["status"] == "ok":  # recovered
                await db.diagnostics_alerts.insert_one({
                    "alert_id": f"dga_{uuid.uuid4().hex[:10]}", "check_id": c["id"], "label": c["label"], "kind": "recovery",
                    "from_status": was, "to_status": "ok", "detail": c["detail"],
                    "fix_hint": "", "created_at": now_iso(), "seen": False})
                recovered.append(f"{c['label']}")
                new_alerts += 1
        if broke or recovered:
            await _dispatch_alerts(broke, recovered)
        return new_alerts
    except Exception as e:
        logger.error(f"auto diagnostics error: {e}")
        return 0


_bg_tasks = set()


def _spawn(coro):
    """Fire-and-forget a coroutine (keeps a ref so it isn't GC'd)."""
    t = asyncio.create_task(coro)
    _bg_tasks.add(t)
    t.add_done_callback(_bg_tasks.discard)
    return t



async def _record_delivery(channel, event, status, ok, error="", attempts=1):
    try:
        await db.webhook_deliveries.insert_one({"channel": channel, "event": event, "status": status,
                                                "ok": ok, "error": (error or "")[:200], "attempts": attempts, "at": now_iso()})
        old = await db.webhook_deliveries.find({"channel": channel}, {"_id": 1}).sort("at", -1).skip(15).to_list(200)
        if old:
            await db.webhook_deliveries.delete_many({"_id": {"$in": [o["_id"] for o in old]}})
    except Exception as e:
        logger.warning(f"delivery log failed: {e}")


async def _send(client, channel, url, payload, event, retries=2):
    """POST to a webhook with retry + backoff; record the (final) result in the delivery log."""
    delays = [1, 3]
    last_status, last_err = 0, ""
    for attempt in range(retries + 1):
        try:
            r = await client.post(url, json=payload)
            if 200 <= r.status_code < 300:
                await _record_delivery(channel, event, r.status_code, True, "", attempt + 1)
                return r.status_code
            last_status, last_err = r.status_code, f"HTTP {r.status_code}"
        except Exception as e:
            last_status, last_err = 0, str(e)
            logger.warning(f"{channel} {event} send attempt {attempt + 1} failed: {e}")
        if attempt < retries:
            await asyncio.sleep(delays[min(attempt, len(delays) - 1)])
    await _record_delivery(channel, event, last_status, False, last_err, retries + 1)
    return last_status or None


async def _dispatch_alerts(broke=None, recovered=None):
    """Send health alerts (regressions + recoveries) to every configured channel."""
    broke = broke or []
    recovered = recovered or []
    parts = []
    if broke:
        parts.append("Regressed: " + ", ".join(broke))
    if recovered:
        parts.append("Recovered: " + ", ".join(recovered))
    text = "Stitches health update — " + " | ".join(parts)
    # Email admins
    try:
        from services.email import send_email_detailed
        admins = await db.users.find({"role": {"$in": ["admin", "super_admin"]}}, {"email": 1}).to_list(50)
        html = "<h3>Stitches health update</h3>"
        if broke:
            html += "<p><strong>Newly regressed:</strong></p><ul>" + "".join(f"<li>{b}</li>" for b in broke) + "</ul>"
        if recovered:
            html += "<p><strong>Recovered ✅:</strong></p><ul>" + "".join(f"<li>{r}</li>" for r in recovered) + "</ul>"
        subject = "Stitches: subsystem recovered" if (recovered and not broke) else "Stitches: something newly broke"
        for a in admins:
            if a.get("email"):
                await send_email_detailed(a["email"], subject, html)
    except Exception as e:
        logger.warning(f"diag alert email failed: {e}")
    # Slack + generic webhook
    ch = ((await db.settings.find_one({"key": "alert_channels"})) or {}).get("value", {})
    import httpx
    emoji = ":white_check_mark:" if (recovered and not broke) else ":rotating_light:"
    sev = "outage" if broke else "recovery"
    async with httpx.AsyncClient(timeout=10) as client:
        if ch.get("slack_webhook") and _mode_allows(ch.get("slack_mode", "all"), "health", sev):
            await _send(client, "slack", ch["slack_webhook"], {"text": f"{emoji} {text}"}, "health")
        if ch.get("webhook_url") and _mode_allows(ch.get("webhook_mode", "all"), "health", sev):
            await _send(client, "webhook", ch["webhook_url"], {"event": "stitches.health.update", "message": text, "regressed": broke, "recovered": recovered}, "health")
        if ch.get("discord_webhook") and _mode_allows(ch.get("discord_mode", "all"), "health", sev):
            await _send(client, "discord", ch["discord_webhook"], {"content": f"{emoji} {text}"}, "health")
        if ch.get("whatsapp_webhook") and _mode_allows(ch.get("whatsapp_mode", "all"), "health", sev):
            await _send(client, "whatsapp", ch["whatsapp_webhook"], {"message": f"{text}", "event": "stitches.health.update"}, "health")


@router.get("/admin/deploy/diagnose/state")
async def diagnose_state(user: dict = Depends(require_admin)):
    auto = ((await db.settings.find_one({"key": "diagnostics_auto"})) or {}).get("value", {})
    alerts = await db.diagnostics_alerts.find({"seen": False}, {"_id": 0}).sort("created_at", -1).to_list(50)
    return {"auto_enabled": bool(auto.get("enabled", False)), "cooldown_min": int(auto.get("cooldown_min", 60)), "alerts": alerts}


@router.put("/admin/deploy/diagnose/auto")
async def set_diagnose_auto(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    cur = ((await db.settings.find_one({"key": "diagnostics_auto"})) or {}).get("value", {})
    val = {"enabled": bool(body.get("enabled", cur.get("enabled", False))),
           "cooldown_min": max(0, min(1440, int(body.get("cooldown_min", cur.get("cooldown_min", 60)))))}
    await db.settings.update_one({"key": "diagnostics_auto"},
                                 {"$set": {"key": "diagnostics_auto", "value": val}}, upsert=True)
    return {"ok": True, **val}


@router.post("/admin/deploy/diagnose/alerts/seen")
async def mark_alerts_seen(user: dict = Depends(require_admin)):
    res = await db.diagnostics_alerts.update_many({"seen": False}, {"$set": {"seen": True}})
    return {"ok": True, "cleared": res.modified_count}


@router.get("/admin/deploy/diagnose/history")
async def diagnose_history(user: dict = Depends(require_admin)):
    runs = await db.diagnostics_history.find({}, {"_id": 0}).sort("generated_at", -1).to_list(50)
    return {"runs": runs}


_CHANNEL_MODES = ("all", "incidents", "outages", "maintenance")


def _mode_allows(mode, category, severity=""):
    """Whether a channel with the given routing mode should receive an event of this category/severity."""
    if mode not in _CHANNEL_MODES:
        mode = "all"
    if mode == "all":
        return True
    if mode == "maintenance":
        return category == "maintenance"
    if mode == "incidents":
        return category in ("incident", "health")
    if mode == "outages":
        return severity == "outage"
    return True


@router.get("/admin/deploy/alert-channels")
async def get_alert_channels(user: dict = Depends(require_admin)):
    ch = ((await db.settings.find_one({"key": "alert_channels"})) or {}).get("value", {})
    return {"slack_webhook": ch.get("slack_webhook", ""), "webhook_url": ch.get("webhook_url", ""),
            "discord_webhook": ch.get("discord_webhook", ""), "whatsapp_webhook": ch.get("whatsapp_webhook", ""),
            "slack_mode": ch.get("slack_mode", "all"), "webhook_mode": ch.get("webhook_mode", "all"),
            "discord_mode": ch.get("discord_mode", "all"), "whatsapp_mode": ch.get("whatsapp_mode", "all")}


@router.put("/admin/deploy/alert-channels")
async def set_alert_channels(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()

    def _m(v):
        v = (v or "all")
        return v if v in _CHANNEL_MODES else "all"
    val = {"slack_webhook": (body.get("slack_webhook") or "").strip(),
           "webhook_url": (body.get("webhook_url") or "").strip(),
           "discord_webhook": (body.get("discord_webhook") or "").strip(),
           "whatsapp_webhook": (body.get("whatsapp_webhook") or "").strip(),
           "slack_mode": _m(body.get("slack_mode")), "webhook_mode": _m(body.get("webhook_mode")),
           "discord_mode": _m(body.get("discord_mode")), "whatsapp_mode": _m(body.get("whatsapp_mode"))}
    await db.settings.update_one({"key": "alert_channels"},
                                 {"$set": {"key": "alert_channels", "value": val}}, upsert=True)
    return {"ok": True, **val}


@router.post("/admin/deploy/alert-channels/test")
async def test_alert_channels(user: dict = Depends(require_admin)):
    _spawn(_dispatch_alerts(broke=["Test alert — sample regression"], recovered=["Test — sample recovery"]))
    ch = ((await db.settings.find_one({"key": "alert_channels"})) or {}).get("value", {})
    return {"ok": True, "queued": True, "sent_to": {"email": True, "slack": bool(ch.get("slack_webhook")), "webhook": bool(ch.get("webhook_url")),
                                                    "discord": bool(ch.get("discord_webhook")), "whatsapp": bool(ch.get("whatsapp_webhook"))}}


@router.post("/admin/deploy/alert-channels/test-one")
async def test_one_channel(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    channel = body.get("channel")
    url = (body.get("url") or "").strip()
    if not url:
        ch = ((await db.settings.find_one({"key": "alert_channels"})) or {}).get("value", {})
        url = ch.get({"slack": "slack_webhook", "discord": "discord_webhook",
                      "whatsapp": "whatsapp_webhook", "webhook": "webhook_url"}.get(channel, ""), "")
    if not url:
        raise HTTPException(status_code=400, detail="Enter a URL for this channel first")
    text = "Stitches test — this channel is wired up correctly. 🎉"
    payload = {"slack": {"text": text}, "discord": {"content": text},
               "whatsapp": {"message": text, "event": "stitches.test"},
               "webhook": {"event": "stitches.test", "message": text}}.get(channel, {"message": text})
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json=payload)
        await _record_delivery(channel, "test", r.status_code, 200 <= r.status_code < 300)
        return {"ok": 200 <= r.status_code < 300, "status": r.status_code}
    except Exception as e:
        await _record_delivery(channel, "test", 0, False, str(e))
        raise HTTPException(status_code=502, detail=f"Delivery failed: {e}")


@router.get("/admin/deploy/alert-channels/deliveries")
async def get_channel_deliveries(user: dict = Depends(require_admin)):
    rows = await db.webhook_deliveries.find({}, {"_id": 0}).sort("at", -1).to_list(120)
    out = {}
    for r in rows:
        out.setdefault(r["channel"], [])
        if len(out[r["channel"]]) < 8:
            out[r["channel"]].append(r)
    return {"deliveries": out}


# ---------------- Incident notes ----------------
@router.get("/admin/deploy/diagnose/alerts/all")
async def all_alerts(user: dict = Depends(require_admin)):
    alerts = await db.diagnostics_alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return {"alerts": alerts}


@router.patch("/admin/deploy/diagnose/alerts/{alert_id}/note")
async def set_alert_note(alert_id: str, request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    note = (body.get("note") or "").strip()[:280]
    res = await db.diagnostics_alerts.update_one({"alert_id": alert_id}, {"$set": {"note": note}})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="alert not found")
    await log_activity(user["user_id"], "incident_note")
    return {"ok": True, "note": note}


# ---------------- Public status page ----------------
# Curated, sanitised subsystem groups (internal check ids -> friendly public labels).
PUBLIC_GROUPS = [
    {"key": "platform", "label": "Platform", "ids": ["mongo", "admin", "frontendurl"]},
    {"key": "ai", "label": "AI Assistant", "ids": ["llm", "aimemory"]},
    {"key": "calls", "label": "Calls & Meetings", "ids": ["turn", "livekit"]},
    {"key": "email", "label": "Email delivery", "ids": ["email"]},
]
_ID_TO_GROUP = {i: g["label"] for g in PUBLIC_GROUPS for i in g["ids"]}
_GROUP_KEY_BY_ID = {i: g["key"] for g in PUBLIC_GROUPS for i in g["ids"]}


async def _status_page_cfg():
    v = ((await db.settings.find_one({"key": "status_page"})) or {}).get("value", {})
    return {"enabled": bool(v.get("enabled", False)), "title": v.get("title", "Stitches Status"),
            "auto_incidents": bool(v.get("auto_incidents", True)),
            "accent": v.get("accent", ""), "logo_path": v.get("logo_path", ""), "logo_v": v.get("logo_v", "")}


def _valid_hex(c):
    return bool(re.fullmatch(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})", c or ""))


def _logo_url(cfg):
    base = (os.environ.get("FRONTEND_URL", "") or "").rstrip("/")
    return f"{base}/api/status/logo?v={cfg['logo_v']}" if cfg.get("logo_path") else ""


@router.get("/admin/deploy/status-page")
async def get_status_page(user: dict = Depends(require_admin)):
    cfg = await _status_page_cfg()
    subs = await db.status_subscribers.count_documents({"active": True})
    open_inc = await db.status_incidents.count_documents({"status": "investigating"})
    return {"enabled": cfg["enabled"], "title": cfg["title"], "auto_incidents": cfg["auto_incidents"],
            "accent": cfg["accent"], "logo": _logo_url(cfg), "subscribers": subs, "open_incidents": open_inc}


@router.put("/admin/deploy/status-page")
async def set_status_page(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    cur = await _status_page_cfg()
    title = (body.get("title") if body.get("title") is not None else cur["title"]) or ""
    if body.get("accent") is not None:
        accent = (body.get("accent") or "").strip()
        if accent and not _valid_hex(accent):
            raise HTTPException(status_code=400, detail="accent must be a hex color like #a11a2b")
    else:
        accent = cur["accent"]
    val = {"enabled": bool(body.get("enabled", cur["enabled"])),
           "title": title.strip()[:60] or "Stitches Status",
           "auto_incidents": bool(body.get("auto_incidents", cur["auto_incidents"])),
           "accent": accent, "logo_path": cur["logo_path"], "logo_v": cur["logo_v"]}
    await db.settings.update_one({"key": "status_page"},
                                 {"$set": {"key": "status_page", "value": val}}, upsert=True)
    return {"ok": True, "enabled": val["enabled"], "title": val["title"],
            "auto_incidents": val["auto_incidents"], "accent": val["accent"], "logo": _logo_url(val)}


@router.post("/admin/deploy/status-logo")
async def upload_status_logo(file: UploadFile = File(...), user: dict = Depends(require_admin)):
    ct = file.content_type or ""
    if not ct.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    data = await file.read()
    if len(data) > 2 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Logo too large (max 2MB)")
    ext = file.filename.split(".")[-1].lower() if "." in (file.filename or "") else "png"
    path = f"{APP_NAME}/status/logo/{uuid.uuid4()}.{ext}"
    result = put_object(path, data, ct or "image/png")
    cur = await _status_page_cfg()
    val = {"enabled": cur["enabled"], "title": cur["title"], "auto_incidents": cur["auto_incidents"],
           "accent": cur["accent"], "logo_path": result["path"], "logo_v": uuid.uuid4().hex[:8]}
    await db.settings.update_one({"key": "status_page"},
                                 {"$set": {"key": "status_page", "value": val}}, upsert=True)
    return {"ok": True, "logo": _logo_url(val)}


@router.delete("/admin/deploy/status-logo")
async def delete_status_logo(user: dict = Depends(require_admin)):
    cur = await _status_page_cfg()
    if cur.get("logo_path"):
        try:
            delete_object(cur["logo_path"])
        except Exception:
            pass
    val = {"enabled": cur["enabled"], "title": cur["title"], "auto_incidents": cur["auto_incidents"],
           "accent": cur["accent"], "logo_path": "", "logo_v": ""}
    await db.settings.update_one({"key": "status_page"},
                                 {"$set": {"key": "status_page", "value": val}}, upsert=True)
    return {"ok": True}


@router.get("/status/logo")
async def status_logo():
    cur = await _status_page_cfg()
    if not cur.get("logo_path"):
        raise HTTPException(status_code=404, detail="No logo")
    data, ct = get_object(cur["logo_path"])
    return FastResponse(content=data, media_type=ct or "image/png",
                        headers={"Cache-Control": "public, max-age=3600", "Access-Control-Allow-Origin": "*"})


def _worst(ids, statuses):
    r = 0
    for i in ids:
        s = statuses.get(i)
        if s:
            r = max(r, _RANK.get(s, 0))
    return {0: "ok", 1: "warn", 2: "fail"}[r]


# ---------------- Status subscribers (email updates) ----------------
async def _notify_subscribers(subject, html):
    """Best-effort email to everyone subscribed to the public status page."""
    try:
        from services.email import send_email_detailed
        subs = await db.status_subscribers.find({"active": True}, {"email": 1, "token": 1, "_id": 0}).to_list(2000)
        if not subs:
            return
        base = (os.environ.get("FRONTEND_URL", "") or "").rstrip("/")
        for s in subs:
            foot = (f'<p style="font-size:11px;color:#888;margin-top:24px">You are subscribed to Stitches status updates. '
                    f'<a href="{base}/api/status/unsubscribe?token={s.get("token","")}">Unsubscribe</a>.</p>') if base else ""
            await send_email_detailed(s["email"], subject, html + foot)
    except Exception as e:
        logger.warning(f"status subscriber notify failed: {e}")


@router.post("/status/subscribe")
async def status_subscribe(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    if "@" not in email or "." not in email.split("@")[-1] or len(email) > 200:
        raise HTTPException(status_code=400, detail="Enter a valid email")
    cfg = await _status_page_cfg()
    if not cfg["enabled"]:
        raise HTTPException(status_code=404, detail="Status page not available")
    existing = await db.status_subscribers.find_one({"email": email})
    if existing:
        if not existing.get("active"):
            await db.status_subscribers.update_one({"_id": existing["_id"]}, {"$set": {"active": True}})
        return {"ok": True, "already": True}
    await db.status_subscribers.insert_one({"email": email, "token": pysecrets.token_urlsafe(18),
                                            "active": True, "created_at": now_iso()})
    return {"ok": True}


@router.get("/status/unsubscribe")
async def status_unsubscribe(token: str = ""):
    if token:
        await db.status_subscribers.update_one({"token": token}, {"$set": {"active": False}})
    return HTMLResponse("<html><body style='font-family:system-ui,sans-serif;text-align:center;padding:64px;background:#1a0d10;color:#f3e9ea'>"
                        "<h2>You're unsubscribed</h2><p>You will no longer receive Stitches status updates.</p></body></html>")


async def _active_maintenance_group_keys():
    """Group keys currently under an in-progress maintenance window (auto-incidents silenced)."""
    now = datetime.now(timezone.utc)
    items = await db.maintenance_windows.find({"status": {"$ne": "cancelled"}}).to_list(200)
    keys = set()
    for m in items:
        if _maint_status(m, now) == "in_progress":
            for k in (m.get("group_keys") or []):
                keys.add(k)
    return keys


async def _notify_incident_channels(event, label, impact="", text="", component=""):
    """Post incident open/update/resolve events to the configured Slack, Discord, WhatsApp + generic webhooks."""
    ch = ((await db.settings.find_one({"key": "alert_channels"})) or {}).get("value", {})
    if not any(ch.get(k) for k in ("slack_webhook", "webhook_url", "discord_webhook", "whatsapp_webhook")):
        return
    base = (os.environ.get("FRONTEND_URL", "") or "").rstrip("/")
    link = (f"{base}/status/{component}" if (base and component) else (f"{base}/status" if base else ""))
    verb = {"opened": "opened", "update": "updated", "resolved": "resolved"}.get(event, event)
    emoji = ":white_check_mark:" if event == "resolved" else (":rotating_light:" if event == "opened" else ":memo:")
    summary = f"{label}: incident {verb}" + (f" ({impact})" if impact else "")
    msg_text = f"{emoji} {summary}" + (f"\n{text}" if text else "") + (f"\n{link}" if link else "")
    sev = "recovery" if event == "resolved" else (impact or "")
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        if ch.get("slack_webhook") and _mode_allows(ch.get("slack_mode", "all"), "incident", sev):
            await _send(client, "slack", ch["slack_webhook"], {"text": msg_text}, f"incident.{event}")
        if ch.get("discord_webhook") and _mode_allows(ch.get("discord_mode", "all"), "incident", sev):
            await _send(client, "discord", ch["discord_webhook"], {"content": msg_text}, f"incident.{event}")
        if ch.get("whatsapp_webhook") and _mode_allows(ch.get("whatsapp_mode", "all"), "incident", sev):
            await _send(client, "whatsapp", ch["whatsapp_webhook"], {"message": summary + (f" — {text}" if text else ""), "event": f"stitches.incident.{event}", "link": link}, f"incident.{event}")
        if ch.get("webhook_url") and _mode_allows(ch.get("webhook_mode", "all"), "incident", sev):
            await _send(client, "webhook", ch["webhook_url"], {"event": f"stitches.incident.{event}", "label": label, "impact": impact, "text": text, "component": component, "link": link}, f"incident.{event}")


async def _dispatch_maint_to_channels(text):
    """Fan out maintenance heads-ups to channels that opted into maintenance/all events."""
    ch = ((await db.settings.find_one({"key": "alert_channels"})) or {}).get("value", {})
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        if ch.get("slack_webhook") and _mode_allows(ch.get("slack_mode", "all"), "maintenance"):
            await _send(client, "slack", ch["slack_webhook"], {"text": f":wrench: {text}"}, "maintenance")
        if ch.get("discord_webhook") and _mode_allows(ch.get("discord_mode", "all"), "maintenance"):
            await _send(client, "discord", ch["discord_webhook"], {"content": f":wrench: {text}"}, "maintenance")
        if ch.get("whatsapp_webhook") and _mode_allows(ch.get("whatsapp_mode", "all"), "maintenance"):
            await _send(client, "whatsapp", ch["whatsapp_webhook"], {"message": text, "event": "stitches.maintenance"}, "maintenance")
        if ch.get("webhook_url") and _mode_allows(ch.get("webhook_mode", "all"), "maintenance"):
            await _send(client, "webhook", ch["webhook_url"], {"event": "stitches.maintenance", "message": text}, "maintenance")


# ---------------- Public incidents (auto + manual) ----------------
async def _sync_public_incidents(report):
    """Open a public incident when a subsystem breaks; resolve it when it recovers."""
    cfg = await _status_page_cfg()
    if not cfg.get("auto_incidents", True):
        return
    maint_keys = await _active_maintenance_group_keys()
    latest = {c["id"]: c["status"] for c in report.get("checks", [])}
    for g in PUBLIC_GROUPS:
        st = _worst(g["ids"], latest)
        openinc = await db.status_incidents.find_one({"group_key": g["key"], "status": "investigating"})
        if st != "ok" and not openinc:
            if g["key"] in maint_keys:
                continue  # silenced: planned maintenance is in progress for this component
            impact = "outage" if st == "fail" else "degraded"
            word = "down" if st == "fail" else "degraded"
            inc = {"incident_id": f"inc_{uuid.uuid4().hex[:10]}", "group_key": g["key"],
                   "group_label": g["label"], "status": "investigating", "impact": impact,
                   "opened_at": now_iso(), "resolved_at": None, "auto": True,
                   "updates": [{"at": now_iso(), "kind": "opened",
                                "text": f"Auto-detected: {g['label']} is {word}. We're investigating."}]}
            await db.status_incidents.insert_one(inc)
            await _notify_subscribers(
                f"[Stitches] Incident opened — {g['label']} {impact}",
                f"<h3>{g['label']} — {impact.title()}</h3>"
                f"<p>We're investigating an issue affecting <strong>{g['label']}</strong>.</p>")
            await _notify_incident_channels("opened", g["label"], impact, f"Auto-detected: {g['label']} is {word}.", g["key"])
        elif st == "ok" and openinc:
            await db.status_incidents.update_one({"_id": openinc["_id"]},
                {"$set": {"status": "resolved", "resolved_at": now_iso()},
                 "$push": {"updates": {"at": now_iso(), "kind": "resolved",
                                       "text": f"{g['label']} has recovered — all checks passing."}}})
            await _notify_subscribers(
                f"[Stitches] Resolved — {g['label']}",
                f"<h3>{g['label']} — Resolved ✅</h3>"
                f"<p>The issue affecting <strong>{g['label']}</strong> has been resolved.</p>")
            await _notify_incident_channels("resolved", g["label"], "", f"{g['label']} has recovered — all checks passing.", g["key"])


@router.get("/admin/deploy/status-incidents")
async def list_status_incidents(user: dict = Depends(require_admin)):
    incs = await db.status_incidents.find({}, {"_id": 0}).sort("opened_at", -1).to_list(50)
    incs = sorted(incs, key=lambda x: x.get("status") == "resolved")
    return {"incidents": incs, "groups": [{"key": g["key"], "label": g["label"]} for g in PUBLIC_GROUPS]}


@router.post("/admin/deploy/status-incidents")
async def create_status_incident(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    gk = body.get("group_key")
    g = next((x for x in PUBLIC_GROUPS if x["key"] == gk), None)
    label = g["label"] if g else (body.get("label") or "Platform")
    impact = body.get("impact") if body.get("impact") in ("degraded", "outage") else "degraded"
    text = (body.get("text") or f"Investigating an issue affecting {label}.").strip()[:400]
    inc = {"incident_id": f"inc_{uuid.uuid4().hex[:10]}", "group_key": gk or "platform",
           "group_label": label, "status": "investigating", "impact": impact,
           "opened_at": now_iso(), "resolved_at": None, "auto": False,
           "updates": [{"at": now_iso(), "kind": "opened", "text": text}]}
    await db.status_incidents.insert_one(inc)
    await log_activity(user["user_id"], "incident_open")

    async def _notify():
        await _notify_subscribers(f"[Stitches] Incident opened — {label} {impact}",
                                  f"<h3>{label} — {impact.title()}</h3><p>{text}</p>")
        await _notify_incident_channels("opened", label, impact, text, gk or "")
    _spawn(_notify())
    return {"ok": True, "incident_id": inc["incident_id"]}


@router.post("/admin/deploy/status-incidents/{incident_id}/update")
async def update_status_incident(incident_id: str, request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    inc = await db.status_incidents.find_one({"incident_id": incident_id})
    if not inc:
        raise HTTPException(status_code=404, detail="incident not found")
    resolve = bool(body.get("resolve"))
    text = (body.get("text") or ("Resolved." if resolve else "Update posted.")).strip()[:400]
    upd = {"at": now_iso(), "kind": "resolved" if resolve else "note", "text": text}
    setter = {"status": "resolved", "resolved_at": now_iso()} if resolve else {}
    await db.status_incidents.update_one({"incident_id": incident_id},
                                         {"$push": {"updates": upd}, **({"$set": setter} if setter else {})})
    await log_activity(user["user_id"], "incident_update")
    label = inc.get("group_label", "Service")
    subj = f"[Stitches] Resolved — {label}" if resolve else f"[Stitches] Update — {label}"
    head = f"<h3>{label} — {'Resolved ✅' if resolve else 'Update'}</h3><p>{text}</p>"

    async def _notify():
        await _notify_subscribers(subj, head)
        await _notify_incident_channels("resolved" if resolve else "update", label, "", text, inc.get("group_key", ""))
    _spawn(_notify())
    return {"ok": True}


@router.get("/admin/deploy/ops-overview")
async def ops_overview(user: dict = Depends(require_admin)):
    runs = await db.diagnostics_history.find({}, {"_id": 0}).sort("generated_at", -1).to_list(500)
    latest = (runs[0].get("statuses") or {}) if runs else {}

    def overall_worst(statuses):
        w = "ok"
        for g in PUBLIC_GROUPS:
            s = _worst(g["ids"], statuses)
            if _RANK.get(s, 0) > _RANK.get(w, 0):
                w = s
        return w
    worst = overall_worst(latest) if latest else "ok"
    overall = {"ok": "operational", "warn": "degraded", "fail": "outage"}[worst]
    # 7-day uptime trend (per-day overall % healthy)
    buckets = {}
    for r in runs:
        day = (r.get("generated_at") or "")[:10]
        if not day:
            continue
        st = overall_worst(r.get("statuses") or {})
        b = buckets.setdefault(day, {"ok": 0, "total": 0, "worst": "ok"})
        b["total"] += 1
        if st == "ok":
            b["ok"] += 1
        if _RANK.get(st, 0) > _RANK.get(b["worst"], 0):
            b["worst"] = st
    trend = [{"date": d, "pct": round(v["ok"] / v["total"] * 100) if v["total"] else 100, "status": v["worst"]}
             for d, v in sorted(buckets.items())][-7:]
    cfg = await _status_page_cfg()
    open_inc = await db.status_incidents.count_documents({"status": "investigating"})
    subs = await db.status_subscribers.count_documents({"active": True})
    recent = await db.webhook_deliveries.find({}, {"_id": 0}).sort("at", -1).to_list(6)
    now = datetime.now(timezone.utc)
    mwin = await db.maintenance_windows.find({"status": {"$ne": "cancelled"}}, {"_id": 0}).sort("starts_at", 1).to_list(50)
    next_maint = None
    for m in mwin:
        st = _maint_status(m, now)
        if st in ("scheduled", "in_progress"):
            next_maint = {"title": m.get("title"), "state": st, "starts_at": m.get("starts_at")}
            break
    return {"overall": overall, "open_incidents": open_inc, "subscribers": subs,
            "status_public": cfg["enabled"], "generated_at": runs[0]["generated_at"] if runs else None,
            "trend": trend, "recent_deliveries": recent, "next_maintenance": next_maint}


@router.get("/status/public")
async def public_status():
    """Public, unauthenticated status page data — only served when an admin enables it."""
    cfg = await _status_page_cfg()
    if not cfg["enabled"]:
        return {"enabled": False}
    runs = await db.diagnostics_history.find({}, {"_id": 0}).sort("generated_at", -1).to_list(200)
    latest = (runs[0].get("statuses") or {}) if runs else {}
    now = datetime.now(timezone.utc)
    WINDOWS = [("24h", 24), ("7d", 24 * 7), ("90d", 24 * 90)]

    def uptime_for(ids, wruns):
        seen = [r for r in wruns if any(i in (r.get("statuses") or {}) for i in ids)]
        okc = sum(1 for r in seen if _worst(ids, r.get("statuses") or {}) == "ok")
        pct = round(okc / len(seen) * 100) if seen else 100
        strip = [_worst(ids, r.get("statuses") or {}) for r in reversed(wruns)][-60:]
        return pct, strip

    groups = []
    for g in PUBLIC_GROUPS:
        cur = _worst(g["ids"], latest) if latest else "ok"
        windows = {}
        for wk, hrs in WINDOWS:
            cut = (now - timedelta(hours=hrs)).isoformat()
            wruns = [r for r in runs if (r.get("generated_at") or "") >= cut]
            pct, strip = uptime_for(g["ids"], wruns)
            windows[wk] = {"pct": pct, "strip": strip}
        groups.append({"key": g["key"], "label": g["label"], "status": cur,
                       "windows": windows, "uptime": windows["90d"]["pct"]})
    overall = "operational"
    if any(x["status"] == "fail" for x in groups):
        overall = "outage"
    elif any(x["status"] == "warn" for x in groups):
        overall = "degraded"

    raw = await db.status_incidents.find({}, {"_id": 0}).sort("opened_at", -1).to_list(30)
    raw = sorted(raw, key=lambda x: x.get("status") == "resolved")
    incidents = [{"label": i.get("group_label"), "status": i.get("status"), "impact": i.get("impact"),
                  "opened_at": i.get("opened_at"), "resolved_at": i.get("resolved_at"),
                  "updates": i.get("updates", []), "auto": i.get("auto", False)} for i in raw]
    mwin = await db.maintenance_windows.find({"status": {"$ne": "cancelled"}}, {"_id": 0}).sort("starts_at", 1).to_list(50)
    maintenance = []
    for m in mwin:
        st = _maint_status(m, now)
        if st in ("scheduled", "in_progress"):
            maintenance.append({"title": m.get("title"), "message": m.get("message"),
                                "starts_at": m.get("starts_at"), "ends_at": m.get("ends_at"), "state": st,
                                "components": [g["label"] for g in PUBLIC_GROUPS if g["key"] in (m.get("group_keys") or [])]})
    return {"enabled": True, "title": cfg["title"], "overall": overall,
            "accent": cfg.get("accent", ""), "logo": _logo_url(cfg),
            "windows": [w[0] for w in WINDOWS],
            "generated_at": runs[0]["generated_at"] if runs else now_iso(),
            "groups": groups, "incidents": incidents, "maintenance": maintenance}


def _parse(iso):
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except Exception:
        return None


def _maint_status(m, now):
    if m.get("status") == "cancelled":
        return "cancelled"
    s = _parse(m.get("starts_at")); e = _parse(m.get("ends_at"))
    if e and now > e:
        return "completed"
    if s and now >= s:
        return "in_progress"
    return "scheduled"


@router.get("/admin/deploy/maintenance")
async def list_maintenance(user: dict = Depends(require_admin)):
    now = datetime.now(timezone.utc)
    items = await db.maintenance_windows.find({}, {"_id": 0}).sort("starts_at", -1).to_list(100)
    for m in items:
        m["state"] = _maint_status(m, now)
    return {"maintenance": items, "groups": [{"key": g["key"], "label": g["label"]} for g in PUBLIC_GROUPS]}


@router.post("/admin/deploy/maintenance")
async def create_maintenance(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    starts = (body.get("starts_at") or "").strip()
    ends = (body.get("ends_at") or "").strip()
    ps, pe = _parse(starts), _parse(ends)
    if not ps or not pe:
        raise HTTPException(status_code=400, detail="Valid start and end time required")
    if pe <= ps:
        raise HTTPException(status_code=400, detail="End must be after start")
    gks = [k for k in (body.get("group_keys") or []) if any(g["key"] == k for g in PUBLIC_GROUPS)]
    m = {"maint_id": f"mnt_{uuid.uuid4().hex[:10]}",
         "title": (body.get("title") or "Scheduled maintenance").strip()[:100],
         "message": (body.get("message") or "").strip()[:500],
         "group_keys": gks, "starts_at": starts, "ends_at": ends,
         "notify_lead_min": max(0, min(10080, int(body.get("notify_lead_min", 60)))),
         "status": "scheduled", "reminder_sent": False, "created_at": now_iso()}
    await db.maintenance_windows.insert_one(m)
    await log_activity(user["user_id"], "maintenance_create")
    return {"ok": True, "maint_id": m["maint_id"]}


@router.delete("/admin/deploy/maintenance/{maint_id}")
async def delete_maintenance(maint_id: str, user: dict = Depends(require_admin)):
    await db.maintenance_windows.delete_one({"maint_id": maint_id})
    return {"ok": True}


async def scan_maintenance():
    """Email subscribers a heads-up before a scheduled maintenance window begins."""
    try:
        now = datetime.now(timezone.utc)
        items = await db.maintenance_windows.find(
            {"reminder_sent": {"$ne": True}, "status": {"$ne": "cancelled"}}).to_list(100)
        sent = 0
        for m in items:
            s = _parse(m.get("starts_at"))
            if not s:
                continue
            lead = m.get("notify_lead_min", 60)
            if s - timedelta(minutes=lead) <= now < s:
                gk = m.get("group_keys") or []
                labels = ", ".join(g["label"] for g in PUBLIC_GROUPS if g["key"] in gk) or "the platform"
                when = s.strftime("%b %d, %Y %H:%M UTC")
                await _notify_subscribers(
                    f"[Stitches] Upcoming maintenance — {m.get('title', 'Scheduled maintenance')}",
                    f"<h3>{m.get('title', 'Scheduled maintenance')}</h3>"
                    f"<p>Planned maintenance affecting <strong>{labels}</strong> begins at <strong>{when}</strong>.</p>"
                    f"<p>{m.get('message', '')}</p>")
                await _dispatch_maint_to_channels(
                    f"Upcoming maintenance: {m.get('title', 'Scheduled maintenance')} affecting {labels}, begins {when}."
                    + (f" {m.get('message', '')}" if m.get("message") else ""))
                await db.maintenance_windows.update_one({"maint_id": m["maint_id"]}, {"$set": {"reminder_sent": True}})
                sent += 1
        return sent
    except Exception as e:
        logger.warning(f"maintenance scan failed: {e}")
        return 0


# ---------------- Per-component detail ----------------
@router.get("/status/public/component/{key}")
async def public_component(key: str):
    cfg = await _status_page_cfg()
    if not cfg["enabled"]:
        return {"enabled": False}
    g = next((x for x in PUBLIC_GROUPS if x["key"] == key), None)
    if not g:
        raise HTTPException(status_code=404, detail="unknown component")
    runs = await db.diagnostics_history.find({}, {"_id": 0}).sort("generated_at", -1).to_list(500)
    latest = (runs[0].get("statuses") or {}) if runs else {}
    cur = _worst(g["ids"], latest) if latest else "ok"
    now = datetime.now(timezone.utc)
    windows = {}
    for wk, hrs in [("24h", 24), ("7d", 24 * 7), ("90d", 24 * 90)]:
        cut = (now - timedelta(hours=hrs)).isoformat()
        wruns = [r for r in runs if (r.get("generated_at") or "") >= cut]
        seen = [r for r in wruns if any(i in (r.get("statuses") or {}) for i in g["ids"])]
        okc = sum(1 for r in seen if _worst(g["ids"], r.get("statuses") or {}) == "ok")
        windows[wk] = {"pct": round(okc / len(seen) * 100) if seen else 100}
    buckets = {}
    for r in runs:
        d = (r.get("generated_at") or "")[:10]
        if not d:
            continue
        st = _worst(g["ids"], r.get("statuses") or {})
        b = buckets.setdefault(d, {"ok": 0, "total": 0, "worst": "ok"})
        b["total"] += 1
        if st == "ok":
            b["ok"] += 1
        if _RANK.get(st, 0) > _RANK.get(b["worst"], 0):
            b["worst"] = st
    daily = [{"date": d, "pct": round(v["ok"] / v["total"] * 100) if v["total"] else 100, "status": v["worst"]}
             for d, v in sorted(buckets.items())][-90:]
    raw = await db.status_incidents.find({"group_key": key}, {"_id": 0}).sort("opened_at", -1).to_list(50)
    incidents = [{"status": i.get("status"), "impact": i.get("impact"), "opened_at": i.get("opened_at"),
                  "resolved_at": i.get("resolved_at"), "updates": i.get("updates", []), "auto": i.get("auto", False)}
                 for i in raw]
    return {"enabled": True, "title": cfg["title"], "key": key, "label": g["label"],
            "accent": cfg.get("accent", ""), "logo": _logo_url(cfg),
            "status": cur, "windows": windows, "daily": daily, "incidents": incidents}


# ---------------- Embeddable status badge (SVG) ----------------
_BADGE_META = {
    "operational": ("operational", "#22c55e"),
    "degraded": ("degraded", "#f59e0b"),
    "outage": ("major outage", "#ef4444"),
    "maintenance": ("maintenance", "#3b82f6"),
    "unknown": ("unknown", "#9ca3af"),
}


def _render_badge(label, value, color):
    def w(t):
        return int(6.2 * len(t)) + 12
    lw, vw = w(label), w(value)
    total = lw + vw
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" role="img" aria-label="{label}: {value}">
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<mask id="m"><rect width="{total}" height="20" rx="3" fill="#fff"/></mask>
<g mask="url(#m)">
<rect width="{lw}" height="20" fill="#3b3138"/>
<rect x="{lw}" width="{vw}" height="20" fill="{color}"/>
<rect width="{total}" height="20" fill="url(#s)"/>
</g>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
<text x="{lw/2}" y="15" fill="#010101" fill-opacity=".3">{label}</text>
<text x="{lw/2}" y="14">{label}</text>
<text x="{lw+vw/2}" y="15" fill="#010101" fill-opacity=".3">{value}</text>
<text x="{lw+vw/2}" y="14">{value}</text>
</g></svg>'''


@router.get("/status/badge.svg")
async def status_badge(component: str = "", label: str = ""):
    cfg = await _status_page_cfg()
    state = "unknown"
    badge_label = label.strip()[:24] or "status"
    if cfg["enabled"]:
        runs = await db.diagnostics_history.find({}, {"_id": 0}).sort("generated_at", -1).to_list(1)
        latest = (runs[0].get("statuses") or {}) if runs else {}
        maint_keys = await _active_maintenance_group_keys()
        if component:
            g = next((x for x in PUBLIC_GROUPS if x["key"] == component), None)
            if g:
                if not badge_label or badge_label == "status":
                    badge_label = g["label"].lower()
                if g["key"] in maint_keys:
                    state = "maintenance"
                else:
                    s = _worst(g["ids"], latest) if latest else "ok"
                    state = {"ok": "operational", "warn": "degraded", "fail": "outage"}[s]
        else:
            worst = "ok"
            for g in PUBLIC_GROUPS:
                s = _worst(g["ids"], latest) if latest else "ok"
                if _RANK.get(s, 0) > _RANK.get(worst, 0):
                    worst = s
            if maint_keys:
                state = "maintenance"
            else:
                state = {"ok": "operational", "warn": "degraded", "fail": "outage"}[worst]
    value, color = _BADGE_META.get(state, _BADGE_META["unknown"])
    svg = _render_badge(badge_label, value, color)
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=60", "Access-Control-Allow-Origin": "*"})


# ---------------- Status history feed (RSS) ----------------
def _rss_date(iso):
    dt = _parse(iso) or datetime.now(timezone.utc)
    return format_datetime(dt)


@router.get("/status/feed.xml")
async def status_feed():
    cfg = await _status_page_cfg()
    base = (os.environ.get("FRONTEND_URL", "") or "").rstrip("/")
    title = cfg.get("title") or "Stitches Status"
    now = datetime.now(timezone.utc)
    entries = []  # (sort_iso, item_xml)
    if cfg["enabled"]:
        incs = await db.status_incidents.find({}, {"_id": 0}).sort("opened_at", -1).to_list(50)
        for i in incs:
            resolved = i.get("status") == "resolved"
            gk = i.get("group_key", "")
            label = i.get("group_label", "Service")
            head = "Resolved" if resolved else (i.get("impact") or "incident").title()
            ups = i.get("updates", [])
            desc = " | ".join(f"{u.get('text', '')} ({_rss_date(u.get('at'))})" for u in ups) or "Incident update"
            last = (ups[-1]["at"] if ups else i.get("opened_at")) or ""
            link = f"{base}/status/{gk}" if base else ""
            guid = f"incident-{i.get('opened_at', '')}-{gk}"
            entries.append((last, f"<item><title>{_xesc(label + ' — ' + head)}</title>"
                                  f"<link>{_xesc(link)}</link>"
                                  f"<guid isPermaLink=\"false\">{_xesc(guid)}</guid>"
                                  f"<pubDate>{_rss_date(last)}</pubDate>"
                                  f"<description>{_xesc(desc)}</description></item>"))
        mwin = await db.maintenance_windows.find({"status": {"$ne": "cancelled"}}, {"_id": 0}).sort("starts_at", -1).to_list(50)
        for m in mwin:
            state = _maint_status(m, now)
            comps = ", ".join(g["label"] for g in PUBLIC_GROUPS if g["key"] in (m.get("group_keys") or [])) or "the platform"
            desc = (f"{m.get('message', '')} — Affects {comps}. "
                    f"{_rss_date(m.get('starts_at'))} to {_rss_date(m.get('ends_at'))}").strip()
            link = f"{base}/status" if base else ""
            guid = f"maint-{m.get('maint_id', '')}"
            key = m.get("created_at") or m.get("starts_at") or ""
            entries.append((key, f"<item><title>{_xesc('Maintenance: ' + (m.get('title') or 'Scheduled maintenance') + ' (' + state + ')')}</title>"
                                 f"<link>{_xesc(link)}</link>"
                                 f"<guid isPermaLink=\"false\">{_xesc(guid)}</guid>"
                                 f"<pubDate>{_rss_date(key)}</pubDate>"
                                 f"<description>{_xesc(desc)}</description></item>"))
    body = "".join(x[1] for x in sorted(entries, key=lambda e: e[0], reverse=True)[:50])
    self_link = f"{base}/api/status/feed.xml" if base else ""
    site_link = f"{base}/status" if base else ""
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>'
           f'<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>'
           f'<title>{_xesc(title)}</title>'
           f'<link>{_xesc(site_link)}</link>'
           f'<atom:link href="{_xesc(self_link)}" rel="self" type="application/rss+xml"/>'
           f'<description>{_xesc("Incident and maintenance updates for " + title)}</description>'
           f'<lastBuildDate>{_rss_date(now.isoformat())}</lastBuildDate>'
           f'{body}</channel></rss>')
    return Response(content=xml, media_type="application/rss+xml",
                    headers={"Cache-Control": "public, max-age=120", "Access-Control-Allow-Origin": "*"})





def _build_compose(sel, domain):
    blocks = ["services:"]
    if "traefik" in sel:
        blocks.append(f"""  traefik:
    image: traefik:v3
    restart: unless-stopped
    command:
      - --providers.docker=true
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      - --certificatesresolvers.le.acme.tlschallenge=true
      - --certificatesresolvers.le.acme.email=admin@{domain}
      - --certificatesresolvers.le.acme.storage=/letsencrypt/acme.json
    ports: ["80:80", "443:443"]
    volumes:
      - ./letsencrypt:/letsencrypt
      - /var/run/docker.sock:/var/run/docker.sock:ro""")
    if "coturn" in sel:
        blocks.append("""  coturn:
    image: coturn/coturn:latest
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./coturn/turnserver.conf:/etc/turnserver.conf:ro
    command: ["-c", "/etc/turnserver.conf"]""")
    if "livekit" in sel:
        blocks.append("""  livekit:
    image: livekit/livekit-server:latest
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./livekit/livekit.yaml:/etc/livekit.yaml:ro
    command: ["--config", "/etc/livekit.yaml"]""")
    if "postgres" in sel:
        blocks.append("""  postgres:
    image: postgres:17
    restart: unless-stopped
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes: [postgres_data:/var/lib/postgresql/data]""")
    if "valkey" in sel:
        blocks.append("""  valkey:
    image: valkey/valkey:8
    restart: unless-stopped""")
    if "nats" in sel:
        blocks.append("""  nats:
    image: nats:2
    command: ["-js"]
    restart: unless-stopped""")
    if "minio" in sel:
        blocks.append("""  minio:
    image: minio/minio:latest
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: admin
      MINIO_ROOT_PASSWORD: ${MINIO_ROOT_PASSWORD}
    ports: ["9000:9000", "9001:9001"]
    volumes: [minio_data:/data]""")
    if "opensearch" in sel:
        blocks.append("""  opensearch:
    image: opensearchproject/opensearch:latest
    restart: unless-stopped
    environment:
      - discovery.type=single-node
      - OPENSEARCH_INITIAL_ADMIN_PASSWORD=${MINIO_ROOT_PASSWORD}
    volumes: [opensearch_data:/usr/share/opensearch/data]""")
    if "keycloak" in sel:
        blocks.append("""  keycloak:
    image: quay.io/keycloak/keycloak:latest
    command: start-dev
    environment:
      KC_BOOTSTRAP_ADMIN_USERNAME: admin
      KC_BOOTSTRAP_ADMIN_PASSWORD: ${KEYCLOAK_ADMIN_PASSWORD}
    ports: ["8080:8080"]""")
    if "prometheus" in sel:
        blocks.append("""  prometheus:
    image: prom/prometheus:latest
    restart: unless-stopped
    ports: ["9090:9090"]
    volumes: [prometheus_data:/prometheus]""")
    if "grafana" in sel:
        blocks.append("""  grafana:
    image: grafana/grafana:latest
    restart: unless-stopped
    environment:
      GF_SECURITY_ADMIN_PASSWORD: ${GRAFANA_ADMIN_PASSWORD}
    ports: ["3001:3000"]
    volumes: [grafana_data:/var/lib/grafana]""")
    if "loki" in sel:
        blocks.append("""  loki:
    image: grafana/loki:latest
    restart: unless-stopped
    ports: ["3100:3100"]""")
    if "clamav" in sel:
        blocks.append("""  clamav:
    image: clamav/clamav:latest
    restart: unless-stopped""")
    if "synapse" in sel:
        blocks.append("""  synapse:
    image: matrixdotorg/synapse:latest
    restart: unless-stopped
    volumes: [synapse_data:/data]
    ports: ["8008:8008"]""")
    if "element-web" in sel:
        blocks.append("""  element-web:
    image: vectorim/element-web:latest
    restart: unless-stopped
    ports: ["8009:80"]""")

    vols = []
    for name, ids in [("postgres_data", ["postgres"]), ("minio_data", ["minio"]),
                      ("grafana_data", ["grafana"]), ("prometheus_data", ["prometheus"]),
                      ("opensearch_data", ["opensearch"]), ("synapse_data", ["synapse"])]:
        if any(i in sel for i in ids):
            vols.append(f"  {name}: {{}}")
    body = "\n".join(blocks)
    if vols:
        body += "\nvolumes:\n" + "\n".join(vols)
    return body + "\n"
