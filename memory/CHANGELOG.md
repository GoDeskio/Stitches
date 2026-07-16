# Stitches Changelog

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
