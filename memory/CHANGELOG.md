# Stitches Changelog

## 2026-06 — Per-bot callback health badge + retry give-up alerts
- **Endpoint health**: `GET /api/bots` now returns `callback_health` per bot — last-24h delivery success rate computed via a single Mongo aggregation over `bot_actions`. The Bots page shows an at-a-glance badge ("75% · 24h") coloured green (≥90%) / amber (≥50%) / red (<50%) with a "X/Y delivered" tooltip. Verified 2/3 → 67% and 3/4 → 75%.
- **Retry give-up alerts**: when a callback exhausts all 3 auto-retries (or the bot has no callback URL) `scan_failed_callbacks` now pings the bot **owner** once — in-app notification + best-effort email ("Bot callback failed"). Verified exactly one notification fires at the give-up transition (auto_retries=3, next_retry_at cleared); email path attempts send (Mailgun 401 until a valid key is added, as expected).


## 2026-06 — Retry backoff + callback logs
- **Retry backoff**: auto-retries are now spaced out (~1 min → ~10 min → ~1 hr) via a per-action `next_retry_at`, so a longer outage still gets a late attempt instead of burning all 3 in 90 min. Added a dedicated **60s callback-retry loop** (separate from the 30-min business loop) so the fine-grained schedule is actually honoured; after the 3rd attempt the schedule is cleared. Verified the exact progression (attempt1→600s, attempt2→3600s, attempt3→give up) and that success clears the schedule.
- **Callback logs**: `_post_callback` now returns the response body; each trail row stores `last_response`. Trail rows are expandable to show STATUS (detail), the RESPONSE body snippet, and the NEXT AUTO-RETRY time — so admins can debug a failing endpoint. Rows also show `·N manual` / `·N auto` retry counts.
- **Verified**: delivered action captured the real response body (`{"status":"received"...}`); failed action scheduled `next_retry_at` ~60s out; backoff progression + give-up; expandable log panel renders in the UI. Test data purged.


## 2026-06 — Signed callbacks (HMAC) + background auto-retry
- **Signed callbacks**: every bot has a `signing_secret` (`whsec_…`, generated at create/clone, encrypted at rest, owner-visible). All card-action callbacks are POSTed with `X-Stitches-Signature: sha256=HMAC(secret, "{timestamp}.{body}")` plus `X-Stitches-Timestamp` and `X-Stitches-Bot` headers so the receiving tool can verify authenticity. Owner UI shows/copies/rotates the secret (`POST /bots/{id}/rotate-secret`) with the exact verification formula.
- **Auto-retry**: `scan_failed_callbacks()` (added to the 30-min reminder loop) re-attempts each failed callback up to 3 background times within 24h, self-healing transient outages; tracked via `auto_retries` (separate from manual `retry_count`). Centralized all callback sending in a signed `_post_callback` helper shared by the action, manual resend, and auto-retry paths.
- **Verified**: receiver-side HMAC check `sig_valid=True`; failed action (auto_retries 0) → after scan with endpoint back up → delivered True, auto_retries 1; signing-secret UI renders with show/copy/rotate. Test data purged.


## 2026-06 — Approval Trail: CSV export + resend failed callbacks
- **Export CSV**: `GET /api/admin/bots/actions/export` (require_admin, honours the `q`/`status` filters) streams the whole trail as `approval-trail.csv` (When, Approver, Email, Bot, Action, Card, Channel, Delivered, Detail, Retries). Frontend "Export CSV" button downloads it via an authed blob request.
- **Resend delivery**: each action now carries a stable `action_uid`. `POST /api/admin/bots/actions/{action_uid}/resend` (require_admin) re-POSTs the exact stored payload to the bot's current callback URL, updates the row's `delivered`/`detail` and increments `retry_count`. Failed trail rows show a "Resend" button; the row reflects the new status + "·N retry".
- **Verified**: curl (resend dead→false, then up→true with retry_count incrementing; CSV headers `text/csv` + `attachment` + correct rows; non-admin→403) + UI (Export button, per-row Resend, retry badge, failure toast). Test data purged.


