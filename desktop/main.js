const { app, BrowserWindow, shell, session, desktopCapturer, Menu, Tray, nativeImage } = require("electron");

// The live Stitches dashboard this client connects to.
const STITCHES_URL = process.env.STITCHES_URL || "https://stitches-connect.preview.emergentagent.com";

let tray = null;

function wireMediaPermissions(ses) {
  // Grant camera / microphone / screen-share to the trusted Stitches origin so
  // WebRTC audio/video meetings work in the desktop client (they do in the web app).
  const allow = new Set(["media", "display-capture", "notifications", "clipboard-read", "clipboard-sanitized-write"]);
  ses.setPermissionRequestHandler((wc, permission, callback) => {
    callback(allow.has(permission));
  });
  ses.setPermissionCheckHandler((wc, permission) => allow.has(permission));

  // Screen sharing: answer getDisplayMedia() with the primary screen source.
  if (ses.setDisplayMediaRequestHandler) {
    ses.setDisplayMediaRequestHandler((request, callback) => {
      desktopCapturer.getSources({ types: ["screen", "window"] }).then((sources) => {
        callback({ video: sources[0], audio: "loopback" });
      }).catch(() => callback({}));
    });
  }
}

function createWindow() {
  // Use a persistent session partition so login (cookies + storage) survives restarts.
  const persistentSession = session.fromPartition("persist:stitches");
  wireMediaPermissions(persistentSession);

  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    backgroundColor: "#1a0d10",
    title: "Stitches",
    autoHideMenuBar: true,
    webPreferences: {
      partition: "persist:stitches",
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Open straight into the dashboard; the app redirects to /login if not signed in.
  win.loadURL(`${STITCHES_URL}/dashboard`);

  // Keep in-app navigation inside the window; open external links in the OS browser.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith(STITCHES_URL)) return { action: "allow" };
    shell.openExternal(url);
    return { action: "deny" };
  });

  win.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith(STITCHES_URL)) {
      event.preventDefault();
      shell.openExternal(url);
    }
  });

  return win;
}

function createTray(win) {
  try {
    tray = new Tray(nativeImage.createEmpty());
    tray.setToolTip("Stitches");
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: "Open Stitches", click: () => { win.show(); win.focus(); } },
      { type: "separator" },
      { label: "Quit", click: () => app.quit() },
    ]));
    tray.on("click", () => { win.show(); win.focus(); });
  } catch (_) { /* tray is optional */ }
}

app.whenReady().then(() => {
  const win = createWindow();
  createTray(win);
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
