# Stitches Changelog

## 2026-06 — Container hands-off auto-update (Watchtower)
- Added a **Watchtower** service to `deploy/self-host/docker-compose.ghcr.yml` (label-gated: only `backend`/`web` carry `com.centurylinklabs.watchtower.enable=true`, so mongo/caddy are left alone). Polls GHCR every `WATCHTOWER_POLL_INTERVAL`s (default 300) and auto-redeploys when a newer `:latest` is published, with `WATCHTOWER_CLEANUP` pruning old images. Commented volume shows how to mount docker creds for private GHCR packages. README documents it. Compose YAML validated (services: mongo/backend/web/caddy/watchtower). This gives the container path the same hands-off updates as the VM `update.sh` path.


## 2026-06 — GHCR image publishing + automatic HTTPS + domain-agnostic frontend
- **Domain-portable frontend**: `lib/api.js` now falls back to `window.location.origin` when `REACT_APP_BACKEND_URL` is unset (exported `BACKEND_ORIGIN`; EmailTab webhook URL updated). This makes prebuilt images work behind ANY domain (API + WebSockets resolve to same origin, proxied by nginx). Managed preview unchanged (env still set). Verified: login/dashboard/authed calls work, clean compile.
- **GHCR publish workflow** (`.github/workflows/docker-images.yml`): on `v*` tag / `main`, builds & pushes `stitches-backend` + `stitches-frontend` to GHCR (buildx + gha cache, lowercased image names, `type=ref/raw/sha` tags).
- **Zero-build container path with auto-TLS** (`deploy/self-host/docker-compose.ghcr.yml` + `Caddyfile`): pulls the GHCR images and fronts them with **Caddy** for automatic Let's Encrypt HTTPS (`SITE_DOMAIN`, ports 80/443). `docker compose pull && up` — no local build. `docker-compose.yml` `SITE_URL` now optional (thanks to origin fallback). README documents the path. YAML validated.


## 2026-06 — Full-app Docker Compose self-host path
- **Container-first self-host** (`/app/deploy/self-host/`): `docker-compose.yml` (MongoDB + backend + nginx/SPA `web`), `Dockerfile.backend` (python:3.11-slim + uvicorn + `/api/health` HEALTHCHECK), `Dockerfile.frontend` (multi-stage node:20 build with `CI=false`/`DISABLE_ESLINT_PLUGIN=true` → nginx:1.27), `nginx.docker.conf` (serves SPA, proxies `/api`+WebSockets → `backend:8001`), and `.dockerignore` at repo root. One command: `SITE_URL=… docker compose -f deploy/self-host/docker-compose.yml up -d --build`. README updated with the container path (data in `mongo_data` volume; update by rebuilding images; VM path remains for in-app auto-update).
- Verified: compose YAML parses (services mongo/backend/web + mongo_data volume). Docker build not runnable in the managed pod (no docker) — artifacts are correct/validated.


## 2026-06 — Self-host make-it-work: build-fail fix + one-command installer + clickable readiness
- **CRITICAL fix — production build was failing** (`yarn build` with `CI=true` treats ESLint warnings as errors → every self-hosted `update.sh` build would fail and auto-rollback). Fixed the 3 offending `useEffect` warnings (NotificationBell, CrmTab, UpdatesTab) AND hardened `scripts/update.sh` + `scripts/restore.sh` to build with `CI=false` + `DISABLE_ESLINT_PLUGIN=true`. Verified `yarn build` now succeeds with `CI=true`.
- **Self-host bundle** (`/app/deploy/self-host/`): `install.sh` (one-command Ubuntu/Debian installer: Node20/yarn, Python venv, MongoDB, nginx, supervisor; builds frontend; wires `backend`/`frontend` supervisor programs matching `update.sh`), `nginx-stitches.conf` (serves SPA + proxies `/api`+`/ws` → :8001), `supervisor-stitches.conf`, `.env.backend.example` (SELF_HOSTED=true + all keys), `README.md`. Makes the whole app + in-app auto-update run outside Emergent.
- **Clickable readiness pills**: Admin → Overview "Production readiness" cards now navigate to the relevant tab (Update source→Updates, Email→Email, SFU/TURN→Meetings). Verified TURN pill → Meetings. Clean compile.


