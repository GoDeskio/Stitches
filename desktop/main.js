const { app, BrowserWindow, shell, session } = require("electron");

// The live Stitches dashboard this client connects to.
const STITCHES_URL = process.env.STITCHES_URL || "https://stitches-connect.preview.emergentagent.com";

function createWindow() {
  // Use a persistent session partition so login (cookies + storage) survives restarts.
  const persistentSession = session.fromPartition("persist:stitches");

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

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
