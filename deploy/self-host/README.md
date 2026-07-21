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

## Prefer containers?

`deploy/docker-compose.yml` runs the optional **LiveKit SFU + coturn TURN** for large
meetings. For a fully containerized app you can build images from `backend/` and `frontend/`
and reverse-proxy with the nginx config here; note that container deploys typically update by
rebuilding images rather than via `update.sh`.