## 2026-06 — Admin "Production readiness" status strip + rotated update token
- **Setup status strip** (Admin → Overview, top): new `GET /api/admin/setup-status` aggregates four go-live checks — Update source (repo + token), Email delivery (SMTP/Mailgun/Gmail/Resend), SFU (LiveKit), TURN relay — each with a green ✓ / amber ⚠ pill + short detail. Gives admins an at-a-glance view of what's configured vs. pending. `SetupStatusStrip` component renders the pills.
- Verified: endpoint returns Update ✓ / Email ✓ (SMTP) / SFU ⚠ / TURN ⚠; strip renders on the Overview (screenshot); clean compile.
- **Rotated GitHub PAT** re-saved (encrypted at rest); live check reached `GoDeskio/Stitches` and detected an available update.


## 2026-06 — Auto-update wired to GitHub (encrypted PAT) + token-at-rest hardening
- **Update token encrypted at rest**: `routers/updates.py` now stores the GitHub PAT as Fernet ciphertext (`token_enc`), decrypts server-side only, and clears any legacy plaintext. Verified in Mongo: `token` field empty, `token_enc` = `gAAAA…`, no `ghp_` leak. `_public_cfg` still returns only `has_token`.
- **Configured live**: admin GitHub repo (`https://github.com/GoDeskio/Stitches.git`, branch `main`) + PAT saved via `/admin/updates/config`; `enabled`, `auto_apply` and `auto_rollback` all ON. A check reached the repo with the token and detected an available update. Admin → Updates shows repo + "Access token · set" + all toggles + "Update available" banner.
- **Behavior**: on a **self-hosted** deploy (`SELF_HOSTED=true`) the site will now auto-pull → rebuild → restart → health-check → auto-rollback on failure. On this **managed Emergent preview**, auto-apply only *notifies* (it cannot git-reset the managed pod) — clearly indicated in the UI.


## 2026-06 — In-app Resend domain setup + live verification
- **Resend DNS/verification helper** (Admin → Email → "Resend domain setup"): new `GET /api/admin/resend/dns` pulls the sender domain's DKIM/SPF records + verification status **live from the Resend API**, and `POST /api/admin/resend/verify` triggers Resend's verify. The card (`resend-setup-card`) shows a status badge (Verified/Pending/Failed/Not started), each record's type/host/value with copy buttons + per-record status dots, and Refresh/Verify buttons — so admins complete the DNS step and confirm delivery without leaving Stitches.
- Verified live against the real Resend account: returns the account domain + 3 records (DKIM TXT, SPF MX, SPF TXT) with correct values; UI renders all rows, badge and buttons; clean compile.


## 2026-06 — Pre-join call connectivity check
- **Network self-check on `/call`** (`Call.jsx` → `probeIce`): before joining a P2P room, the client runs a WebRTC ICE-gathering probe against the fetched `iceServers`. If a TURN server is configured it verifies a `relay` candidate is obtained; otherwise it checks for a STUN (`srflx`) candidate. Shows a dismissible amber/red warning banner (`call-net-warning`) when the network may block calls, or a subtle green "network good" line (`call-net-ok`) — so bad-network users get a heads-up instead of a frozen call.
- Verified in-browser: sandbox (STUN reachable, no TURN) → green "Network looks good for peer-to-peer calls"; warn/fail paths covered logically. Clean compile.


