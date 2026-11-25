import { contextBridge, ipcRenderer, webUtils } from "electron"

contextBridge.exposeInMainWorld("avd", {
  pickFile: (): Promise<string | null> => ipcRenderer.invoke("pick-file"),
  // 拖进窗口的文件取本机路径
  pathOf: (file: File): string => webUtils.getPathForFile(file),
  analyze: (file: string): Promise<{ ok: boolean; job?: string; error?: string }> => ipcRenderer.invoke("analyze", file),
  cancel: (job: string): Promise<boolean> => ipcRenderer.invoke("cancel", job),
  listDetectors: (): Promise<any[]> => ipcRenderer.invoke("list-detectors"),
  preview: (path: string): Promise<any> => ipcRenderer.invoke("preview", path),
  setTheme: (t: string): Promise<void> => ipcRenderer.invoke("set-theme", t),
  appInfo: (): Promise<{ platform: string; version: string }> => ipcRenderer.invoke("app-info"),
  onMenu: (cb: (cmd: string) => void) => ipcRenderer.on("menu", (_e, c: string) => cb(c)),
  showInFolder: (path: string): Promise<void> => ipcRenderer.invoke("show-in-folder", path),
  fileExists: (path: string): Promise<boolean> => ipcRenderer.invoke("file-exists", path),
  onOpenFile: (cb: (path: string) => void) => ipcRenderer.on("open-file", (_e, p: string) => cb(p)),
  onEvent: (cb: (ev: any) => void) => {
    const fn = (_e: unknown, ev: any) => cb(ev)
    ipcRenderer.on("engine-event", fn)
    return () => ipcRenderer.removeListener("engine-event", fn)
  },
})
