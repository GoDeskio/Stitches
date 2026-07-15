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

## Backlog / Next
- P1: Direct messages (1:1), workspace member invites, message edit/delete + typing indicators.
- P1: Actually invoke connected integrations (trigger N8N workflows, pull files from connected cloud storage).
- P2: Notifications, presence/online status, project task boards (kanban).
- P2: Split server.py into routers; use async HTTP client for storage; unique per-item data-testids.
- P2: Avatar image upload (currently URL field).
