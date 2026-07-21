# Self-hosting Stitches (with real auto-updates)

Run Stitches on your own Ubuntu/Debian server. Once installed, the in-app
**Software Update Center** (Admin → Updates) pulls new code from GitHub, rebuilds,
restarts, health-checks, and **auto-rolls-back** if an update breaks the site.

## Quick install

```bash
sudo APP_DIR=/opt/stitches \
     REPO_URL=https://github.com/GoDeskio/Stitches.git \
     SITE_URL=https://stitches.yourdomain.com \
     DOMAIN=stitches.yourdomain.com \
     bash deploy/self-host/install.sh
```

The installer sets up Node 20 + yarn, Python venv, MongoDB, nginx and supervisor;
builds the frontend; and wires services named `backend`/`frontend` (matching
`scripts/update.sh`).

## After install

1. Edit `/opt/stitches/backend/.env` (copied from `.env.backend.example`) — set
   `SELF_HOSTED=true`, `MONGO_URL`, `JWT_SECRET`, `ADMIN_EMAIL/PASSWORD`,
   `ENCRYPTION_KEY`, `EMERGENT_LLM_KEY`, and your public `FRONTEND_URL`/`CORS_ORIGINS`.
   Generate a Fernet key: `python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
2. `sudo supervisorctl restart backend`
3. HTTPS: `sudo certbot --nginx -d stitches.yourdomain.com`
4. Log in as the admin, go to **Admin → Updates**, set your GitHub repo + a
   fine-grained access token, and enable **Auto-apply** + **Auto-rollback**.

## How auto-update works on your box

`Admin → Updates → Apply` (or the auto-apply scanner) runs `scripts/update.sh`, which:
backs up `.env` + a MongoDB dump → `git reset --hard origin/<branch>` (code only, your
data is never touched) → reinstalls deps → `yarn build` (lint warnings can't fail it) →
restarts services → polls `/api/health` → and, if unhealthy with auto-rollback on, runs
`scripts/restore.sh` to restore the previous snapshot (code + .env + database).

> Data safety: MongoDB and uploaded files (object storage) are separate from code and are
> preserved across updates; a snapshot is taken before every update for one-click rollback.

## Prefer containers? (full-app Docker Compose)

Run the whole stack (MongoDB + backend + nginx/SPA) with one command — from the repo root:

```bash
cp deploy/self-host/.env.backend.example backend/.env   # edit secrets
export SITE_URL=https://stitches.yourdomain.com          # public URL, baked into the SPA
docker compose -f deploy/self-host/docker-compose.yml up -d --build
```

Put TLS in front of port 80 (reverse proxy, Cloudflare tunnel, or host certbot). Data persists
in the `mongo_data` volume. **Update by rebuilding**: `git pull && docker compose -f
deploy/self-host/docker-compose.yml up -d --build`. (The in-app Software Update Center —
`scripts/update.sh` — targets the VM install above, which supports fully in-app auto-update
with health-check + auto-rollback.)

`deploy/docker-compose.yml` additionally runs the optional **LiveKit SFU + coturn TURN** for
large meetings.

## Zero-build path: prebuilt images + automatic HTTPS (recommended for containers)

Push a `v*` tag (or land on `main`) and the **`.github/workflows/docker-images.yml`** workflow
builds & publishes `stitches-backend` and `stitches-frontend` images to GHCR. Your server then
just pulls them — no local build — and **Caddy handles TLS automatically**:

```bash
cp deploy/self-host/.env.backend.example backend/.env       # edit secrets
export GHCR_OWNER=godeskio                                   # your GitHub org/user (lowercase)
export SITE_DOMAIN=stitches.yourdomain.com                   # DNS A record must point here
docker compose -f deploy/self-host/docker-compose.ghcr.yml pull
docker compose -f deploy/self-host/docker-compose.ghcr.yml up -d
```

Open ports **80 + 443**; Caddy fetches and renews a Let's Encrypt certificate for
`SITE_DOMAIN` on its own. The frontend image is domain-agnostic (it calls the API on the same
origin), so the same image works behind any domain. Make the GHCR packages public, or run
`docker login ghcr.io` on the server first.

**Hands-off auto-update (containers):** the GHCR compose includes a **Watchtower** service that
polls GHCR every `WATCHTOWER_POLL_INTERVAL` seconds (default 300) and automatically redeploys
`backend`/`web` when a newer `:latest` image is published — so once you push a `v*` tag, your
server updates itself with no manual `pull`. For private packages, mount your docker creds into
the Watchtower service (see the commented volume in the compose file).