## 2026-06 — Approval Trail (admin audit of card actions)
- **Approval Trail** admin tab (`admin-tab-botactions`): a searchable, paginated audit of every bot-card action — approver (name/email), bot, action, card title + channel, delivery status (callback delivered Yes/No with the reason on hover), and timestamp.
- Backend: `GET /api/admin/bots/actions` (require_admin) with pagination + `q` search (approver/bot/card/action) + `status` filter (all/delivered/failed). Action records are now **denormalized at write time** (bot_name, action_label, card_title, channel_name, user_name/email) so the trail stays intact even if the bot/message is later deleted.
- **Verified**: curl (enriched rows, failed filter, text search, non-admin→403) + UI (tab renders the table with green/red delivery pills, search + All/Delivered/Failed filters, pagination). Test data purged.
- Note: dropped the "Bot Leaderboard" idea per user — bots are inbound integration connections, not ranked content.


## 2026-06 — Card approver rules (who can action a card)
- **Approver rules**: a bot card can include `approvers` — a list of specific emails and/or roles (`role:admin`, `role:superadmin`, `role:owner`). When set, only matching users can tap the card's action buttons; anyone else gets `403 "You're not authorized to action this card."` (enforced server-side in `bot_card_action`, before the action lock).
- Sanitized by `_clean_approvers` (only valid emails / known role tokens, de-duped, max 20); matching via `_user_matches_approvers` (role/email/owner checks, super-admin resolved against `ADMIN_EMAIL`).
- Frontend: `BotMessageCard` shows a "🛡 Only <…> can action this" hint and **proactively disables** the buttons for non-approvers (server remains source of truth). Rich-card cURL example now includes an `approvers` field.
- **Verified**: curl (email approver→200, role:admin as non-admin→403, role:owner→200, webhook fired only for authorized) + UI (hint shown, buttons disabled for non-approver). Test data purged.


## 2026-06 — Card action lock (single-decision, race-safe)
- **Action lock**: the first action taken on a bot card wins — the callback fires exactly once and all buttons disable for everyone in the channel. Enforced **atomically** server-side (`update_one` guarded by `card_receipts` empty) so concurrent taps can't double-fire; a losing/late tap gets `409 "This card was already actioned by <name>."`. The `card_receipt` WS broadcast carries `locked: true`.
- Frontend: `BotMessageCard` disables all buttons and shows a "🔒 locked" hint once any receipt exists; the taken action shows "✓ <label>".
- **Verified**: curl (1st→200 locked, 2nd→409, webhook fired exactly once) + UI (both buttons disabled, "✓ Approve", locked badge, receipt line). Test data purged.


## 2026-06 — Card action receipts (channel-wide outcome line)
- **Action receipts**: when a teammate taps a bot-card button, `POST /api/bots/{bot_id}/action` now records a receipt on the message (`card_receipts: [{action_id,label,user_id,user_name,at}]`) and broadcasts a `card_receipt` WebSocket event to the channel. Everyone sees a subtle "✓ Alice approved · 1:45 AM" line under the card in real time (also survives reloads/polling).
- Frontend: `BotMessageCard` accepts `receipts` and renders them; Messages WS handler updates `card_receipts` on the `card_receipt` event.
- **Verified end-to-end**: curl (receipt persisted + returned + present on the message) and a full UI click that rendered the receipt line channel-wide via WebSocket. Test data purged.


## 2026-06 — Bot card actions (callbacks) + bot-health email pings
- **Card action buttons**: bot cards can include `actions: [{id,label,style(primary/default/danger)}]` (max 4). They render as tappable buttons in the chat card. Tapping one calls `POST /api/bots/{bot_id}/action {message_id, action_id}` which validates the user's channel access, then POSTs a `card_action` payload (action_id, label, bot, message/channel, acting user, timestamp) to the bot's **callback URL** and records it in `bot_actions`. Owners set/clear the callback URL per bot on the Bots page (`outbound_webhook`, Fernet-encrypted, masked).
  - Access-gated: non-members → 403; unknown action → 400; no callback set → 400 with guidance.
  - **Verified end-to-end**: curl (deliver HTTP 200 to a local catcher, 400/403/unknown paths) AND a full UI flow (click "Approve" → toast + callback received by the external tool).
- **Bot-health email pings** (improvement): `scan_bot_health()` now also emails the bot owner (best-effort via `send_email_detailed`) in addition to the in-app "Bot went quiet" notification. Delivers once Mailgun/SMTP is configured; no-ops gracefully otherwise.
- Card sanitizer `_clean_card` extended with `actions`; `BotMessageCard` renders buttons with busy/done states. Bots page rich-card example now shows an `actions` array.


