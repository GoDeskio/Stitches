# Stitches Desktop Client

A lightweight [Electron](https://www.electronjs.org/) client that opens straight into your
**Stitches dashboard** and stays connected to your online account. It has all the same tools
and features as the web app (messages, threads, projects, assets, integrations, AI) — your data
lives online and stays in sync.

## Run in development

```bash
cd desktop
npm install
npm start
```

## Build installers

```bash
npm run dist          # current platform
npm run dist:win      # Windows  .exe (NSIS)
npm run dist:mac      # macOS    .dmg
npm run dist:linux    # Linux    .AppImage
```

Installers are written to `desktop/dist/`.

## Configuration

The client connects to the dashboard URL in the `STITCHES_URL` environment variable and
defaults to the current deployment. To point it at a different deployment:

```bash
STITCHES_URL="https://your-stitches-domain.com" npm start
```

## How it works

- Loads `${STITCHES_URL}/dashboard`; if you're not signed in, the app redirects you to login.
- Uses a **persistent Electron session** (`persist:stitches`) so your login survives restarts.
- Keeps in-app navigation inside the window and opens external links in your system browser.
