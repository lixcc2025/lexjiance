// 页面能调用的接口（和 preload、shared/schema.ts 的 Bridge 一一对应）。这里只做参数检查和转发，逻辑在各模块里。

import { app, dialog, ipcMain, nativeTheme, shell } from "electron"
import { existsSync } from "fs"
import type { AppInfo, DetectorInfo, SettingsPatch } from "../../shared/schema"
import { CLOUD_DETECTORS } from "../../shared/cloud-protocol"
import { cancelAnalysis, startAnalysis } from "./analysis"
import { testCloud } from "./cloud"
import { engineJson } from "./engine"
import { allowPath } from "./media-protocol"
import { logDir, PLATFORM, IS_MAC } from "./paths"
import { cacheSize, clearCache, getPreview } from "./preview"
import { getSettings, saveSettings } from "./settings"
import { MEDIA_EXT, mainWindow, refreshTitlebar, TITLEBAR_H } from "./window"

const str = (v: unknown) => typeof v === "string" && v.length > 0 && v.length < 4096

export function applyTheme() {
  nativeTheme.themeSource = getSettings().theme
  refreshTitlebar()
}

export function registerIpc() {
  ipcMain.handle("pick-file", async () => {
    const w = mainWindow()
    const opts = {
      title: "选择要检测的视频或音频",
      properties: ["openFile" as const],
      filters: [{ name: "视频 / 音频", extensions: MEDIA_EXT }, { name: "所有文件", extensions: ["*"] }],
    }
    const r = w ? await dialog.showOpenDialog(w, opts) : await dialog.showOpenDialog(opts)
    return r.canceled ? null : r.filePaths[0]
  })

  ipcMain.handle("analyze", (_e, file: unknown) => {
    if (!str(file)) return { ok: false, error: "文件路径不对" }
    return startAnalysis(file as string, (ev) => mainWindow()?.webContents.send("engine-event", ev))
  })
  ipcMain.handle("cancel", (_e, id: unknown) => { if (str(id)) cancelAnalysis(id as string); return true })

  // 检测项清单 = 本机引擎的 + 云端的
  ipcMain.handle("list-detectors", async (): Promise<DetectorInfo[]> => {
    try {
      const local = await engineJson<DetectorInfo[]>(["detectors", "--json"], 30000)
      return [...local, ...CLOUD_DETECTORS]
    } catch {
      return []
    }
  })

  ipcMain.handle("preview", (_e, file: unknown) => {
    if (!str(file) || !existsSync(file as string)) return null
    allowPath(file as string)
    return getPreview(file as string)
  })

  ipcMain.handle("app-info", async (): Promise<AppInfo> => ({ platform: PLATFORM, version: app.getVersion(), titlebar: IS_MAC ? 0 : TITLEBAR_H }))

  ipcMain.handle("get-settings", () => getSettings())
  ipcMain.handle("save-settings", (_e, patch: SettingsPatch) => {
    const s = saveSettings(patch || {})
    if (patch?.theme) applyTheme()
    return s
  })
  ipcMain.handle("test-cloud", () => testCloud())

  ipcMain.handle("cache-size", () => cacheSize())
  ipcMain.handle("clear-cache", () => clearCache())
  ipcMain.handle("open-logs", () => shell.openPath(logDir()))
  ipcMain.handle("show-in-folder", (_e, p: unknown) => { if (str(p) && existsSync(p as string)) shell.showItemInFolder(p as string) })
  ipcMain.handle("file-exists", (_e, p: unknown) => str(p) && existsSync(p as string))
}
