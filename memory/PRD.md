# Stitches — Product Requirements Document

## Original Problem Statement
Build a fully functional, dynamic, beautiful, heavily neumorphic web app (Slack/Teams-like) called **Stitches** where business & creative users share, collaborate, communicate and work together in shared workspaces. Each user has a full profile + dashboard with a collapsible left sidebar, a settings page storing personal/company/project info, light/dark mode, and UI-scale control. Extremely neumorphic with shadowing everywhere. Users can integrate external apps (N8N, cloud storage, AI LLMs, MCP servers) via wizards, and upload/download/share assets. Design: deep red dark neumorphic base with textured shadowed wallpaper; very easy login.

## User Choices
- Auth: **both** JWT email/password + Emergent Google login
- Chat: **both** WebSocket realtime + polling fallback
- Integrations: connection wizards on user dashboard + admin
- Assets: real uploads (object storage) from computer + cloud connect entry point
- Design: **deep red DARK neumorphic** base, light/dark toggle, attractive accents

## Architecture
- **Backend**: FastAPI (`/app/backend/server.py`), MongoDB (motor). JWT + Google session auth unified in one `users` collection (user_id UUID). Emergent object storage for assets. Emergent LLM key for AI (streaming SSE). WebSocket at `/api/ws/{channel_id}`.
- **Frontend**: React 19 + React Router + Tailwind, custom neumorphic CSS utilities (`.neu-raised`/`.neu-pressed`), framer-motion sidebar, ThemeContext (theme + `--ui-scale`), AuthContext (Bearer token in localStorage + httpOnly cookies).

## Personas
- Business user: manages workspaces, projects, integrations, team chat.
- Creative user: shares assets, collaborates, uses AI assistant.
- Admin: platform oversight via admin dashboard.

## Implemented (2026-06-15)
- Auth: register/login/logout/me, Google session exchange, brute-force lockout, admin seeding.
- Dashboard with stats + recent projects + quick actions.
- Collapsible sidebar shell with all nav + theme toggle + user card.
- Messages: workspaces + auto channels + channels CRUD + realtime chat (WS + polling).
- Projects CRUD with status cycling.
- Assets: upload (object storage) / download / share / soft-delete, image thumbnails.
- Integrations: catalog + 2-step connection wizard + connected list (N8N, cloud, LLM, MCP).
- AI Assistant: streaming chat (GPT-5.4 / Claude Sonnet 4.6 / Gemini 3.1 Pro).
- Profile page + Settings (personal/company/project info, theme, UI scale slider).
- Admin dashboard (platform stats + recent members).
- Verified: backend 14/14 pytest pass; all 12 frontend flows functional.

## Implemented (2026-06-16)
- Public blank neumorphic Home page (`/`) with stitched-leather texture, TMS logo placeholder + "Too Many Stitches" and top-right Login button. Login tagline updated.
- Notifications: bell + unread badge + toast; created on workspace/project invite and friend add.
- Admin dashboard tabs: Overview, Users (role toggle, enable/disable, reset password, impersonate/login-as with return banner), Features (global feature flags), SEO (editable meta, applied to document head), Monitoring (activity feed + 7-day chart), Heat Map (7x24 activity grid).
- Feature flags enforced backend (403) + hide nav; `is_active=false` blocks login.
- Friends/People page (add/remove connections); workspace & project member add/remove modals.
- Activity logging on login/register/message/project/asset/integration/ai/admin actions.
- Verified: all new backend endpoints via curl; all 11 new frontend flows pass (iteration_2).

## Implemented (2026-06-17)
- Branding: replaced all logos with the uploaded voodoo/stitched-doll logo (`/logo.png`) on Home, Login, Sidebar + favicon + page title.
- Admin Monitoring: audit-log CSV export (`/api/admin/activity/export`) + per-user activity drill-down (`/api/admin/users/{id}/activity`).
- Created two communication test users: alice@stitches.app / Alice@123, bob@stitches.app / Bob@123.
- Verified (iteration_3): logos render in all 3 locations, CSV export + drill-down work, and full two-user real-time chat (invite → cross-user notification → message exchange) passes.