## 2026-06 — Bot health alerts + rich bot cards (iteration_42)
- **Bot health alerts**: `scan_bot_health()` (in the 30-min reminder loop + manual `POST /api/admin/bots/scan-health`, admin-only) pings a bot's **owner** with an in-app "Bot went quiet" notification when the bot's last activity (`last_used_at`, else `created_at`) is 7+ days old. Idempotent via a `stale_alerted` flag that **re-arms** automatically when the bot next ingests a message.
- **Rich bot cards**: `POST /api/bots/ingest` now accepts an optional `card` `{title, status(info/success/warn/error), fields:[{label,value}], link}` (sanitized server-side by `_clean_card`; text OR card required, else 400). Messages carry the card (`_create_message(card=...)`) and render as a styled **BotMessageCard** in chat with a status-colored left accent, a key/value field grid (hover shows full values), and an "Open" link. The Bots page shows a "Send a rich card instead" cURL example per bot.
- **Verified (iteration_42: backend 8/8 pytest + frontend 100%, zero defects)**: card ingest/persist/render with correct accent colors, empty-body 400, health alert fires once + re-arms after use, non-admin blocked from scan, plus full bot + chat regression. Test data purged.


## 2026-06 — Bot usage stats (sparklines) + categories/filter + Featured Bots strip (iteration_41)
- **Bot usage stats**: each bot now tracks per-day message counts (`daily.<YYYY-MM-DD>`, incremented on ingest, auto-pruned >30d). `_spark()` returns a 14-day series rendered as an SVG **sparkline** (`components/Sparkline.jsx`) on every My-bots and Directory card.
- **Bot categories**: creators tag bots (general/ci/alerts/support/monitoring/marketing/sales/ops) via a picker in the New-bot modal and an inline `bot-category-select` on existing cards. The **Directory** has category **filter pills** with live counts. `create`/`patch`/`clone` accept `category`; clones inherit the source category.
- **Featured Bots dashboard strip** (`components/FeaturedBots.jsx`, mounted in Dashboard): surfaces up to 6 most-active shared bots (ranked by 7-day activity via `GET /api/bots/featured`) with category badge, owner, "N this week" and a sparkline; hidden entirely when there are no shared bots.
- Backend: `GET /api/bots/directory` now also returns `activity[14]` + `categories`; `GET /api/bots/featured` added. Token is still **never** exposed in directory/featured payloads.
- **Verified (iteration_41: backend 8/8 pytest + frontend 100%, zero defects)**: category create/edit/persist, sparkline reflects ingests, directory filter, featured strip renders + hides when empty, cross-user clone inherits category with a fresh token, no token leak.


## 2026-06 — Bot Directory (share + reuse) + LiveKit/TURN readiness verified (iteration_40)
- **Bot Directory**: bots can now be **shared to a team directory** so every member can discover and reuse them. New `GET /api/bots/directory` returns all shared bots with the owner's name — and **never exposes the token** (public-safe `_directory_bot` view). Bots gained a `shared` flag + optional `description`.
- **Clone & reuse**: `POST /api/bots/{id}/clone` lets any member copy a shared bot into their **own** bot with a **fresh token**, pointed at a channel they have access to (membership-gated; cloning a non-shared bot → 404).
- **Bots page redesign** (`Bots.jsx`): two tabs — *My bots* (with a per-card **Share** toggle + shared badge) and *Directory* (gallery of shared bots with **Clone & reuse**). Added a collapsible **"How to set up a bot"** guide (4 steps + copyable ingest endpoint) shown on the Bots tab across all dashboards. Added a zero-workspace hint so users without a workspace aren't dead-ended in the create/clone modals.
- **Verified (iteration_40, frontend E2E 100%, zero bugs)**: cross-user flow (Alice shares → Admin sees it with owner name, no token, no "yours" badge → clones into own channel with a unique fresh token), share toggle, setup guide. Backend curl-verified (directory no-token, clone fresh-token, non-shared→404).
- **LiveKit SFU + coturn TURN readiness (kept OFF, per user)**: confirmed activation-ready — `/api/rtc/config` returns STUN-only with `sfu.enabled=false`, `/api/rtc/sfu-token` → 400 while disabled, `/api/admin/rtc/test` connectivity tester live, setup-status shows sfu/turn as optional. Deploy artifacts present (`deploy/docker-compose.yml` with LiveKit + coturn incl. UDP port ranges, `livekit.yaml`, README). Activate via Admin → Meetings after deploying to infra with open UDP ports.
- **Ops Alerts webhook**: skipped per user — they'll paste their Slack/Discord webhook in Admin → Storage & DB later.


