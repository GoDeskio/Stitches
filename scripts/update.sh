#!/usr/bin/env bash
# Self-hosted auto-update script for Stitches.
# Pulls the latest code from the configured GitHub repo, installs deps,
# rebuilds the frontend and restarts services via supervisor.
#
# DATA SAFETY GUARANTEE:
#   * MongoDB data (all users/admin/site data) lives in a SEPARATE service and is
#     NEVER touched by this script.
#   * .env files (secrets, DB connection, API keys) are git-ignored and are also
#     explicitly backed up and restored around the code update.
#   * Uploaded files use external object storage, untouched by code updates.
#   * We use `git reset --hard` for code ONLY and NEVER run `git clean`, so any
#     untracked local files you keep are preserved.
#   * A best-effort MongoDB dump + a restore manifest are written before every
#     update so it can be rolled back from the Admin -> Updates tab.
#
# Environment (provided by the backend updater, or set manually):
#   REPO_URL, BRANCH, REPO_TOKEN, APP_DIR (default /app), BACKUP_DIR (default $APP_DIR/backups)
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
BRANCH="${BRANCH:-main}"
REPO_URL="${REPO_URL:-https://github.com/GoDeskio/Stitches.git}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
HAS_DB=false

cd "$APP_DIR"
mkdir -p "$BACKUP_DIR/$STAMP"

echo "==> Preparing update ($REPO_URL @ $BRANCH)"

# Record the current commit so we can roll back
PRE_SHA="$(git rev-parse HEAD 2>/dev/null || echo '')"

# 1) Preserve environment/config files
echo "==> Backing up .env files"
for ENVF in backend/.env frontend/.env .env; do
  if [ -f "$ENVF" ]; then
    mkdir -p "$BACKUP_DIR/$STAMP/$(dirname "$ENVF")"
    cp "$ENVF" "$BACKUP_DIR/$STAMP/$ENVF"
  fi
done

# 2) Best-effort MongoDB backup (skips silently if mongodump is unavailable)
if command -v mongodump >/dev/null 2>&1 && [ -f backend/.env ]; then
  MONGO_URL="$(grep -E '^MONGO_URL=' backend/.env | cut -d= -f2- | tr -d '"')" || true
  DB_NAME="$(grep -E '^DB_NAME=' backend/.env | cut -d= -f2- | tr -d '"')" || true
  if [ -n "${MONGO_URL:-}" ]; then
    echo "==> Backing up MongoDB to $BACKUP_DIR/$STAMP/db"
    if mongodump --uri="$MONGO_URL" ${DB_NAME:+--db="$DB_NAME"} --out="$BACKUP_DIR/$STAMP/db" >/dev/null 2>&1; then
      HAS_DB=true
    else
      echo "    (mongodump skipped/failed — continuing)"
    fi
  fi
else
  echo "==> mongodump not available — skipping DB snapshot"
fi

# 3) Write restore manifest
cat > "$BACKUP_DIR/$STAMP/manifest.json" <<JSON
{"stamp":"$STAMP","created_at":"$(date -u +%FT%TZ)","pre_sha":"$PRE_SHA","branch":"$BRANCH","repo":"$REPO_URL","has_db":$HAS_DB}
JSON

# 4) Update the code (code only — no git clean, so untracked data is preserved)
PUSH_URL="$REPO_URL"
if [ -n "${REPO_TOKEN:-}" ]; then
  PUSH_URL="$(echo "$REPO_URL" | sed -E "s#https://#https://${REPO_TOKEN}@#")"
fi
if [ ! -d .git ]; then
  echo "==> No git repo found — initialising"
  git init
  git remote add origin "$PUSH_URL"
else
  git remote set-url origin "$PUSH_URL"
fi
echo "==> Fetching latest"
git fetch origin "$BRANCH"
echo "==> Resetting code to origin/$BRANCH (data & .env untouched)"
git reset --hard "origin/$BRANCH"
git remote set-url origin "$REPO_URL" || true

# 5) Restore preserved .env files (local config always wins)
echo "==> Restoring .env files"
for ENVF in backend/.env frontend/.env .env; do
  if [ -f "$BACKUP_DIR/$STAMP/$ENVF" ]; then
    cp "$BACKUP_DIR/$STAMP/$ENVF" "$ENVF"
  fi
done

# 6) Dependencies + build
echo "==> Installing backend dependencies"
pip install -r backend/requirements.txt
echo "==> Installing frontend dependencies & building"
cd frontend
if command -v yarn >/dev/null 2>&1; then
  yarn install --frozen-lockfile || yarn install
  yarn build
else
  npm ci || npm install
  npm run build
fi
cd "$APP_DIR"

# 7) Restart services
echo "==> Restarting services"
if command -v supervisorctl >/dev/null 2>&1; then
  sudo supervisorctl restart backend frontend || supervisorctl restart backend frontend || true
fi

echo "==> Done. Backup + rollback point saved at $BACKUP_DIR/$STAMP"