## Implemented (2026-06-18)
- Logo: cleanly background-removed transparent voodoo-doll cutout (`/logo.png`), blends on dark background with no box on Home/Login/Sidebar.
- Login: password show/hide eye toggle.
- 1:1 Direct Messages (reuse channel messaging + WebSocket) with a Channels/Direct rail toggle, connection-based DM picker, and message-a-connection shortcut from People.
- Online presence: 30s heartbeat (`/api/presence/ping`), green online dots on People, DM list and DM picker.
- Friends quick-add to workspaces and projects (chips from your connections) in both member modals; users & admin can create workspaces/projects and add members.
- Verified (iteration_4): all four areas pass 100% (logo blend, eye toggle, two-user DM realtime + presence, quick-add for workspace & project, non-admin create).

## Implemented (2026-06-19)
- Unread message badges: per-channel + per-DM counts in the Messages rail and a total badge on the sidebar Messages nav item; auto-clear on open (read_state via `/api/channels/{id}/read`, counts via `/api/unreads`).
- Live typing indicators on channels and DMs via WebSocket (`{type:'typing'}` broadcast), auto-dismiss after 3s.
- Verified (iteration_5): unread badges (rail + sidebar, clear on open) and typing indicator pass 100% across two browser sessions.

## Implemented (2026-06-20)
- Notification controls: user Settings > Notifications toggles (master + workspace/project/friend) and admin Notifications tab for platform-wide on/off. create_notification gates on both admin-global and per-user prefs.
- Actionable AI assistant (`/api/ai/agent`): Stitch AI can create projects/workspaces, add connections, list/show stats for users, and (admin-only, guardrailed) toggle features and manage user accounts; shows an action chip + result items. Robust envelope parser (fixed double-envelope/tool-prefix bug in iteration_6→7).
- Verified (iteration_6 & 7, 100%): notification prefs gate delivery, admin global controls work, AI actions execute with non-admin guardrails, and no raw JSON leaks.

## Implemented (2026-06-21)
- Message reactions (emoji): hover-to-react picker + reaction chips with counts on channel and DM messages, toggled per user, broadcast in real time over WebSocket (`/api/messages/{id}/react`).
- AI assistant acts on your behalf: new agent actions send_message (post to a channel), invite_to_workspace and invite_to_project (add people by email) with name resolution + notifications.
- Verified (iteration_8, 100%): reactions single + cross-user (count 2) on channels and DMs, AI send/invite actions execute and reflect in the UI, no raw JSON leaks.

## Implemented (2026-07-15)
- Notes: private personal notes page (`/notes`, left-nav item) — create/edit/delete with title, content and color tag; owner-scoped via `/api/notes` (GET/POST/PUT/DELETE, owner_id filtered).
- Admin user moderation: clear labeled **Disable Account** / **Reinstate Account** button next to each user in Admin > Users (toggles `is_active`); disabled users are blocked at login (403). Admin account is never a disable target.
- Verified (iteration_9, 100%): Notes CRUD + per-user isolation and admin disable→login-blocked→reinstate all pass; reusable pytest at `/app/backend/tests/test_notes_and_admin.py`.

## Implemented (2026-07-16)
- Channel **reply threads**: hover a message → reply icon opens a Thread panel; replies stay out of the main timeline and surface via a "N replies" button. Real-time via WebSocket + REST.
- **@mentions**: typing `@` shows a member autocomplete; selecting inserts `@Name`, mentioned text is highlighted, and the mentioned user gets a `mention` notification (bell + unread). All sends now go through REST `POST /api/messages`.
- **Real integration connectors** (user-entered credentials via setup wizard): N8N (`/run`), AWS S3 / Dropbox / Google Drive (`/files` + `/download`), LLM & MCP (`/test`). Connected cards expose Run / Browse files / Test. Admin Dashboard has an **Integrations** tab. Deps: boto3, dropbox.
- Verified (iteration_10, 22/22 backend + 100% frontend).

## Implemented (2026-07-16, part 2)
- **At-rest encryption (Fernet)** for all integration credentials: encrypted on write (`ENCRYPTION_KEY` in backend .env), decrypted only server-side when calling a service. Raw `config` is never returned by any API; secrets show as bullets in the user Integrations dashboard and are absent from the admin Integrations tab. Legacy plaintext values decrypt-fallback gracefully.
- **User Activity Log** (`/activity`, left-nav): private per-user history of every account action via `GET /api/activity/me` (owner-scoped, isolated per user).
- **Admin activity search-by-user** in Admin > Monitoring: search box → member results → full per-user activity drilldown with "Back to search".
- **Downloads page** (`/downloads`, left-nav) + **Electron desktop client** scaffold in `/app/desktop` (main.js loads the live dashboard with a persistent session so users stay signed in; README + build scripts). NOTE: installers must be built from `/app/desktop` outside this sandbox — no binaries are compiled here.
- Verified (iteration_11, 14/14 backend + 100% frontend): encryption no-leak (Mongo stores `gAAAAA…` ciphertext), activity isolation, admin search-by-user, downloads render, all-account login regression.

