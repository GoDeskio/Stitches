#!/usr/bin/env bash
# Self-hosted auto-update script for Stitches (self-healing).
# Pulls the latest code from the configured GitHub repo, installs deps,
# rebuilds the frontend, restarts services, then runs a post-update HEALTH
# CHECK. If the site is unhealthy and AUTO_ROLLBACK=true, it automatically
# restores the pre-update snapshot (code + .env + database).
#
# DATA SAFETY GUARANTEE:
#   * MongoDB data (all users/admin/site data) lives in a SEPARATE service and is
#     NEVER touched by the code update. A best-effort dump is taken first so it can
#     be rolled back.
#   * .env files (secrets, DB connection, API keys) are git-ignored and are also
#     explicitly backed up and restored around the code update.
#   * Uploaded files use external object storage, untouched by code updates.
#   * We use `git reset --hard` for code ONLY and NEVER run `git clean`, so any
#     untracked local files you keep are preserved.
#
# Environment (provided by the backend updater, or set manually):
#   REPO_URL, BRANCH, REPO_TOKEN, APP_DIR (default /app),
#   BACKUP_DIR (default $APP_DIR/backups), STAMP (backend-provided folder name),
#   HEALTH_URL (default http://localhost:8001/api/health), AUTO_ROLLBACK (true|false)
set -uo pipefail

APP_DIR="${APP_DIR:-/app}"
BRANCH="${BRANCH:-main}"
REPO_URL="${REPO_URL:-https://github.com/GoDeskio/Stitches.git}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
# Respect the STAMP handed to us by the backend so it can find our logs/result.
STAMP="${STAMP:-$(date +%Y%m%d_%H%M%S)}"
HEALTH_URL="${HEALTH_URL:-http://localhost:8001/api/health}"
AUTO_ROLLBACK="${AUTO_ROLLBACK:-false}"
RESTORE_SCRIPT="$APP_DIR/scripts/restore.sh"
SNAP="$BACKUP_DIR/$STAMP"
HAS_DB=false

mkdir -p "$SNAP"
# Mirror everything to the update log the Admin UI streams.
exec > >(tee -a "$SNAP/update.log") 2>&1

cd "$APP_DIR" || { echo "==> APP_DIR $APP_DIR missing"; exit 1; }

write_result() {  # $1=status  $2=rolled_back(true|false)
  cat > "$SNAP/result.json" <<JSON
{"status":"$1","rolled_back":$2,"finished_at":"$(date -u +%FT%TZ)"}
JSON
}

fail_and_maybe_rollback() {
  echo "==> Update FAILED: $1"
  if [ "$AUTO_ROLLBACK" = "true" ] && [ -f "$RESTORE_SCRIPT" ]; then
    echo "==> Auto-rollback enabled — restoring snapshot $STAMP"
    if STAMP="$STAMP" APP_DIR="$APP_DIR" BACKUP_DIR="$BACKUP_DIR" bash "$RESTORE_SCRIPT"; then
      echo "==> Auto-rollback complete — site restored to last working version"
    else
      echo "==> Auto-rollback script reported errors"
    fi
    write_result "rolled_back" true
  else
    echo "==> Auto-rollback disabled — leaving current state for manual review"
    write_result "failed" false
  fi
  exit 1
}

echo "==> Preparing update ($REPO_URL @ $BRANCH)"

# Record the current commit so we can roll back.
PRE_SHA="$(git rev-parse HEAD 2>/dev/null || echo '')"

# 1) Preserve environment/config files
echo "==> Backing up .env files"
for ENVF in backend/.env frontend/.env .env; do
  if [ -f "$ENVF" ]; then
    mkdir -p "$SNAP/$(dirname "$ENVF")"
    cp "$ENVF" "$SNAP/$ENVF"
  fi
done