## 2026-06 — Email delivery diagnostics finalized (P1) + full regression (iteration_39)
- **Root cause of confusing "email failing" reports fixed**: `send_email_detailed` tried providers in order and only kept the *last* fallback error, so the admin saw an unrelated SMTP error even though the *active* provider (Mailgun) was the real failure. `services/email.py::_send_email_impl` now accumulates a per-provider error map and returns a detail that **leads with the active provider** — e.g. `Mailgun (active) failed: Mailgun 401: Forbidden | admin SMTP failed: …`.
- **`/api/admin/setup-status` email pill** now reflects the *selected* provider (`Mailgun (active)`), instead of always reporting whatever happened to be configured first (previously mislabeled "SMTP").
- Hardened the provider id→label map (includes `resend`) to avoid a future KeyError.
- **Verified (iteration_39, testing_agent, 100% backend 11/11 + 100% frontend, zero issues)**: active-provider error surfacing, setup-status label, plus full regression (auth for 4 users, super-admin gating on DB/storage, RTC config + SFU-token-400, bots create+ingest, admin dashboard tabs render, user dashboard renders).
- NOTE (user-action): actual delivery still fails because the stored **Mailgun API key is invalid (401 Forbidden)** and the Gmail SMTP account needs an **app-specific password**. Enter a valid key at Admin → Email to go live. Restored the Mailgun domain/sender (`mg.godesk.io` / `noreply@mg.godesk.io`) that the test overwrote.


## 2026-06 — Ops alerts: quiet-hours + severity filter
- `services/ops_alerts.py` now supports `min_level` (info/warn/error), `quiet_enabled`, `quiet_start`/`quiet_end` (hours) and `tz_offset`. `_passes_filters` drops events below the min severity, and during quiet hours only `error`-level pings go through. Manual "Send test" bypasses filters.
- Persisted via `POST /admin/ops-webhook` (expanded key list); exposed in `public_ops_webhook`.
- UI (`StorageDbTab` OpsWebhookSection): Minimum-severity select + Quiet-hours toggle with From/To hour pickers and UTC offset.
- **Verified**: unit test of `_passes_filters` (warn-min blocks info; quiet blocks warn, allows error) + live catcher end-to-end (min_level=error filtered a warn purge → 0 delivered; min_level=info delivered it). Config persists; UI renders; clean compile. Test data + webhook cleaned up.


## 2026-06 — Ops alerts broadened into a live feed
- Extended `send_ops_alert` hooks beyond auto-rollback to a full ops feed:
  - **Payments/subscriptions** (`payments.py`): new pricing-page purchase → "New subscription 🎉" (plan/amount/email); successful admin charge → "Payment charged 💳".
  - **Destructive admin actions** (`storage_admin.py`): collection purge (warn), DB restore (error), delete files by user / orphans (warn), delete-all files (error) — each with actor email + counts.
- All calls are best-effort and only send when the webhook is enabled.
- **Verified end-to-end** with a local webhook catcher: enabling the webhook and purging a throwaway collection delivered the exact Slack-formatted message ("Collection purged 🗑️ … deleted by admin@stitches.app"). Cleaned up webhook + throwaway data after.


## 2026-06 — Ops-alerts webhook (Slack/Discord), super-admin only — TESTED
- **Service** `services/ops_alerts.py`: webhook URL stored Fernet-encrypted; `send_ops_alert(title, msg, level)` posts to Slack (`{text}`) or Discord (`{content}`) with auto platform detection.
- **Endpoints** (super-admin only, in `storage_admin.py`): `GET/POST /admin/ops-webhook` (config, returns `has_url` only), `POST /admin/ops-webhook/test`. Wired into `updates.py` `_alert_admins_job` so an auto-rollback / failed update pings the channel (level warn/error).
- **UI**: `OpsWebhookSection` added to the top of the super-admin **Storage & DB** tab (top-admin dashboard only) — URL (masked), platform select, enable toggle, Save + Send test.
- **Verified by testing_agent (iteration_37, 100% backend + frontend, 0 issues)**: save/get/test/clear cycle, encrypted at rest (no plaintext leak), destructive DB purge + storage delete-orphans on seeded throwaway data, DB backup, audit trail capture, and access control (non-admin `demo@stitches.app` gets 401/403). Throwaway data cleaned up after.


