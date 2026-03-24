const { app, BrowserWindow, dialog } = require("electron");
const { spawn } = require("child_process");
const path = require("path");
const fs = require("fs");

const BACKEND_URL = "http://127.0.0.1:8000/health";
const isDev = !app.isPackaged;
const DEV_ORIGIN = "http://localhost:5173";

let backendProcess = null;

function projectRoot() {
  return path.resolve(__dirname, "..", "..");
}

function resolveAppIcon() {
  if (isDev) {
    const devIcon = path.join(projectRoot(), "assets", "icon.png");
    return fs.existsSync(devIcon) ? devIcon : undefined;
  }
  const packagedIcon = path.join(process.resourcesPath, "icon.png");
  return fs.existsSync(packagedIcon) ? packagedIcon : undefined;
}

function spawnBackend() {
  if (backendProcess) {
    return;
  }

  if (app.isPackaged) {
    const exePath = path.join(process.resourcesPath, "backend", "CricAnalystApi.exe");
    backendProcess = spawn(exePath, [], {
      cwd: process.resourcesPath,
      windowsHide: true
    });
  } else {
    const pyPath = path.join(projectRoot(), ".venv", "Scripts", "python.exe");
    const backendEntry = path.join(projectRoot(), "run_backend.py");
    backendProcess = spawn(pyPath, [backendEntry], {
      cwd: projectRoot(),
      windowsHide: true
    });
  }

  if (backendProcess && backendProcess.stdout) {
    backendProcess.stdout.on("data", (buf) => {
      process.stdout.write(`[backend] ${buf.toString()}`);
    });
  }
  if (backendProcess && backendProcess.stderr) {
    backendProcess.stderr.on("data", (buf) => {
      process.stderr.write(`[backend] ${buf.toString()}`);
    });
  }
}

function stopBackend() {
  if (!backendProcess) {
    return;
  }
  backendProcess.kill();
  backendProcess = null;
}

async function waitForBackend(maxAttempts = 60, delayMs = 500) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    try {
      const response = await fetch(BACKEND_URL);
      if (response.ok) {
        return;
      }
    } catch (err) {
      // Retry until backend is ready.
    }
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
  throw new Error("Backend did not become ready in time.");
}

async function createMainWindow() {
  const mainWindow = new BrowserWindow({
    width: 1500,
    height: 1020,
    minWidth: 1200,
    minHeight: 860,
    backgroundColor: "#060a14",
    icon: resolveAppIcon(),
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      devTools: isDev
    }
  });

  // Prevent unexpected popup windows from untrusted content.
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: "deny" }));

  // Allow only the expected app origin in dev and the local file in production.
  mainWindow.webContents.on("will-navigate", (event, url) => {
    const allowed = isDev ? url.startsWith(DEV_ORIGIN) : url.startsWith("file://");
    if (!allowed) {
      event.preventDefault();
    }
  });

  if (isDev) {
    await mainWindow.loadURL(DEV_ORIGIN);
    mainWindow.webContents.openDevTools({ mode: "detach" });
    return;
  }

  await mainWindow.loadFile(path.join(__dirname, "..", "dist", "index.html"));
}

app.whenReady().then(async () => {
  try {
    app.setAppUserModelId("com.cricanalyst.desktop");
    spawnBackend();
    await waitForBackend();
    await createMainWindow();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    dialog.showErrorBox("Startup Error", `Unable to start CricAnalyst backend.\n\n${message}`);
    app.quit();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    stopBackend();
    app.quit();
  }
});

app.on("before-quit", () => {
  stopBackend();
});

app.on("activate", async () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    await createMainWindow();
  }
});