## Implemented (2026-07-16, part 3)
- **Avatar image upload**: upload a photo from device in Settings → object storage; served via public `GET /api/users/{id}/avatar-image`; shows across app. Validated image MIME + 5MB cap.
- **Kanban task boards** per project (`/projects/:id/board`): To Do / In Progress / Done, drag-and-drop + move buttons, add/delete tasks, cascade-delete with project. Task endpoints are project-membership gated (IDOR-safe; non-members 403).
- **Dynamic UI scaling** confirmed working: Settings slider (80%–130%) → `--ui-scale` → root font-size, persisted.
- **GitHub Actions CI** (`.github/workflows/desktop-build.yml`): builds Win/macOS/Linux desktop installers on tag push and publishes a Release.
- Verified (iteration_12, 9/9 backend + 100% frontend) + post-review security hardening (task membership checks, avatar validation, owner-scoped cascade).

## Implemented (2026-07-16, part 4)
- **Beginner-friendly integration connections**: each connector now offers one or more **connection methods** with plain-language help + placeholders. Added **Email (IMAP)** (connect with email + password) and **Custom App** (username+password OR API key) connectors. N8N adds a "link + username/password" (Basic Auth) method; N8N run supports Basic Auth. Test actions do real checks (IMAP login, HTTP basic-auth), fail gracefully. Wizard has method tabs, help callouts, Escape-to-close. All creds Fernet-encrypted at rest, masked in responses.
- Verified (iteration_13, 12/12 backend pytest + 100% frontend). Hardening: IMAP socket timeout, Custom App test requires credentials.

## Implemented (2026-07-16, part 5 — Refactor)
- **Backend modularized**: `server.py` 1856 → **75 lines** (thin bootstrap: app, `/api/ws/{channel_id}`, startup/shutdown). Extracted `core.py` (shared db/security/helpers/storage/ws_manager/`_create_message`/`is_online`), `models.py` (all Pydantic), and `routers/{auth,users,messaging,projects,assets,integrations,ai,admin}.py` included under `/api`. All 83 API routes preserved.
- **Frontend**: `Messages.jsx` 678 → 439 lines; extracted `components/messages/MessageParts.jsx` (MentionText, ThreadPanel, MembersModal, CreateModal, ReactionPicker).
- Verified (iteration_14): 18/18 regression suite + frontend smoke, **zero regressions** (incl. /friends, /dms, WebSocket realtime, mentions, reactions, threads, kanban gate, integrations encrypt/mask, AI stream). Test data purged.

## Implemented (2026-07-16, part 6)
- **Google Drive one-click OAuth**: "Connect with Google" on Integrations → Google consent (scope drive.readonly, offline + refresh token) → encrypted access+refresh tokens stored; Drive browse/download with auto-refresh. Callback fails safe (redirect `?google=error`, no 500s).
- **Admin-editable Google credentials**: `client_id`/`client_secret` stored in DB settings (`google_oauth`), seeded from env, editable in Admin > Integrations (secret masked; masked PUT does not overwrite). Redirect URI shown for the owner to register in Google Cloud.
- **"My Tasks" dashboard widget**: cross-project view of the user's open Kanban tasks (`GET /api/tasks/mine`, membership-scoped, project_name), click-through to the board.
- Deps: google-api-python-client, google-auth-oauthlib, google-auth-httplib2.
- Verified (iteration_15): 16/16 new + 18/18 regression, zero bugs.

## Owner setup required for Google Drive to work end-to-end
In Google Cloud Console for the OAuth app: (1) enable **Google Drive API**, (2) add redirect URI `https://stitches-connect.preview.emergentagent.com/api/integrations/google/callback`, (3) add your Google account as a **Test user** (or publish the consent screen).

## Implemented (2026-07-16, part 7)
- **Kanban assignees + due dates**: task cards have an assignee dropdown (project members) and a due-date picker; cards show assignee + due badges (overdue in red); backend enriches tasks with `assignee_name`. Membership-gated updates (non-member 403).
- **"My Tasks" upgraded**: dashboard widget sorts open tasks by due date, shows project + assignee + "Due <date>" (overdue highlighted), click-through to board.
- **Integrations available on the admin dashboard**: the full catalog + setup wizard (extracted as reusable `IntegrationsManager`) now renders in Admin > Integrations ("Connect an application") alongside the Google OAuth editor and platform-wide list. Nothing is forced — connectors are just available with wizard + setup help.
- Verified (iteration_16): 12/12 new + 18/18 regression, zero bugs.

