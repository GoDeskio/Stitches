#!/usr/bin/env bash
# One-shot self-host installer for Stitches on a fresh Ubuntu/Debian VM.
# Sets up the app so the in-app Software Update Center (Admin -> Updates) can
# auto-pull from GitHub, rebuild, restart, health-check and auto-rollback.
#
# Run as root (or with sudo):  sudo bash deploy/self-host/install.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/stitches}"
REPO_URL="${REPO_URL:-https://github.com/GoDeskio/Stitches.git}"
BRANCH="${BRANCH:-main}"
DOMAIN="${DOMAIN:-_}"                       # e.g. stitches.example.com (or _ for any)
SITE_URL="${SITE_URL:-http://localhost}"    # public URL the browser uses; baked into the frontend

echo "==> Installing prerequisites"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git curl build-essential python3 python3-venv python3-pip nginx supervisor gnupg
# Node 20 + yarn
if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y nodejs
fi
command -v yarn >/dev/null 2>&1 || npm install -g yarn
# MongoDB (community) — skip if you point MONGO_URL at an existing/managed cluster
if ! command -v mongod >/dev/null 2>&1 && [ "${INSTALL_MONGO:-true}" = "true" ]; then
  curl -fsSL https://pgp.mongodb.com/server-7.0.asc | gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
  echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" > /etc/apt/sources.list.d/mongodb-org-7.0.list
  apt-get update -y && apt-get install -y mongodb-org
  systemctl enable --now mongod
fi
# mongodump/mongorestore (for update snapshots/rollback)
apt-get install -y mongodb-database-tools || true

echo "==> Fetching the app into $APP_DIR"
mkdir -p "$APP_DIR"
if [ ! -d "$APP_DIR/.git" ]; then
  git clone -b "$BRANCH" "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch origin "$BRANCH" && git -C "$APP_DIR" reset --hard "origin/$BRANCH"
fi
cd "$APP_DIR"

echo "==> Writing environment files (edit these with real secrets!)"
if [ ! -f backend/.env ]; then
  cp deploy/self-host/.env.backend.example backend/.env
  echo "  -> created backend/.env from template — EDIT IT before going live"
fi
# Frontend must know the public URL at build time.
grep -q "^REACT_APP_BACKEND_URL=" frontend/.env 2>/dev/null || echo "REACT_APP_BACKEND_URL=$SITE_URL" > frontend/.env

echo "==> Python venv + backend deps"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r backend/requirements.txt

echo "==> Building frontend (lint warnings won't fail the build)"
( cd frontend && CI=false DISABLE_ESLINT_PLUGIN=true yarn install && CI=false DISABLE_ESLINT_PLUGIN=true yarn build )

echo "==> Installing supervisor + nginx configs"
mkdir -p /var/log/stitches
sed "s#{{APP_DIR}}#$APP_DIR#g" deploy/self-host/supervisor-stitches.conf > /etc/supervisor/conf.d/stitches.conf
sed -e "s#{{APP_DIR}}#$APP_DIR#g" -e "s#{{DOMAIN}}#$DOMAIN#g" deploy/self-host/nginx-stitches.conf > /etc/nginx/sites-available/stitches.conf
ln -sf /etc/nginx/sites-available/stitches.conf /etc/nginx/sites-enabled/stitches.conf
rm -f /etc/nginx/sites-enabled/default || true

echo "==> Starting services"
supervisorctl reread && supervisorctl update && supervisorctl restart backend || supervisorctl start backend
nginx -t && systemctl reload nginx

echo ""
echo "==> Stitches is installed at $APP_DIR"
echo "    1) Edit backend/.env (set SELF_HOSTED=true, MONGO_URL, JWT_SECRET, ADMIN_*, ENCRYPTION_KEY, EMERGENT_LLM_KEY)."
echo "    2) Re-run: sudo supervisorctl restart backend"
echo "    3) Open $SITE_URL and log in. In Admin -> Updates, set your repo + token and enable auto-apply + auto-rollback."
echo "    Auto-updates now run on this box: pull -> rebuild -> restart -> health-check -> auto-rollback on failure."
