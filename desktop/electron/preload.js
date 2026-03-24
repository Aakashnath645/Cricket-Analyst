const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("cricanalystDesktop", {
  runtime: {
    platform: process.platform,
    electron: process.versions.electron
  }
});