## Implemented (2026-07-16, part 8)
- **Task due-soon reminders (in-app)**: background loop (every 30 min) + admin `POST /api/tasks/scan-reminders`; creates a `task_due` notification for the assignee of any not-done task due within 24h or overdue (idempotent via `reminded` flag; reset when due_date/assignee changes). Surfaced in the existing NotificationBell.
- **Deployment-readiness (works outside Emergent)**: CORS now reads `CORS_ORIGINS` (comma-separated) with `FRONTEND_URL` fallback + credentials; Emergent auth session URL now env-driven (`AUTH_SESSION_URL`). `deployment_agent` scan = **PASS, no blockers**. All URLs/secrets externalized to env; backend :8001, frontend :3000, all routes `/api`-prefixed, MongoDB via `MONGO_URL`.
- Verified (iteration_17): 16/16 backend + frontend smoke, zero issues.

### Deploy env vars (set for the target domain)
backend/.env: MONGO_URL, DB_NAME, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD, EMERGENT_LLM_KEY, FRONTEND_URL, ENCRYPTION_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_DRIVE_REDIRECT_URI, AUTH_SESSION_URL, (optional CORS_ORIGINS). frontend/.env: REACT_APP_BACKEND_URL. On a new domain, update FRONTEND_URL + GOOGLE_DRIVE_REDIRECT_URI and re-register the redirect URI in Google Cloud.

## Implemented (2026-06-24, part 4) — Connected devices / session management
- **Connected devices panel** (Settings → "Connected devices"): lists a user's active sessions with a friendly device label (browser + OS), IP and last-active time; the current session is badged. Sign out a single device, or **"Sign out all other devices"** (keeps the current device logged in via a freshly issued token).
- **Auth**: `create_access_token` now embeds `iat` + optional `jti`; login/register/QR-claim record a row in `sessions` (device/UA/IP). `resolve_user_from_token` rejects revoked-session `jti`s and any token issued before a per-user `sessions_valid_after` epoch (revoke-all). Backward compatible with pre-existing jti-less tokens. Indexes on `sessions.jti` / `sessions.user_id`.
- Verified (iteration_20): 3/3 backend + 100% frontend; full revoke flow confirmed (other devices → 401, current device stays signed in). Google-login sessions are separate (not shown in this JWT panel).

## Implemented (2026-06-24, part 5) — session hardening + new-device alerts
- **"New sign-in" security notification**: when a device that hasn't been seen before (device label + IP) signs in — and it isn't the user's first-ever session — the user gets an in-app `security` notification linking to Settings. Verified created on a second-device login.
- **Session scaling/cleanup**: added compound index `sessions {user_id:1, last_seen:-1}` and a **TTL index on `revoked_at` (7 days)** so revoked sessions are auto-purged; single-revoke and revoke-all now stamp `revoked_at`.

## Implemented (2026-06-24, part 6) — always-on security alerts
- **Security alerts bypass the mute**: `create_notification` treats `security` notifications specially — they deliver even when the master (global or per-user) notifications toggle is off, and are only silenced by a dedicated toggle.
- **Dedicated "Security alerts" toggle** in Settings → Notifications (independent of the master switch, default on, `notif-security`). Added `security` to `DEFAULT_NOTIF_PREFS`.
- Verified via curl: master OFF + security ON still fires the new-device alert; security OFF suppresses it.

