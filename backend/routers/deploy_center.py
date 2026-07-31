import io
import zipfile
import secrets as pysecrets
from fastapi import APIRouter
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
        new_alerts = 0
        broke = []
        for c in report["checks"]:
            was = prev.get(c["id"], "ok")
            if _RANK.get(c["status"], 0) > _RANK.get(was, 0):  # regressed
                # Throttle: skip if we alerted on this check within the cooldown window
                recent = await db.diagnostics_alerts.find_one({"check_id": c["id"], "created_at": {"$gte": cooldown_cut}})
                if recent:
                    continue
                await db.diagnostics_alerts.insert_one({
                    "alert_id": f"dga_{uuid.uuid4().hex[:10]}", "check_id": c["id"], "label": c["label"],
                    "from_status": was, "to_status": c["status"], "detail": c["detail"],
                    "fix_hint": c.get("fix_hint", ""), "created_at": now_iso(), "seen": False})
                broke.append(f"{c['label']} ({c['status']})")
                new_alerts += 1
        if broke:
            await _dispatch_alerts(broke)
        return new_alerts
    except Exception as e:
        logger.error(f"auto diagnostics error: {e}")
        return 0


async def _dispatch_alerts(broke):
    """Send a health-regression alert to every configured channel (email + Slack + webhook)."""
    text = "Stitches health alert — these checks newly regressed: " + ", ".join(broke)
    # Email admins
    try:
        from services.email import send_email_detailed
        admins = await db.users.find({"role": {"$in": ["admin", "super_admin"]}}, {"email": 1}).to_list(50)
        html = "<h3>Stitches health alert</h3><p>These checks newly regressed:</p><ul>" + "".join(f"<li>{b}</li>" for b in broke) + "</ul>"
        for a in admins:
            if a.get("email"):
                await send_email_detailed(a["email"], "Stitches: something newly broke", html)
    except Exception as e:
        logger.warning(f"diag alert email failed: {e}")
    # Slack + generic webhook
    ch = ((await db.settings.find_one({"key": "alert_channels"})) or {}).get("value", {})
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        if ch.get("slack_webhook"):
            try:
                await client.post(ch["slack_webhook"], json={"text": ":rotating_light: " + text})
            except Exception as e:
                logger.warning(f"slack alert failed: {e}")
        if ch.get("webhook_url"):
            try:
                await client.post(ch["webhook_url"], json={"event": "stitches.health.regression", "message": text, "checks": broke})
            except Exception as e:
                logger.warning(f"webhook alert failed: {e}")


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


@router.get("/admin/deploy/alert-channels")
async def get_alert_channels(user: dict = Depends(require_admin)):
    ch = ((await db.settings.find_one({"key": "alert_channels"})) or {}).get("value", {})
    return {"slack_webhook": ch.get("slack_webhook", ""), "webhook_url": ch.get("webhook_url", "")}


@router.put("/admin/deploy/alert-channels")
async def set_alert_channels(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    val = {"slack_webhook": (body.get("slack_webhook") or "").strip(),
           "webhook_url": (body.get("webhook_url") or "").strip()}
    await db.settings.update_one({"key": "alert_channels"},
                                 {"$set": {"key": "alert_channels", "value": val}}, upsert=True)
    return {"ok": True, **val}


@router.post("/admin/deploy/alert-channels/test")
async def test_alert_channels(user: dict = Depends(require_admin)):
    await _dispatch_alerts(["Test alert — this is a sample health regression"])
    ch = ((await db.settings.find_one({"key": "alert_channels"})) or {}).get("value", {})
    return {"ok": True, "sent_to": {"email": True, "slack": bool(ch.get("slack_webhook")), "webhook": bool(ch.get("webhook_url"))}}





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
