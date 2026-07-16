# Stitches Changelog

## 2026-06 — Scheduled Admin Digest Email
- Added `backend/services/digest.py`: config store, data aggregator (new signups, open support requests, top-clicked pages, automation health), HTML builder, `send_digest_now`, and `scan_digest` due-check with once-per-day guard.
- Admin endpoints (`routers/admin.py`): `GET/PUT /api/admin/digest-config`, `POST /api/admin/digest/send-now`.
- Background loop (`server.py`): `scan_digest()` added to `_reminder_loop` (runs every 30 min, sends when due).
- Frontend `Admin.jsx`: `DigestCard` in Site Note tab — enable toggle, Frequency (Daily/Weekly/Monthly), Day-of-week / Day-of-month, Time (UTC hour), editable recipient (default admin@godesk.io), Save schedule + Send now.
- Verified via curl (GET/PUT/send-now) and UI screenshot. Send fails only due to expected unverified Resend domain `godesk.io`.

## Earlier (prior session)
- UI scale default 0.7 (slider min 0.55 / max 0.85, 70% centered) — confirmed already complete.
- Per-user SMTP, Resend integration, Microsoft Clarity, click heatmap + reference overlay, Support inbox, N8N/MCP workflows, WebRTC/LiveKit conferencing, QR login, session management.