## 2026-06 — Danger-zone audit trail (Storage & DB tab)
- **Backend** `GET /admin/audit/destructive` (super-admin): returns the last 100 destructive actions from the activity log (db_purge/delete_doc/backup/restore, storage delete asset/by-user/orphans/all), joined with actor name + email.
- **Frontend** `AuditSection` in `StorageDbTab.jsx`: red-bordered "Danger-zone audit trail" listing each action with a color-coded dot, human label + meta (collection/docs, backup stamp, file counts), actor, and timestamp; refresh button.
- Verified: endpoint returns the earlier backup entry (actor "Stitches Admin Test", stamp); screenshot confirms the audit row + PROTECTED users badge + backups/storage sections render. Clean compile.


## 2026-06 — Super-admin Storage & Database management tab
- **New backend router `routers/storage_admin.py`** (super-admin only, gated by `require_super_admin` = email == `ADMIN_EMAIL`):
  - DB: `GET /admin/db/overview` (dbstats + per-collection count/size/indexes), `GET /admin/db/collections/{name}/docs` (paginated JSON browse), `POST …/delete-doc` (delete by _id; super-admin user protected), `POST …/purge` (empty a collection; `users` purge preserves the super admin), `POST /admin/db/backup` + `GET /admin/db/backups` + `POST /admin/db/restore/{stamp}` (mongodump/mongorestore).
  - Storage: `GET /admin/storage/overview` (total files/bytes + per-user breakdown w/ orphan flag), `GET /admin/storage/assets` (paginated), `DELETE /admin/storage/assets/{id}`, `POST …/delete-by-user/{id}`, `…/delete-orphans`, `…/delete-all` (hard-delete: removes object via new `core.delete_object` + DB record). All destructive ops logged to activity log.
  - `GET /admin/superadmin/whoami` → `{is_super_admin}` for UI gating.
- **Frontend** `pages/admin/StorageDbTab.jsx` + wired into `Admin.jsx` as a **"Storage & DB"** tab shown only when `whoami.is_super_admin` (ADMIN_EMAIL). Sections: DB overview (collections w/ Browse doc-viewer + Empty), DB backups (backup/restore, disabled w/ notice if mongodump absent), File storage (per-user usage + delete user/orphans/all). Confirm dialogs on all destructive actions.
- Verified via curl (whoami=true, 33 collections/1990 docs, real mongodump backup 427KB, doc browse, storage overview 10 files/5 users) + screenshot (tab renders for super admin). Clean compile. Destructive purge/delete-all endpoints were NOT executed against preview data (logic mirrors tested paths).


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

## Implemented (2026-06-28) — Guided Coturn TURN server setup (Admin → Meetings)
- New `frontend/src/pages/admin/TurnSetupGuide.jsx`: collapsible step-by-step guide with **Docker (quickest)** and **From source (Ubuntu/Debian)** tabs, each with copy-to-clipboard command blocks (docker run + docker-compose, deps libevent2/openssl/libmicrohttpd/sqlite3, /etc/turnserver.conf, systemctl enable, firewall ports).
- Ends with a "paste these values below" hint mapping the generated secret/IP to the TURN URLs/username/credential fields, then Test connectivity.
- Rendered inside `MeetingsTab` above the TURN config card. Also FIXED a broken build: previous session imported `TurnSetupGuide` without creating the file (webpack module-not-found). Verified via screenshot.

## Implemented (2026-07-31) — Deployment Center + AI Memory Persistence (from "Too Many Stitches" project record)
- **Deployment Center** (new Admin tab `deploy`, `routers/deploy_center.py` + `admin/DeploymentTab.jsx`): curated 15-service GitHub catalog (coturn, livekit, traefik, prometheus, grafana, loki, minio, valkey, nats, opensearch, clamav, keycloak, postgres, synapse, element-web). Services Stitches already provides are badged "ALREADY IN STITCHES". Generates a ready-to-run bundle: clone-repos.sh, .env (auto-generated secrets), coturn/turnserver.conf, livekit/livekit.yaml, compose.yml, firewall.sh, install.sh, DEPLOY.md. Endpoints: GET /admin/deploy/catalog, PUT /admin/deploy/config (domain/public_ip/selected/encrypted github_token), POST /admin/deploy/generate (+regenerate), GET /admin/deploy/download (zip), POST /admin/deploy/apply-calls (wires generated TURN + LiveKit creds straight into Meetings config). NOTE: preview pod can't run Docker — bundle is meant to run on the operator's own VM.
- **AI Memory Persistence** (new Admin tab `aimemory`, endpoints in `routers/ai.py` + `admin/AiMemoryTab.jsx`): per-user AND shared-workspace long-term memory, both toggleable, with retention days + max items per scope. Facts auto-distilled from chats via background gpt-5.4-mini extraction and injected into the assistant's system prompt on every `/api/ai/chat`. Admin can view/search/filter/add/delete/clear memories. Collection `ai_memories` {mem_id, scope, owner_id, content, created_at}; workspace scope owner_id='__workspace__'. Settings key `ai_memory`.
- **One-Click Coturn Test**: MeetingsTab `saveTurn` now auto-runs the connectivity test after saving TURN creds.
- **Callback Sparkline**: `GET /api/bots` `callback_health.trend` now includes a 7-day daily reliability series; rendered as a mini sparkline (data-testid bot-reliability-trend) next to the 24h health badge on bot cards.
- Verified iteration_43: backend 18/18, frontend 100%, zero issues.