## Implemented (2026-06-24, part 7) — Audio/Video conferencing + security-bell polish
- **WebRTC conferencing** (peer-to-peer mesh, signaling over the app's own WebSocket, public STUN — no external service/keys): `/meetings` page (start instant meeting / join by code, opens the room in a new window) + Dashboard quick action; `/call/:roomId` full-window room with camera+mic **permission prompts**, participant grid with real names, and controls: **mute mic, toggle camera, screen share (getDisplayMedia + replaceTrack), end call, copy invite**. Backend: `CallManager` + `WS /api/ws/call/{room_id}` (welcome/peer-joined/signal-relay/peer-left) and REST `POST /api/meetings`, `GET /api/meetings/{id}`.
- **Admin Meetings tab**: start a meeting, monitor live rooms (live participant badge), and force-**end** any meeting. `GET /api/admin/meetings`, `POST /api/admin/meetings/{id}/end` (admin-only).
- **Security notifications distinct in the bell**: red shield icon + "All / Security" filter tabs; security items get a red accent.
- Verified (iteration_21): 100% frontend + backend REST/WS; two-client WebRTC media exchange confirmed working in-sandbox. Zero bugs.
- NOTE: P2P mesh uses public STUN only (no TURN) — very restrictive corporate NATs may fail to connect media; add a TURN server for guaranteed connectivity at scale.

## Implemented (2026-06-24, part 8) — conferencing (D) + self-hosted TURN
- **Top-of-dashboard launch buttons** on both user & admin dashboards: "Video meeting" (camera icon) + "Audio call" (phone icon) via reusable `MeetingLaunchButtons`; audio call opens `/call/:id?mode=audio` (camera off).
- **In-call features**: raise hand (indicator on tile + participant row), participants panel, and in-call text chat — all relayed over the call WebSocket (`chat`/`hand` message types). Participant count badge on the people button.
- **Channel "Meet"**: a Meet button in the Messages channel header starts a meeting and auto-posts a "Started a video meeting — join here: <link>" message; URLs in messages are now **clickable** (`MentionText` linkify).
- **Self-hosted TURN (option a/c, no third party)**: `GET /api/rtc/config` returns iceServers (STUN by default, +TURN when configured); admin-editable TURN server (urls/username/credential, credential masked & clearable) in Admin → Meetings (`turn-config-card`), env fallback `TURN_URLS/USERNAME/CREDENTIAL`. Calls fetch this config on join.
- Verified (iteration_22): backend 5/5 pytest + WS chat/hand relay; frontend 100%. NOTE: SFU media server (option b, e.g. LiveKit/mediasoup) NOT added — it requires raw UDP ports this preview can't expose; deploy to real infra + run coturn/SFU there for large-group guaranteed connectivity.

## Implemented (2026-06-24, part 9) — incoming-call ring + deploy-ready SFU (LiveKit)
- **Incoming-call "ring"**: starting a channel meeting (channel Meet button → `POST /api/meetings {channel_id}`) posts a clickable join link to the channel AND creates a `meeting` notification for every other workspace member. The bell polls (20s) and shows a toast with a **"Join" action** + a bell entry linking to `/call/<room>`. `meeting` icon added to the bell.
- **Self-hosted SFU (LiveKit), OFF by default**: `GET /api/rtc/config` now returns `sfu:{enabled,url}`; `POST /api/rtc/sfu-token` mints a LiveKit JWT (livekit-api, `VideoGrants`/`with_grants`); admin-editable `livekit` settings (url/api_key/api_secret — secret Fernet-encrypted & masked) at Admin → Meetings (`sfu-config-card`), env fallback `LIVEKIT_*`. `Call.jsx` fetches config on mount: loader → renders `SfuCall` (LiveKit `<VideoConference/>`) when SFU enabled, else the existing **P2P** room (default, fully tested). Deps: `livekit-api`, `livekit-client`, `@livekit/components-react`.
- Verified (iteration_23): backend 5/5 pytest + frontend 100%; P2P regression confirmed intact. NOTE: the LiveKit media path itself is only functional after deploying a LiveKit server with open UDP ports — untestable in this sandbox, so it's shipped gated OFF.

## Implemented (2026-06-24, part 10) — meeting scheduler, invites, email + calendar
- **Invite users & friends**: meeting creation accepts `invitee_ids` + optional `scheduled_at` + `description`. The "Invite people" modal on /meetings lets you search/select people, set a time, and either "Start now & invite" or "Schedule". Invitees get an in-app `meeting` notification (toast + bell with Join link).
- **Email invites + calendar**: if an admin has configured SMTP, each invitee with an email gets an HTML invite with a Join button + a `.ics` calendar attachment. `GET /api/meetings/{room_id}/ics` also powers the "Add to calendar" button. `.ics` built server-side (VEVENT).
- **Upcoming meetings** list on /meetings (`GET /api/meetings/upcoming`) for host & invitees; **meeting reminders** added to the 30-min background loop (`scan_meeting_reminders`) → in-app alert as the start time nears.
- **Email (SMTP) integration**: admin-editable SMTP (host/port/user/pass[Fernet-encrypted]/from) in Admin → Meetings (`smtp-config-card`), env fallback `SMTP_*`; uses stdlib `smtplib` in a threadpool (STARTTLS/SSL). Email also present in the integrations catalog (IMAP) on both user & admin pages. No third-party service required.
- Verified (iteration_24): backend 4/4 pytest + frontend 100%. **NOTE: actual email DELIVERY needs real SMTP creds — not exercised in tests; the send path skips gracefully when SMTP is unset.**

## Backlog / Next
- P1: (DONE 2026-06-25) Recurring meetings + week calendar — see below.
- Post-deploy: enable LiveKit SFU / coturn TURN; configure SMTP (e.g. Gmail app password) to activate meeting-invite emails.
- P2: Deeper N8N / MCP workflows once real credentials exist.  ✅ DONE 2026-06-25 (see below)
- P3 (deferred): Resend as an alternative email provider (waiting on user's API key).
- P3: Dropbox one-click OAuth (manual-token connector available now); authenticated Drive download stream.
- Refactor: split meetings.py into meetings/rtc/sfu/smtp routers.  ✅ DONE 2026-06-25 (see below)

## Implemented (2026-06-25, part 2) — meetings router refactor + deeper N8N/MCP workflows
- **Backend refactor**: `routers/meetings.py` (~440 lines) split into 4 focused routers — `meetings.py` (meeting CRUD + `.ics`), `smtp_config.py` (per-user + admin SMTP, `build_ics`, `send_meeting_email`), `sfu_config.py` (LiveKit/`_get_livekit_cfg`), `rtc_config.py` (TURN + `/rtc/config`). All 4 registered in `server.py`. Zero behavior change — full regression verified.
- **N8N run history**: `POST /api/integrations/{id}/run` now records each run (`integration_runs` collection, capped 50/integration, indexed `(integration_id, created_at)`); `GET /api/integrations/{id}/runs` returns the last 20. Run modal shows a "Recent runs" list with success/fail indicators. Deleting an integration purges its run history.
- **MCP tools**: MCP integrations expose a "Tools" action → `GET /api/integrations/{id}/mcp/tools` (JSON-RPC `initialize`+`tools/list`, SSE/JSON aware) lists available tools; `POST /api/integrations/{id}/mcp/call` (`tools/call`) invokes a tool with JSON arguments and records the call in history. New `McpModal` UI: browse tools → provide args → run → view result. Graceful handling when the URL isn't a real MCP server (empty tools / error, no crash).
- Verified (iteration_26): backend 12/12 pytest + frontend 100%. Fixed a React `useEffect` Promise-return bug in Run/MCP modals (found by testing agent).
- NOTE: real MCP tool execution requires a real MCP server (untestable in-sandbox — validated graceful fallback only).

## Implemented (2026-06-25, part 9) — Support tab unread badge
- **Open-requests badge** on the Admin "Support" tab (`support-tab-badge`): red count of open support requests, fetched efficiently (limit=1, reads `open_count`) and refreshed on tab switch so admins spot new AI escalations immediately. Self-verified (endpoint returns open_count; compiles clean).

## Implemented (2026-06-25, part 8) — admin Support inbox
- **Support inbox** (Admin → Support tab, `admin-tab-support`): lists AI-escalated `support_requests` with open/resolved/all filters, per-request subject/message/requester, a Reply link (mailto to the requester), and Resolve/Reopen actions. Stat cards for Open/Total; "Load more" pagination.
- Endpoints: `GET /api/admin/support-requests` (status/limit/skip → open_count/total/has_more) and `POST /api/admin/support-requests/{id}/status` ({resolved} → sets status/resolved_at/resolved_by).
- Verified (iteration_30): frontend 100% E2E (resolve/reopen/filters/mailto), backend curl-verified. Closes the loop on AI `contact_support` escalations.

## Implemented (2026-06-25, part 7) — ai.py refactor + integration-runs pagination
- **AI handler refactor**: extracted the agent prompt + all per-action handlers from `routers/ai.py` (303→117 lines) into `services/agent_actions.py` (dict-dispatched `USER_HANDLERS`/`ADMIN_HANDLERS`, `build_agent_system`, `execute_agent_action`). Behaviour-neutral — verified create_project, contact_support, and informational Q all still work.
- **Pagination** on `GET /api/admin/integration-runs`: `limit` (≤200) + `skip` params; response adds `filtered_total`, `skip`, `limit`, `has_more`. Admin Automation activity list now uses a "Load more" button (`automation-load-more`, page size 20). Verified page1 has_more=true / page2 has_more=false.

## Implemented (2026-06-25, part 6) — admin-editable announcement, support email, AI support escalation
- **Admin-editable Home note**: the landing-page glass card is now a managed site announcement. Admin → **Site Note** tab (`admin-tab-sitenote`) edits title/message/signature and toggles it on/off. Public `GET /api/site-config`; admin `GET/PUT /api/admin/site-config`. Home shows it only when enabled; dismissal versioned by `updated_at` so editing re-shows it.
- **Configurable support email** (`support-email-input`) used for AI escalations.
- **AI support escalation**: new `contact_support` action — when Stitch can't help / user reports a bug / asks for a human, it forwards to support (in-app `support` notification to admins + email via SMTP) and stores a `support_requests` doc.
- **Bug fix**: AI JSON envelope parser clobbered the real command with a nested `params.message`; now requires the `action` key.
- Verified (iteration_29): backend 7/7 pytest + frontend 100%, zero issues.


## Backlog / Next
- Post-deploy: enable LiveKit SFU / coturn TURN; configure SMTP to activate meeting-invite emails.
- P3 (deferred): Resend as an alternative email provider (waiting on user's API key).
- P3: Dropbox one-click OAuth (manual-token connector available now); authenticated Drive download stream.
- Optional: extract a shared `services/` layer (email + livekit helpers) to remove cross-router imports.  ✅ DONE 2026-06-25 (part 3)

## Implemented (2026-06-25, part 3) — services layer + admin Automation activity
- **Shared services layer**: extracted `backend/services/email.py` (`build_ics`, `send_meeting_email`, `get_smtp_cfg`, `get_user_smtp`, `_safe_port`) and `backend/services/livekit.py` (`get_livekit_cfg`). Routers `smtp_config`, `sfu_config`, `rtc_config`, `meetings` now import from services instead of importing each other — removes cross-router coupling. Behaviour-neutral (full regression passed).
- **Admin "Automation activity" view**: new Admin tab (`admin-tab-automation`) + `GET /api/admin/integration-runs` (admin-only; 403 otherwise) showing every N8N workflow trigger & MCP tool call across the platform, enriched with owner_name / integration_name / type. Stat cards (Total/Succeeded/Failed), filter pills (all/succeeded/failed/N8N runs/MCP calls), and refresh. Turns the per-user run history into platform-wide observability.
- Verified (iteration_27): backend 9/9 pytest + frontend 100%, zero issues.

## Implemented (2026-06-25, part 4) — automation failure alerts
- **Consecutive-failure alerts**: when an integration (N8N run or MCP call) fails N times in a row, all admins get an in-app `automation` notification (link → /admin), plus optional **email** (platform SMTP) and **webhook** (JSON POST). Fires once per failure streak (`failure_alerted` flag on the integration; reset on any successful run).
- **Admin-configurable** in Admin → Automation ("Failure alerts" card, `automation-alerts-card`): enable toggle, threshold (1–20, default 3), alert email, webhook URL. Endpoints `GET/PUT /api/admin/automation-alerts` (admin-only; threshold clamped).
- Verified (iteration_28): backend 5/5 pytest + frontend 100%, once-per-streak confirmed, zero issues.

## Implemented (2026-06-25, part 5) — automation health summary + home welcome note
- **Admin Overview "Automation health" card** (`automation-health-card`): success-rate % (green/amber/red), total runs, failed runs, and "failing now" (integrations whose latest run failed). Backed by `GET /api/admin/automation-health`; the card only renders when there is at least one run (no clutter otherwise).
- **Home page welcome note**: dismissible glass-neumorphic card centered on the landing page (18px backdrop blur) with the dev-team welcome message; dismissal persists via `localStorage` (`stitches_welcome_dismissed`). Testids `welcome-note-card` / `welcome-note-close`.
- Self-verified: health endpoint returns correct shape; home card renders and is sized to read without overpowering (screenshot confirmed).

## Implemented (2026-06-25) — per-user SMTP, clear-credentials, recurring meetings + week calendar
- **Per-user SMTP sending**: meeting invites are sent from the host's own SMTP account when configured (`send_meeting_email(sender_user_id)` → personal SMTP → falls back to admin SMTP). New user Settings section "Send invites from your own email" (`my-smtp-section`) with save + **Clear credentials**; endpoints `GET/PUT/DELETE /api/me/smtp-config` (password Fernet-encrypted, port parse hardened via `_safe_port`).
- **Explicit "Clear credentials" buttons** in Admin → Meetings for SMTP (`clear-smtp-btn`), SFU/LiveKit (`clear-sfu-btn`) and TURN (`clear-rtc/turn-btn`), wired to `DELETE /api/admin/{smtp,sfu,rtc}-config`.
- **Recurring meetings**: create meeting accepts `recurrence` in {none,daily,weekly}; `/api/meetings/upcoming` expands recurring meetings into occurrences over the next 30 days (`_expand_occurrences`); reminder loop (`scan_meeting_reminders`) is recurrence-aware via a per-occurrence `reminded_occurrences` list; `.ics` includes `RRULE`. Schedule modal has a Repeat selector; Upcoming rows show a recurrence badge.
- **"This week" dashboard calendar** (`WeekCalendar.jsx`, `week-calendar-widget`): Mon–Sun grid, today highlighted, meeting chips click through to the room.
- Verified (iteration_25): backend 8/8 pytest + all frontend flows 100%, zero bugs. NOTE: actual email DELIVERY still needs real SMTP creds (send path skips gracefully); LiveKit SFU media path remains gated OFF (config save/clear only).

## Implemented (2026-06-24, part 3) — perf/polish
- **GitHub release lookup cached** (5-min TTL, in-memory per repo; cache cleared when admin changes the repo) to avoid api.github.com rate limits.
- **Message pagination index**: `messages` now has a compound `(channel_id, created_at)` index for fast cursor pagination at scale.
- **iOS install hint**: `InstallPrompt` now also shows iPhone/iPad users (no `beforeinstallprompt`) a "tap Share → Add to Home Screen" hint when not already installed.
- Verified via curl (cache 0.36s→0.11s) + index confirmed present; frontend compiles clean.

## Implemented (2026-06-24, part 2) — Downloads/CI, delete-avatar, pagination, install banner
- **Desktop downloads wired to real releases**: `GET /api/downloads/release` resolves the latest GitHub release assets (win/.exe, mac/.dmg, linux/.AppImage) for an **admin-editable repo** (`Admin > Integrations > Desktop app releases`, settings key `desktop_release`, env fallback `DESKTOP_RELEASE_REPO`). Downloads buttons link to the matching asset, else the releases page, with a "no installers yet — push a v* tag" hint. CI workflow (`desktop-build.yml`) already publishes releases on `v*` tags.
- **Delete avatar**: `DELETE /api/users/me/avatar` + a "Remove" button in Settings (shown only when an avatar is set).
- **Message pagination**: `GET /api/channels/{id}/messages?limit=&before=` (cursor, newest-first fetch, ascending return); Messages UI has a "Load earlier messages" button + merge-on-poll so history isn't clobbered. `GET /api/users?limit=&skip=&q=` supports bounded/searchable user lists.
- **PWA install banner**: `InstallPrompt` (uses `beforeinstallprompt`) offers a one-tap Install button in-app (Chromium). Dropbox confirmed available as a connector on both user + admin dashboards.
- Verified (iteration_19): 9/9 backend + 100% frontend, zero bugs. (Resend email reminders deferred at user's request.)

## Implemented (2026-06-24) — Mobile client (PWA) + QR cross-device login
- **Installable PWA**: added `public/manifest.json` (standalone, start_url /dashboard, crimson theme), `public/service-worker.js` (app-shell cache, bypasses /api & /ws), SW registration + apple/mobile meta in `index.html`, and generated app icons (`icon-192/512`, `maskable-512`, `apple-touch-icon`). Installs to home screen/dock on phone & desktop with a custom Stitches voodoo-doll icon.
- **Responsive Layout** (`Layout.jsx`): mobile top bar (`mobile-topbar`) + hamburger (`mobile-menu-button`) opens a slide-in nav drawer with backdrop + close button; desktop unchanged. Same full feature set on every device.
- **Downloads page** rebuilt with per-device install QR codes (`mobile-qr-android`, `mobile-qr-ios`, `desktop-qr`) + step-by-step add-to-home-screen instructions, alongside the existing Electron desktop client build section.
- **QR cross-device login**: backend `POST /api/auth/qr/generate` (auth, 3-min single-use token via `qr_tokens` TTL index) + `POST /api/auth/qr/claim` (unauth, atomic find_one_and_update, issues JWT + cookie). Dashboard shows a "Log in on your phone" QR card (`QrLoginCard.jsx`, auto-refresh); scanning opens `/qr-login/claim?token=...` (`QrClaim.jsx`) which auto-signs-in the device and redirects to the dashboard. Continuity via shared backend + existing WebSockets.
- Deps: `qrcode.react`. Verified (iteration_18): 5/5 backend + 100% frontend, zero bugs.
