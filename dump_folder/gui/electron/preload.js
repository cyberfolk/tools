const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("dumpBuilderApi", {
  chooseRoot: (initialPath) => ipcRenderer.invoke("dialog:chooseRoot", initialPath),
  selectOutput: (payload) => ipcRenderer.invoke("dialog:selectOutput", payload),
  getNode: (nodePath, parentId) => ipcRenderer.invoke("fs:getNode", nodePath, parentId),
  listDirectory: (nodePath) => ipcRenderer.invoke("fs:listDirectory", nodePath),
  openPath: (nodePath) => ipcRenderer.invoke("shell:openPath", nodePath),
  getSummary: (payload) => ipcRenderer.invoke("dump:getSummary", payload),
  generateDump: (payload) => ipcRenderer.invoke("dump:generate", payload),
  loadSettings: () => ipcRenderer.invoke("settings:load"),
  saveSettings: (settings) => ipcRenderer.invoke("settings:save", settings),
});
