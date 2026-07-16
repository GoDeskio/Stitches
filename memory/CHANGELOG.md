# Stitches Changelog

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
