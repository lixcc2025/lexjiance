// 主进程入口：只负责启动顺序和生命周期，具体功能在各模块：
//   paths 文件位置 · log 日志 · settings 设置 · engine 调引擎 · analysis 一次检测 · cloud 云端识别
//   preview 预览素材 · media-protocol 本地回放 · window 窗口 · menu 菜单 · ipc 页面接口
// 全程离线：文件不上传（启用云端识别时只传提取的音轨和抽帧，见 cloud.ts）。

import { app } from "electron"
import { applyTheme, registerIpc } from "./ipc"
import { log } from "./log"
import { handleMediaProtocol, registerMediaScheme } from "./media-protocol"
import { setupMenu } from "./menu"
import { cancelAll } from "./analysis"
import { sweepExtracts } from "./cloud"
import { trimCache } from "./preview"
import { createMainWindow, mainWindow, mediaArg, openFileInWindow } from "./window"

// 只开一个窗口：再次打开（比如双击另一个视频）时把文件交给已经开着的窗口
if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  registerMediaScheme()

  app.on("second-instance", (_e, argv) => {
    const w = mainWindow()
    if (!w) return
    const f = mediaArg(argv)
    if (f) openFileInWindow(f)
    else { if (w.isMinimized()) w.restore(); w.focus() }
  })

  // macOS：拖到 Dock 图标上
  app.on("open-file", (e, path) => { e.preventDefault(); openFileInWindow(path) })

  app.whenReady().then(() => {
    log.info("启动", { version: app.getVersion(), platform: process.platform, packaged: app.isPackaged })
    if (process.platform === "win32") app.setAppUserModelId("com.avdetect.desktop")
    // 上次崩溃或被强杀留下的上传素材（音轨、截图）：启动时清掉（问题清单 P2-3）；预览缓存按容量 / 时间清理
    sweepExtracts()
    void trimCache()
    handleMediaProtocol()
    registerIpc()
    applyTheme()
    setupMenu()
    createMainWindow()
  })

  app.on("window-all-closed", () => {
    cancelAll()
    app.quit()
  })

  // 退出前同步清理上传素材（异步的 finally 可能来不及跑）
  app.on("will-quit", () => {
    cancelAll()
    try { sweepExtracts() } catch { /* 下次启动再清 */ }
  })

  process.on("uncaughtException", (e) => log.error("未捕获的异常", e))
}