## Implemented (2026-07-31, part 2) — Memory Insights + Deploy Presets
- **Memory Insights** (user-facing): AiAssistant now has a "Memory" button opening a slide-in "What Stitch remembers" panel — shows the user's own remembered facts (with per-item Forget) plus read-only shared team memories. New endpoints: GET /api/ai/memory (respects admin on/off toggles), DELETE /api/ai/memory/{mem_id} (users can forget ONLY their own user-scoped memory; workspace memories are protected -> 404). Verified via curl + screenshot.
- **Deploy Presets**: DeploymentTab quick presets — Calls only (coturn+livekit), Calls + Monitoring (+traefik/prometheus/grafana/loki), Full stack (all) — one tap sets the service selection; active preset highlights.

## Implemented (2026-07-31, part 3) — Auto-Capture toggle, Pin memory, Custom deploy presets
- **Auto-Capture toggle** (per-user): users can turn off Stitch auto-learning so only explicitly pinned memories are kept. Stored in `ai_user_prefs` {user_id, auto_capture} (default true); GET /api/ai/memory returns it, PUT /api/ai/memory/prefs sets it. `_extract_memory` now honors it (skips user-scope auto capture when off; still captures workspace scope if enabled).
- **Pin A Memory** (user): POST /api/ai/memory {content} adds a user-scoped memory (source:"pinned"); rendered with a pin icon + input in the Memory panel.
- **Preset From Selection** (admin): save the current service selection as a named preset — POST /api/admin/deploy/presets, DELETE /api/admin/deploy/presets/{id}; presets returned in catalog and rendered (clickable, deletable) beside the built-in Calls only / Calls+Monitoring / Full stack presets.
- Verified via curl (prefs toggle, pin source, preset save+list, forget own=200/team=404) + screenshots of both UIs.

## Implemented (2026-07-31, part 4) — Memory Search, Edit A Memory, Preset Import/Export
- **Memory Search**: the AI Assistant Memory panel now has a live search box (data-testid memory-search-input) that filters both "About you" and team memories client-side; shows a "no matches" state.
- **Edit A Memory**: each user memory row has an edit (pencil) button -> inline input with save/cancel. New endpoint PATCH /api/ai/memory/{mem_id} (users can edit ONLY their own user-scoped memory; sets edited_at; 404 otherwise). Verified via curl (200 own / 404 missing).
- **Preset Import/Export**: custom deploy presets have a Copy icon that copies a base64 shareable code (btoa of {name, ids}); an "Import code" button decodes a pasted code and saves it via the existing POST /admin/deploy/presets. Cross-environment sharing with no new backend.

## Implemented (2026-07-31, part 5) — Memory Categories, Suggested Memories, Preset Diff Preview
- **Memory Categories**: memories now carry a category (preference/project/deadline/tool/general). Auto-extraction (`_distill_facts`) returns {content, category}; POST /api/ai/memory accepts category. The Memory panel groups "About you" facts under colored category headers.
- **Suggested Memories**: new POST /api/ai/memory/suggest {user_text, assistant_text} distills one candidate fact (no store). After each AI Assistant reply the frontend shows a suggestion chip with Remember (pins it, source=suggested) / Dismiss. Only surfaces when memory is enabled and a durable, not-already-stored fact is found.
- **Preset Diff Preview**: importing a deploy preset code now opens a modal showing which services it Adds / Removes vs the current selection before Apply (which saves the preset + updates selection). Export stays a one-click base64 copy.
- Verified iteration_44: backend 14/14, frontend 100%, zero issues.
