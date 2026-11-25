// 页面能调用的接口（和 preload、shared/schema.ts 的 Bridge 一一对应）。这里只做参数检查和转发，逻辑在各模块里。
// 问题清单 P2-1：回放白名单只由可信来源写入——
//   打开文件对话框的结果、系统传来的文件（window.ts）、页面传来但确实是音视频文件的（拖进窗口、检测记录里重新打开）。
//   预览只给已经在白名单里的文件生成；file-exists 只回答音视频文件，不能拿来探测任意路径。

import { app, dialog, ipcMain, nativeTheme, shell } from "electron"
import type { AppInfo, DetectorInfo, SettingsPatch } from "../../shared/schema"
import { CLOUD_DETECTORS } from "../../shared/cloud-protocol"
import { isMediaFile, MEDIA_EXT } from "./access"
import { cancelAnalysis, startAnalysis } from "./analysis"
import { testCloud } from "./cloud"
import { engineJson } from "./engine"
import { access } from "./media-protocol"
import { clearLogs, log } from "./log"
import { logDir, PLATFORM, IS_MAC } from "./paths"
import { cacheSize, clearCache, getPreview } from "./preview"
import { getSettings, saveSettings } from "./settings"
import { mainWindow, markRendererReady, refreshTitlebar, TITLEBAR_H } from "./window"

const str = (v: unknown): v is string => typeof v === "string" && v.length > 0 && v.length < 4096

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
    if (r.canceled || !r.filePaths[0]) return null
    if (!access.allowMedia(r.filePaths[0])) {
      dialog.showMessageBox(w!, { type: "warning", message: "不支持这种文件", detail: "请选择视频或音频文件（" + MEDIA_EXT.join("、") + "）" })
      return null
    }
    return r.filePaths[0]
  })

  ipcMain.handle("analyze", (_e, file: unknown) => {
    if (!access.allowMedia(file)) return { ok: false, error: "不是支持的音视频文件，或文件已不存在" }
    return startAnalysis(file as string, (ev) => mainWindow()?.webContents.send("engine-event", ev))
  })
  ipcMain.handle("cancel", (_e, id: unknown) => { if (str(id)) cancelAnalysis(id); return true })

  // 检测项清单 = 本机引擎的 + 云端的
  ipcMain.handle("list-detectors", async (): Promise<DetectorInfo[]> => {
    try {
      const local = await engineJson<DetectorInfo[]>(["detectors", "--json"], 30000)
      return [...local, ...CLOUD_DETECTORS]
    } catch (e) {
      log.error("取检测项清单失败（检测引擎可能没装好）", e)
      return []
    }
  })

  ipcMain.handle("preview", (_e, file: unknown) => {
    if (!str(file) || !access.isAllowed(file)) return null
    return getPreview(file)
  })

  ipcMain.handle("app-info", async (): Promise<AppInfo> => ({ platform: PLATFORM, version: app.getVersion(), titlebar: IS_MAC ? 0 : TITLEBAR_H }))

  ipcMain.handle("get-settings", () => getSettings())
  ipcMain.handle("save-settings", (_e, patch: SettingsPatch) => {
    const s = saveSettings(patch && typeof patch === "object" ? patch : {})
    if (patch?.theme) applyTheme()
    return s
  })
  ipcMain.handle("test-cloud", () => testCloud())

  ipcMain.handle("cache-size", () => cacheSize())
  ipcMain.handle("clear-cache", () => clearCache())
  ipcMain.handle("open-logs", () => shell.openPath(logDir()))
  ipcMain.handle("clear-logs", () => clearLogs())
  ipcMain.handle("show-in-folder", (_e, p: unknown) => { if (str(p) && access.isAllowed(p)) shell.showItemInFolder(p) })
  ipcMain.handle("file-exists", (_e, p: unknown) => isMediaFile(p))
  ipcMain.on("renderer-ready", () => markRendererReady())
}