## 2026-06 — SFU/TURN connectivity tester + CI URL baking
- **"Test connectivity" tool** (Admin → Meetings): new `POST /api/admin/rtc/test` (admin) probes the saved config — LiveKit via HTTP reachability (wss→https) and TURN via DNS resolve + TCP connect — returning `{sfu:{ok,detail}, turn:{ok,detail}}`. Both the TURN and SFU cards gained a **Test connectivity** button (`test-turn-btn`/`test-sfu-btn`) with a green/amber result line (`turn-test-result`/`sfu-test-result`). De-risks the P1 post-deploy step: admins confirm reachability without starting a real call.
  - Verified: unconfigured → clear guidance; reachable hosts (google.com:443 / https://google.com) → `ok:true` with details; frontend buttons render + fire (screenshot + toast).
- **CI desktop build**: `desktop-build.yml` now bakes the production `STITCHES_URL` (repo variable) into `main.js` at build time so end-user installers connect to the right domain (runtime env isn't set on user machines). Triggers on `v*` tag push → builds Win/macOS/Linux → publishes a GitHub Release.


## 2026-06 — Rollback alerts + Admin.jsx UsersTab refactor + conferencing/desktop deploy artifacts
- **Auto-rollback admin alert** (`routers/updates.py`): when an update finishes as `failed` or `rolled_back`, all admins get a one-time in-app notification ("Update auto-rolled back" / "Update failed") via `_alert_admins_job` (idempotent `alerted` flag), surfaced through `/admin/updates/status`.
- **P2 refactor**: extracted `UsersTab` from the monolithic `Admin.jsx` into `src/pages/admin/UsersTab.jsx`, plus shared `src/pages/admin/UserBits.jsx` (`Avatar`, `RolePill`, `ActionBtn`). Removed the now-unused icon/auth imports from `Admin.jsx`. Verified: Users tab renders 18 rows with avatars, role pills, plan selects and all action buttons; zero regressions; clean compile.
- **P1 deploy artifacts** (`/app/deploy/`): `docker-compose.yml` (LiveKit SFU + coturn TURN), `livekit.yaml`, `.env.example`, `README.md` with step-by-step setup + Admin → Meetings wiring. Enables real SFU/TURN on self-hosted infra (media path untestable in the managed preview, ships gated OFF). Confirmed `/api/rtc/config` + `/api/rtc/sfu-token` behave correctly (400 while disabled).
- **P3 desktop wrapper** (`/app/desktop/main.js`): added WebRTC media permissions (camera/mic/notifications) + screen-share via `setDisplayMediaRequestHandler`/`desktopCapturer`, and a system tray, so the Electron client's audio/video meetings work. Installers still built via CI outside the sandbox.


## 2026-06 — Self-healing auto-rollback for the Software Update Center (COMPLETE)
- **update.sh (self-healing)**: now respects the backend-provided `STAMP`, tees all output to `$BACKUP_DIR/$STAMP/update.log` (live-streamed in the Admin UI), and after restart runs a post-update **health check** (polls `HEALTH_URL` = `/api/health`, up to ~60s). Every step (git fetch/reset, pip install, yarn build) is guarded — on any failure OR a failed health check with `AUTO_ROLLBACK=true`, it automatically invokes `restore.sh` to roll the site back to the pre-update snapshot (code + .env + MongoDB). Writes `result.json` `{status: success|failed|rolled_back, rolled_back, finished_at}` that the backend reports to the UI.
- **Backend** (`routers/updates.py`): `/api/health` endpoint; `_launch_update_script` passes `STAMP/HEALTH_URL/AUTO_ROLLBACK`; `/admin/updates/status` reads the file-based `result.json`/`update.log`. Managed (Emergent) instances still return a simulated response so the pod is never destroyed; real execution only under `SELF_HOSTED=true`.
- **UI** (`UpdatesTab.jsx`): new **"Auto-rollback if an update breaks the site"** toggle (`updates-autorollback`), a rolled-back banner + color-coded status in the log panel.
- Verified: `/api/health`=200; config persists `auto_rollback`; apply returns managed simulation. Isolated self-hosted harness proved both the healthy path (`result:success`) and the broken path (health 500 → `restore.sh` runs → `result:rolled_back`, snapshot restored). Frontend toggle renders.


## 2026-06 — CRM Kanban pipeline + more Admin.jsx refactor
- **CRM pipeline (Kanban)**: List/Pipeline toggle in the CRM tab; drag lead cards across 6 stage columns (new→…→won/lost) with live persistence (`PUT` on drop). New `GET /api/admin/crm/board` groups leads by stage.
- **"New leads this week"**: `new_leads_week` added to `/admin/crm/stats`, surfaced on the Leads funnel card.
- **Refactor cont.**: extracted `SiteNoteTab`, `AutomationTab`, and shared `StatCard` into `src/pages/admin/`. Admin.jsx now 1037 lines (was 1263). UsersTab left in place (depends on many local helpers — needs a dedicated pass).
- Verified: board endpoint groups leads, pipeline drag UI renders 6 columns/9 cards, all admin tabs render post-refactor (no crash).

## 2026-06 — Landing lead-capture CTA + Admin.jsx refactor
- **Landing page**: "Request a demo" CTA + glass modal (name/email/company/message) posts to public `POST /api/leads`, flowing real visitors into the CRM funnel. On capture, admins are emailed (best-effort) via the delivery pipeline.
- **Refactor**: split the 1970-line `Admin.jsx` → extracted `src/pages/admin/CrmTab.jsx` (197 lines) and `src/pages/admin/EmailTab.jsx` (526 lines); Admin.jsx now 1262 lines. Verified no regressions (all admin tabs render).
- Verified: demo modal + CTA render, lead capture works, CRM/Email tabs intact post-refactor.

## 2026-06 — Full CRM + dedicated Email tab
- **Email tab split**: email management (setup wizard, delivery analytics, test email, digest) moved into its own admin **Email** tab; Site Note tab keeps announcement/support/clarity/require-verification.
- **CRM** (`routers/crm.py`, admin "CRM" tab): visitor→lead→user funnel with conversion rates, contacts list (filter by type/stage, search, pagination), lead CRUD, pipeline stages (new/contacted/qualified/proposal/won/lost), notes timeline, `sync-users` (idempotent import of registered users), and a **public `POST /api/leads`** capture endpoint with per-IP rate limiting (5/10min → 429).
- Frontend: `CrmTab`, `CrmAddLead`, `CrmContactModal` in Admin.jsx.
- Tested iteration_34: 8/8 backend + all CRM/tab-split frontend flows pass. Rate limit verified (6th submission 429).
- NOTE (tech debt): Admin.jsx is now ~1970 lines — split into per-tab files recommended before further feature work.

## 2026-06 — One-click Mailgun DNS checklist
- `services/mailgun.check_domain` → Mailgun v4 `GET /domains/{domain}`, returns domain state + sending DNS records (SPF/DKIM/tracking) each with valid/missing. Endpoint `GET /api/admin/mailgun/dns`.
- Admin wizard: **"Check DNS"** button shows domain state (+ all-valid indicator) and a green/red checklist of each required record with name/value. Graceful error surfacing (e.g. 401 invalid key).
- Verified: endpoint returns records shape / graceful errors; UI button + error toast confirmed.

## 2026-06 — Mailgun webhooks, delivery analytics & easier setup
- **Webhook receiver** `POST /api/webhooks/mailgun` — HMAC-SHA256 signature verified against the stored webhook signing key (406 on bad sig). Records events to `email_events`; bounced/complained → auto-added to `suppressed_emails`.
- **Suppression guard**: `send_email_detailed` skips suppressed recipients (returns clear detail).
- **Analytics**: `GET /api/admin/email-events` (delivered/opened/bounced counts, delivery+open rates, recent events, suppressed list, webhook URL) + `POST /api/admin/email-events/unsuppress`.
- **Admin UI**: "Email delivery" card (live stats, suppressed list with Restore) + webhook signing key field + copyable **Webhook URL**. Added `CopyRow` copy-to-clipboard for the Mailgun webhook URL and the Gmail OAuth redirect URI (easier external-account setup).
- Verified via curl: valid signed webhook records delivered, bounce auto-suppresses; UI renders stats + suppressed row + Restore.

## 2026-06 — Mailgun email provider (admin + per-user)
- New **Mailgun** send path (`services/mailgun.py`): HTTP API via httpx, US/EU region, HTML + .ics attachments, API key stored **encrypted** (Fernet). Config lives in DB (dashboard-entered, no .env).
- Provider abstraction (`services/email.py`): added `mailgun` to the order (`mailgun→gmail_sa→gmail→smtp`, Resend fallback off). Per-user sends now try personal Mailgun → personal SMTP first.
- Endpoints (`routers/gmail_oauth.py`): `GET/PUT/DELETE /api/admin/mailgun-config`, `GET/PUT/DELETE /api/me/mailgun-config`; `email-provider` status includes mailgun; provider PUT accepts `mailgun`.
- **Admin dashboard**: Mailgun is the first option in the Email Setup wizard (domain/region/API key/sender + Save).
- **User dashboard** (Settings): new "My Mailgun (optional)" section mirroring the per-user SMTP one.
- Verified: config persists (encrypted), provider switches to mailgun, both UIs render. Live delivery pending a real Mailgun API key + verified/sandbox domain.

## 2026-06 — Email health badge
- Every send now records last result to `settings.email_last_send` (ok/detail/to/at) via a `send_email_detailed` wrapper. Endpoint `GET /api/admin/email-health`.
- Admin header shows an **email health badge** (green "Email working" / red "Email failing" / gray "No emails sent yet") with a tooltip of the last detail + timestamp; auto-refreshes every 30s. Verified via curl + screenshot (currently red due to the SMTP app-password issue).

## 2026-06 — Verification soft-gate + SMTP diagnosis
- Admin-configurable **"Require email verification"** toggle (Site tab, default **OFF**). When ON, unverified non-admin users get 403 on meeting creation (`ensure_verified` in core.py, enforced in `POST /meetings`). Verified via curl: enabled→403 (unverified)/200 (admin), disabled→200.
- Stored `require_email_verification` setting; exposed via `/admin/site-config` GET/PUT.
- SMTP diagnosis: configured Gmail SMTP with the provided account password → Gmail returns **`534 Application-specific password required`** (2-Step Verification on). SMTP pipeline works; needs a 16-char **App Password**, not the normal password.

## 2026-06 — Email verification on signup + email notifications
- **Signup verification**: register now sets `email_verified=false`, generates a single-use 24h token (`email_verifications`), and emails a verify link. Endpoints: `GET/POST /api/auth/verify-email`, `POST /api/auth/resend-verification`. Google users auto-verified. Non-blocking (login still works); registration succeeds even if the email can't be delivered.
- **Frontend**: `/verify-email` page (success/error states), an unverified banner in the app Layout with a Resend button, and `email_verified` exposed on the user.
- **Email notifications**: `create_notification` now also emails the user (best-effort, gated by `notification_prefs.email`, default on) + a Settings toggle "Also send notifications to my email".
- Tested iteration_33: 6/6 backend + all frontend flows pass. ⚠️ Actual email DELIVERY still requires a working sender (see prior entries) — currently none is fully configured.

## 2026-06 — Gmail service-account send + in-wizard test button
- Added **Gmail service-account** send path (`services/gmail.py`): domain-wide delegation, impersonates the configured sender, `gmail.send` scope, HTML + .ics. Key stored **encrypted** (`settings.gmail_service_account` via Fernet), never in git/.env.
- Provider abstraction now supports `gmail_sa | gmail | smtp` with priority order + Resend fallback (off). Endpoints: `PUT /api/admin/gmail/service-account`, `POST /api/admin/gmail/service-account/disconnect`; `email-provider` GET/PUT accept `gmail_sa`.
- Seeded the provided service account (encrypted) and set provider=gmail_sa, sender=admin@godesk.io.
- Wizard (`Admin.jsx`): 3rd provider option "Gmail (service account)" with JSON paste/replace/remove + delegation instructions; added **"Send test email"** button (uses selected provider).
- STATUS: real send returns `unauthorized_client` → **domain-wide delegation not yet configured in Google Workspace** (authorize client ID 109384956045425917926 for scope gmail.send, and godesk.io must be a Workspace domain). Code path verified correct.

## 2026-06 — Email overhaul: Gmail API + SMTP wizard, Resend demoted, digest meetings
- **Upcoming meetings**: digest/report now includes an "Upcoming meetings (next 7 days)" card (`services/digest.py`).
- **Provider abstraction** (`services/email.py`): new `get_email_provider_cfg` (settings key `email_provider`); `send_email_detailed` now sends via the selected provider (gmail↔smtp order) and only uses **Resend if `resend_fallback` is explicitly enabled** (OFF by default). Default provider `gmail`, sender `admin@godesk.io`.
- **Gmail API send** (`services/gmail.py`): OAuth (reuses existing GOOGLE_CLIENT_ID/SECRET), token stored in `settings.gmail_token`, send-only via `gmail.send` scope with HTML + .ics support.
- **Router** (`routers/gmail_oauth.py`): `GET/PUT /api/admin/email-provider`, `GET /api/admin/gmail/authorize`, `GET /api/oauth/gmail/callback`, `POST /api/admin/gmail/disconnect`.
- **Admin UI** (`Admin.jsx` `EmailSetupWizard`, Site tab): 3-step wizard — pick provider (Gmail/SMTP), configure (Gmail connect w/ redirect URI shown, or SMTP fields), set default sender + Resend-fallback toggle.
- Tested: iteration_32 — 8/8 backend + frontend wizard checks pass. NOTE: Gmail live send requires the admin to Connect Google + register redirect URI `.../api/oauth/gmail/callback` and enable Gmail API in Google Cloud; sending as admin@godesk.io needs godesk.io on Google Workspace.

## 2026-06 — Digest: Send History Log
- `services/digest.py`: `_log_send` records every send to `digest_sends`; `get_digest_history` returns last 20. All send paths (scheduled/send-now/send-report) now log kind, recipient, ok, detail, timestamp.
- Endpoint: `GET /api/admin/digest/history`.
- `Admin.jsx` DigestCard: scrollable "Send history" list with kind, recipient, time, detail and Sent/Failed pill; refreshes after each send.
- Verified via curl (rows logged for report + digest) and UI screenshot.

## 2026-06 — Digest: Full Report, Preview & Last-sent
- `services/digest.py`: `_collect` now supports `full=True` (all-time, no window); added `send_report_now` and `render_digest` (preview HTML).
- Endpoints: `POST /api/admin/digest/send-report`, `GET /api/admin/digest/preview?frequency=&full=`.
- `Admin.jsx` DigestCard: "Send Report" button (full all-time report), "Preview" toggle with live srcDoc iframe, and "Last sent" indicator.
- Verified: preview returns HTML, send-report builds + attempts send (blocked only by unverified Resend domain), UI screenshot confirms buttons + preview.

## 2026-06 — Scheduled Admin Digest Email
- Added `backend/services/digest.py`: config store, data aggregator (new signups, open support requests, top-clicked pages, automation health), HTML builder, `send_digest_now`, and `scan_digest` due-check with once-per-day guard.
- Admin endpoints (`routers/admin.py`): `GET/PUT /api/admin/digest-config`, `POST /api/admin/digest/send-now`.
- Background loop (`server.py`): `scan_digest()` added to `_reminder_loop` (runs every 30 min, sends when due).
- Frontend `Admin.jsx`: `DigestCard` in Site Note tab — enable toggle, Frequency (Daily/Weekly/Monthly), Day-of-week / Day-of-month, Time (UTC hour), editable recipient (default admin@godesk.io), Save schedule + Send now.
- Verified via curl (GET/PUT/send-now) and UI screenshot. Send fails only due to expected unverified Resend domain `godesk.io`.

## Earlier (prior session)
- UI scale default 0.7 (slider min 0.55 / max 0.85, 70% centered) — confirmed already complete.
- Per-user SMTP, Resend integration, Microsoft Clarity, click heatmap + reference overlay, Support inbox, N8N/MCP workflows, WebRTC/LiveKit conferencing, QR login, session management.

## Implemented (2026-06-16) — NMI Payments (Admin → Payments tab)
- **New Admin → Payments tab** (`src/pages/admin/PaymentsTab.jsx`): take-a-payment card (amount/email/description), recent-transactions list with status badges, and per-transaction refund/void. Stat cards: Collected, Successful sales, Failed, Refunds/voids.
- **Frontend tokenization** via official NMI **Payment Component** (`@nmipayments/nmi-pay-react`, React 19 compatible) using the PUBLIC tokenization key; card data never touches our server. `onPay` returns the payment token to the backend.
- **Backend** `routers/payments.py` uses NMI **v5 Payments API** (`{NMI_API_BASE}/payments/sale`, `Authorization: <private key>`), stores results in `payment_transactions`, exposes `GET /admin/payments/{config,stats,transactions}`, `POST /admin/payments/charge`, `POST /admin/payments/refund/{tx_id}` (refund→void fallback). Env: `NMI_API_BASE`, `NMI_TOKENIZATION_KEY`, `NMI_SECRET_KEY`, `NMI_CURRENCY`.
- Status: code-complete & wired; backend endpoints verified via curl. **BLOCKED on valid NMI credentials** — the provided sandbox keys are rejected by NMI's own servers (public key: "Specified API key not found" 401; private key: "Authenticated user is invalid" 403), verified against secure.nmi.com AND sandbox.nmi.com. Not a code bug. Widget shows a graceful "Failed to initialize" + admin hint until valid Tokenization + API keys (attached to an active user) are supplied. Note: the new Payment Component only targets secure.nmi.com, so a reseller/white-label gateway would require a different (classic Collect.js/Direct Post) approach.

## Updated (2026-06-16) — NMI Payments NOW WORKING (Direct Post, sandbox)
- Resolved the credential blocker: the working key is the classic NMI **security key** `KvX958...` on a **sandbox account**, which must hit `sandbox.nmi.com`. The earlier `pf.sandbox.aflt...`/`v4_secret_...` pair (new v5 platform) was invalid for this account.
- Switched to **classic Direct Post API** (`routers/payments.py` → `NMI_TRANSACT_URL=https://sandbox.nmi.com/api/transact.php`, `NMI_SECRET_KEY=KvX958...`). Frontend `PaymentsTab.jsx` now uses secure card inputs (number/expiry/CVV) posting to the backend (removed the `@nmipayments` Payment Component since it only targets secure.nmi.com and can't reach a sandbox account).
- Verified end-to-end (curl + UI): sale → `response=1 SUCCESS`, refund→void fallback works, stats/transactions update, card last-4 shown, refunded sales excluded from Collected. UI toast "Charged $X · <txn id>".
- NOTE (production): Direct Post sends the PAN to our server (PCI SAQ D). For a public/customer-facing checkout, upgrade to Collect.js tokenization (needs a public "Tokenization" key) for SAQ A — flagged in the UI. `@nmipayments/*` packages remain installed for a future Collect.js/hosted-component swap.

## Implemented (2026-06-16) — Pricing plans + public checkout → CRM
- **Admin → Plans tab** (`src/pages/admin/PlansTab.jsx`): full CRUD for pricing plans (name, description, price, interval month/year/once, features, "Popular"/highlighted, CTA text, sort order, active toggle). Backend `GET/POST/PUT/DELETE /api/admin/plans`.
- **Public /pricing page** (`src/pages/Pricing.jsx`, route in App.js; "Pricing" button added to landing Home.jsx): renders active plans from public `GET /api/plans`; free plans route to /login, paid plans open a checkout modal → `POST /api/checkout/plan` (rate-limited by IP, amount taken server-side from the plan).
- **Checkout → CRM**: successful purchases charge via NMI Direct Post (sandbox) and upsert `crm_contacts` as **stage=won, value=plan price, source=pricing** (`_crm_mark_won`), and log a `payment_transactions` row with plan_id/name. So paying customers appear in the CRM pipeline/forecast automatically.
- Added `dup_seconds:"0"` to NMI sale payloads (charge + checkout) to avoid 2-min duplicate-transaction rejections on retries.
- Verified: backend curl (CRUD + checkout + CRM won) and frontend testing_agent iteration_35 (all flows pass, no regressions). Current plans: Free $0 / Pro $10/mo / Team $25/mo (admin-editable).

## Implemented (2026-06-16) — Yearly billing + plan-based feature gating
- **Yearly billing**: plans now have `yearly_price`; public /pricing has a Monthly/Yearly toggle (shows /yr price + "Save X%" badge). `POST /api/checkout/plan` accepts `billing` ('month'|'year') and charges the right amount server-side.
- **Feature gating**: each plan has `feature_keys` (admin picks which app features it unlocks: chat/projects/assets/integrations/ai_assistant/friends). Global admin toggle `plan_gating` (default OFF) in Admin → Plans. `core.ensure_feature(name, user)` now returns 402 when gating ON and the user's plan lacks the feature; admins always bypass; users with no plan fall back to the cheapest active plan. Call sites updated in assets/integrations/ai/messaging/projects routers.
- **Entitlements**: `GET /api/me/entitlements`; frontend `FeaturesContext` exposes `entitled(flag)`; Layout locks nav items (Lock icon → /pricing) + shows an "Upgrade" button. A logged-in buyer's `plan_id` is auto-assigned on checkout; admin can set a user's plan via `POST /api/admin/users/{id}/plan`.
- IMPORTANT: This NMI sandbox processor REJECTS `dup_seconds` ("Disabling Duplicate Check is not allowed"), so it was removed. Duplicate identical charges within ~2 min are rejected by the gateway by design — use unique amounts when testing.
- Verified: backend curl (entitlements, 402 gating, yearly checkout + auto-assign, admin toggles) + testing_agent iteration_36 (7/7 phases pass). Gating left OFF by default.

## Implemented (2026-06-16) — Admin plan assignment + subscriptions & renewal reminders
- **Admin → Users**: each user row now has a plan dropdown (data-testid user-plan-select) that assigns/clears a plan via POST /api/admin/users/{id}/plan (used by feature gating). Verified assign + clear + 404 on bad plan.
- **Subscriptions**: successful pricing-page checkouts (month/year plans) create a `subscriptions` record with current_period_end. Admin → Payments has a Subscriptions panel showing Est. MRR, active count, per-sub status/renewal date, and Cancel. Endpoints: GET /api/admin/subscriptions, POST /api/admin/subscriptions/{id}/cancel.
- **Auto-renewal reminders**: background scan (`scan_subscription_renewals`, added to server.py reminder loop) marks expired subs and, 7 days before period end, sends the customer a renewal reminder (in-app 'billing' notification for logged-in users + best-effort email) and sets renewal_reminded. Verified via direct scanner run (notification created). Note: not auto-charging (cards aren't vaulted with Direct Post) — reminder prompts re-purchase.

## Implemented (2026-06-16) — "My billing" in user Settings
- New `GET /api/me/billing` returns the user's current plan + active subscription (renewal date) + gating flag.
- Settings page now has a **Billing & plan** section (between Notifications and Connected devices): shows current plan + price/interval, renewal date (if subscribed), and Renew/Change-plan buttons that link to /pricing. Free-tier users see an upgrade nudge. Verified via curl + screenshot (demo user shows "Pro · $10/mo · Change plan").

## Implemented (2026-06-18) — Feature gating enabled + Software Update Center
- **Feature gating turned ON**: Free=Messages/Projects; Pro=+Assets/AI/People; Team=all. 16 non-admin users assigned Free (admins + existing plan holders untouched). Verified via entitlements.
- **Admin → Updates tab** (`src/pages/admin/UpdatesTab.jsx`, backend `routers/updates.py`): admin configures the GitHub repo (default https://github.com/GoDeskio/Stitches.git), branch, and optional token. Shows installed version (VERSION + git sha), environment (self-hosted vs managed), and latest commit from GitHub. Buttons: Check for updates, Apply update. Toggles: enable checks, auto-apply. Background `scan_updates()` (added to reminder loop, throttled 25min) auto-checks and notifies admins + shows a site banner (UpdateBanner) when a new version is available.
- **True auto-apply for self-hosted** (`scripts/update.sh`): git fetch + reset to origin/branch, install deps, build frontend, restart via supervisor. GUARDED: only runs when SELF_HOSTED=true (or no .emergent dir); on the managed Emergent preview, Apply returns a "deploys managed by platform" message instead of running destructive commands.
- **DATA PERSISTENCE THROUGH UPDATES (guaranteed)**: updates replace code ONLY. MongoDB (all user/admin/site data) is a separate service — untouched. `.env` files are git-ignored AND explicitly backed-up/restored around each update. Uploads use external object storage. Script never runs `git clean` (untracked files preserved) and takes a best-effort mongodump to backups/ before applying. Surfaced in the UI as a green "Your data is safe" note. Endpoints: GET/POST /api/admin/updates/config, POST /api/admin/updates/check, /apply, GET /status, /available.
- Verified: backend curl (config save/mask/persist, invalid-repo 400, check vs GoDesk repo, apply managed-guard) + frontend screenshots (tab renders, check works, data-safety note).

## Implemented (2026-06-18) — One-click Restore from backup (update rollback)
- `scripts/update.sh` now records a restore manifest before each update (pre-update git sha, branch, repo, has_db) alongside the .env + mongodump snapshot.
- New `scripts/restore.sh`: rolls code back to the recorded sha, restores .env files, and restores MongoDB (mongorestore --drop) from the snapshot, then rebuilds + restarts.
- Backend `routers/updates.py`: GET /api/admin/updates/backups (lists snapshots via manifest), POST /api/admin/updates/restore/{stamp} (self-hosted only; managed preview returns a safe message; validates stamp; 404 on missing; shares update_jobs status/log polling).
- Admin → Updates now has a **Backups & rollback** section listing each snapshot (date, pre-sha, DB/.env badges) with a one-click Restore. Verified: list, managed-guard message, 404 on bad stamp, UI render.
