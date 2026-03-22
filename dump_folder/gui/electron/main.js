const path = require("path");
const { app, BrowserWindow, dialog, ipcMain, shell } = require("electron");

const { collectManifestFromSelection, generateDump, FORMAT_EXTENSIONS } = require("./src/dump-engine");
const { loadSettings, saveSettings } = require("./src/settings-store");
const { listDirectory, inspectPath } = require("./src/fs-service");

function createWindow() {
  const settings = loadSettings(app);
  const bounds = settings.windowBounds || {};

  const win = new BrowserWindow({
    width: bounds.width || 1220,
    height: bounds.height || 760,
    minWidth: 1160,
    minHeight: 700,
    backgroundColor: "#f3efe7",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (bounds.x !== undefined && bounds.y !== undefined) {
    win.setPosition(bounds.x, bounds.y);
  }

  win.on("close", () => {
    saveSettings(app, { windowBounds: win.getBounds() }, { merge: true });
  });

  win.loadFile(path.join(__dirname, "renderer", "index.html"));
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

ipcMain.handle("dialog:chooseRoot", async (_event, initialPath) => {
  const result = await dialog.showOpenDialog({
    title: "Seleziona root di lavoro",
    defaultPath: initialPath || undefined,
    properties: ["openDirectory"],
  });
  if (result.canceled || !result.filePaths.length) {
    return null;
  }
  return inspectPath(result.filePaths[0]);
});

ipcMain.handle("dialog:selectOutput", async (_event, payload) => {
  const format = payload?.format || "txt";
  const extension = FORMAT_EXTENSIONS[format] || ".txt";
  const result = await dialog.showSaveDialog({
    title: "Seleziona output",
    defaultPath: payload?.initialPath || payload?.initialDir || `dump${extension}`,
    filters: [
      { name: "Text", extensions: ["txt"] },
      { name: "Markdown", extensions: ["md"] },
      { name: "HTML", extensions: ["html"] },
    ],
  });
  if (result.canceled || !result.filePath) {
    return null;
  }
  const parsed = path.parse(result.filePath);
  return path.join(parsed.dir, `${parsed.name}${extension}`);
});

ipcMain.handle("fs:getNode", async (_event, nodePath, parentId = null) => inspectPath(nodePath, parentId));
ipcMain.handle("fs:listDirectory", async (_event, nodePath) => listDirectory(nodePath));
ipcMain.handle("shell:openPath", async (_event, nodePath) => {
  const error = await shell.openPath(nodePath);
  return { ok: !error, error: error || null };
});
ipcMain.handle("dump:getSummary", async (_event, payload) =>
  collectManifestFromSelection(payload.selection, payload.outputPath, payload.format),
);
ipcMain.handle("dump:generate", async (_event, payload) =>
  generateDump(payload.selection, payload.outputPath, payload.format),
);
ipcMain.handle("settings:load", async () => loadSettings(app));
ipcMain.handle("settings:save", async (_event, partialSettings) => {
  saveSettings(app, partialSettings, { merge: true });
  return true;
});
