# Stitches Changelog

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
