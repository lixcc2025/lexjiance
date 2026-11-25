// 给页面的接口（window.avd），类型见 shared/schema.ts 的 Bridge。页面拿不到 Node 和 Electron 本身
import { contextBridge, ipcRenderer, webUtils } from "electron"
import type { Bridge, EngineEvent } from "../../shared/schema"

const api: Bridge = {
  pickFile: () => ipcRenderer.invoke("pick-file"),
  pathOf: (file) => webUtils.getPathForFile(file), // 拖进窗口的文件取本机路径
  analyze: (file) => ipcRenderer.invoke("analyze", file),
  cancel: (job) => ipcRenderer.invoke("cancel", job),
  listDetectors: () => ipcRenderer.invoke("list-detectors"),
  preview: (path) => ipcRenderer.invoke("preview", path),
  appInfo: () => ipcRenderer.invoke("app-info"),
  getSettings: () => ipcRenderer.invoke("get-settings"),
  saveSettings: (patch) => ipcRenderer.invoke("save-settings", patch),
  testCloud: () => ipcRenderer.invoke("test-cloud"),
  cacheSize: () => ipcRenderer.invoke("cache-size"),
  clearCache: () => ipcRenderer.invoke("clear-cache"),
  openLogs: () => ipcRenderer.invoke("open-logs"),
  showInFolder: (path) => ipcRenderer.invoke("show-in-folder", path),
  fileExists: (path) => ipcRenderer.invoke("file-exists", path),
  onOpenFile: (cb) => { ipcRenderer.on("open-file", (_e, p: string) => cb(p)) },
  onMenu: (cb) => { ipcRenderer.on("menu", (_e, c: string) => cb(c)) },
  onEvent: (cb) => {
    const fn = (_e: unknown, ev: EngineEvent) => cb(ev)
    ipcRenderer.on("engine-event", fn)
    return () => { ipcRenderer.removeListener("engine-event", fn) }
  },
}

contextBridge.exposeInMainWorld("avd", api)