# 2) Best-effort MongoDB backup (skips silently if mongodump is unavailable)
if command -v mongodump >/dev/null 2>&1 && [ -f backend/.env ]; then
  MONGO_URL="$(grep -E '^MONGO_URL=' backend/.env | cut -d= -f2- | tr -d '"')" || true
  DB_NAME="$(grep -E '^DB_NAME=' backend/.env | cut -d= -f2- | tr -d '"')" || true
  if [ -n "${MONGO_URL:-}" ]; then
    echo "==> Backing up MongoDB to $SNAP/db"
    if mongodump --uri="$MONGO_URL" ${DB_NAME:+--db="$DB_NAME"} --out="$SNAP/db" >/dev/null 2>&1; then
      HAS_DB=true
    else
      echo "    (mongodump skipped/failed — continuing)"
    fi
  fi
else
  echo "==> mongodump not available — skipping DB snapshot"
fi

# 3) Write restore manifest
cat > "$SNAP/manifest.json" <<JSON
{"stamp":"$STAMP","created_at":"$(date -u +%FT%TZ)","pre_sha":"$PRE_SHA","branch":"$BRANCH","repo":"$REPO_URL","has_db":$HAS_DB}
JSON

# 4) Update the code (code only — no git clean, so untracked data is preserved)
PUSH_URL="$REPO_URL"
if [ -n "${REPO_TOKEN:-}" ]; then
  PUSH_URL="$(echo "$REPO_URL" | sed -E "s#https://#https://${REPO_TOKEN}@#")"
fi
if [ ! -d .git ]; then
  echo "==> No git repo found — initialising"
  git init && git remote add origin "$PUSH_URL" || fail_and_maybe_rollback "git init failed"
else
  git remote set-url origin "$PUSH_URL" || true
fi
echo "==> Fetching latest"
git fetch origin "$BRANCH" || fail_and_maybe_rollback "git fetch failed"
echo "==> Resetting code to origin/$BRANCH (data & .env untouched)"
git reset --hard "origin/$BRANCH" || fail_and_maybe_rollback "git reset failed"
git remote set-url origin "$REPO_URL" || true

# 5) Restore preserved .env files (local config always wins)
echo "==> Restoring .env files"
for ENVF in backend/.env frontend/.env .env; do
  if [ -f "$SNAP/$ENVF" ]; then
    cp "$SNAP/$ENVF" "$ENVF"
  fi
done

# 6) Dependencies + build
echo "==> Installing backend dependencies"
pip install -r backend/requirements.txt || fail_and_maybe_rollback "backend dependency install failed"
echo "==> Installing frontend dependencies & building"
cd frontend || fail_and_maybe_rollback "frontend directory missing"
if command -v yarn >/dev/null 2>&1; then
  (yarn install --frozen-lockfile || yarn install) || fail_and_maybe_rollback "yarn install failed"
  yarn build || fail_and_maybe_rollback "frontend build failed"
else
  (npm ci || npm install) || fail_and_maybe_rollback "npm install failed"
  npm run build || fail_and_maybe_rollback "frontend build failed"
fi
cd "$APP_DIR"

# 7) Restart services
echo "==> Restarting services"
if command -v supervisorctl >/dev/null 2>&1; then
  sudo supervisorctl restart backend frontend || supervisorctl restart backend frontend || true
fi

# 8) Post-update HEALTH CHECK (self-healing gate)
echo "==> Waiting for the site to come back up, then health-checking $HEALTH_URL"
HEALTHY=false
for i in $(seq 1 30); do
  sleep 2
  if command -v curl >/dev/null 2>&1; then
    CODE="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$HEALTH_URL" || echo 000)"
  elif command -v wget >/dev/null 2>&1; then
    CODE="$(wget -q -O /dev/null -T 5 "$HEALTH_URL" && echo 200 || echo 000)"
  else
    CODE="$(python3 -c "import urllib.request; print(urllib.request.urlopen('$HEALTH_URL', timeout=5).getcode())" 2>/dev/null || echo 000)"
  fi
  if [ "$CODE" = "200" ]; then
    echo "    health OK ($CODE) on attempt $i"
    HEALTHY=true
    break
  fi
  echo "    not healthy yet ($CODE) — attempt $i/30"
done

if [ "$HEALTHY" != "true" ]; then
  fail_and_maybe_rollback "post-update health check did not pass (site did not return 200)"
fi

echo "==> Update applied successfully and site is healthy ✔"
echo "==> Backup + rollback point saved at $SNAP"
write_result "success" false
