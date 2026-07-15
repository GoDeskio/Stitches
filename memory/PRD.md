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

## Backlog / Next
- P1: Reply threads + @mentions with mention notifications in channels.
- P1: Actually invoke connected integrations (trigger N8N workflows, pull files from connected cloud storage) — currently placeholder catalogs.
- P2: Dynamic UI text-size / accessibility scaling control (theme toggle already exists).
- P2: Split server.py (~1460 lines) into routers; split Messages.jsx; use async HTTP client for storage.
- P2: Avatar image upload (currently URL field); project task boards (kanban).
