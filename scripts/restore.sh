#!/usr/bin/env bash
# Roll back Stitches to a previous backup snapshot (code + .env + MongoDB).
# Used by Admin -> Updates -> Restore. Self-hosted only.
#
# Environment:
#   STAMP       - backup folder name to restore (required)
#   APP_DIR     - application root (default /app)
#   BACKUP_DIR  - backups root (default $APP_DIR/backups)
set -euo pipefail

APP_DIR="${APP_DIR:-/app}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
STAMP="${STAMP:?STAMP is required}"
SNAP="$BACKUP_DIR/$STAMP"

cd "$APP_DIR"
[ -d "$SNAP" ] || { echo "Backup $STAMP not found"; exit 1; }

echo "==> Restoring from backup $STAMP"

# Read manifest
PRE_SHA=""
HAS_DB="false"
if [ -f "$SNAP/manifest.json" ]; then
  PRE_SHA="$(grep -oE '"pre_sha":"[^"]*"' "$SNAP/manifest.json" | cut -d'"' -f4)"
  HAS_DB="$(grep -oE '"has_db":(true|false)' "$SNAP/manifest.json" | cut -d: -f2)"
fi

# 1) Roll back code
if [ -n "$PRE_SHA" ]; then
  echo "==> Rolling code back to $PRE_SHA"
  git reset --hard "$PRE_SHA"
else
  echo "==> No pre_sha recorded — skipping code rollback"
fi

# 2) Restore .env files
echo "==> Restoring .env files"
for ENVF in backend/.env frontend/.env .env; do
  if [ -f "$SNAP/$ENVF" ]; then
    cp "$SNAP/$ENVF" "$ENVF"
  fi
done

# 3) Restore MongoDB (destructive: --drop) if a dump exists
if [ "$HAS_DB" = "true" ] && [ -d "$SNAP/db" ] && command -v mongorestore >/dev/null 2>&1; then
  MONGO_URL="$(grep -E '^MONGO_URL=' backend/.env | cut -d= -f2- | tr -d '"')" || true
  if [ -n "${MONGO_URL:-}" ]; then
    echo "==> Restoring MongoDB (drop + restore)"
    mongorestore --uri="$MONGO_URL" --drop "$SNAP/db" >/dev/null 2>&1 || echo "    (mongorestore failed — continuing)"
  fi
else
  echo "==> No DB snapshot to restore (or mongorestore unavailable)"
fi

# 4) Rebuild + restart
echo "==> Installing backend dependencies"
pip install -r backend/requirements.txt
echo "==> Building frontend"
cd frontend
if command -v yarn >/dev/null 2>&1; then
  yarn install --frozen-lockfile || yarn install
  yarn build
else
  npm ci || npm install
  npm run build
fi
cd "$APP_DIR"

echo "==> Restarting services"
if command -v supervisorctl >/dev/null 2>&1; then
  sudo supervisorctl restart backend frontend || supervisorctl restart backend frontend || true
fi

echo "==> Restore complete from $STAMP"
