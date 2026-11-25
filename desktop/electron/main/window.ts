// 主窗口。
// macOS：标题栏融进窗口、红绿灯嵌在侧栏上，侧栏用系统半透明材质
// Windows：自绘标题栏，最小化 / 最大化 / 关闭用系统的「窗口控件覆盖」（titleBarOverlay），颜色跟主题走

import { app, BrowserWindow, nativeTheme, screen } from "electron"
import { existsSync, writeFileSync } from "fs"
import { resolve } from "path"
import { IS_MAC, preloadPath, rendererIndex } from "./paths"
import { log } from "./log"

export const TITLEBAR_H = 40
export const MEDIA_EXT = ["mp4", "mov", "m4v", "avi", "mkv", "webm", "3gp", "flv", "ts", "mp3", "wav", "m4a", "aac", "amr", "flac", "ogg", "opus", "wma"]

let win: BrowserWindow | null = null
export const mainWindow = () => (win && !win.isDestroyed() ? win : null)

function overlayColors() {
  return nativeTheme.shouldUseDarkColors ? { color: "#161920", symbolColor: "#aab2c2" } : { color: "#ffffff", symbolColor: "#4b5466" }
}

export function refreshTitlebar() {
  const w = mainWindow()
  if (!IS_MAC && w) {
    try { w.setTitleBarOverlay({ ...overlayColors(), height: TITLEBAR_H }) } catch { /* 系统不支持就算了 */ }
  }
}

// 命令行里的媒体文件（「打开方式」、拖到程序图标上、第二个实例转过来的）
export function mediaArg(argv: string[]): string | null {
  const f = argv.slice(1).reverse().find((a) => !a.startsWith("-") && MEDIA_EXT.some((x) => a.toLowerCase().endsWith("." + x)) && existsSync(a))
  return f ? resolve(f) : null
}

export function openFileInWindow(path: string) {
  const w = mainWindow()
  if (!w) return
  if (w.isMinimized()) w.restore()
  w.focus()
  w.webContents.send("open-file", path)
}

export function createMainWindow(): BrowserWindow {
  // 初始大小按屏幕可用区域算；最小 940×560：1366×768 开 125% 缩放、去掉任务栏约 1093×580 也放得下
  const wa = screen.getPrimaryDisplay().workAreaSize
  const fixed = !app.isPackaged && /^(\d+)x(\d+)$/.exec(process.env.AVD_WINDOW_SIZE || "") // 开发用：固定窗口大小检查小屏布局
  win = new BrowserWindow({
    width: fixed ? Number(fixed[1]) : Math.min(1360, Math.round(wa.width * 0.94)),
    height: fixed ? Number(fixed[2]) : Math.min(860, Math.round(wa.height * 0.94)),
    ...(fixed ? { x: 0, y: 0 } : {}),
    minWidth: 940,
    minHeight: 560,
    title: "音视频检测",
    show: false,
    ...(IS_MAC
      ? { titleBarStyle: "hiddenInset" as const, trafficLightPosition: { x: 18, y: 20 }, vibrancy: "sidebar" as const, visualEffectState: "active" as const, backgroundColor: "#00000000" }
      : { titleBarStyle: "hidden" as const, titleBarOverlay: { ...overlayColors(), height: TITLEBAR_H }, backgroundColor: nativeTheme.shouldUseDarkColors ? "#0f1115" : "#f5f6f8" }),
    webPreferences: { preload: preloadPath(), contextIsolation: true, nodeIntegration: false, sandbox: true },
  })
  win.once("ready-to-show", () => win?.show())
  // 不允许页面打开新窗口或跳到外部网址
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }))
  win.webContents.on("will-navigate", (e, url) => { if (!url.startsWith("file:") && !url.startsWith(process.env.ELECTRON_RENDERER_URL || "\0")) e.preventDefault() })
  win.webContents.on("render-process-gone", (_e, d) => log.error("页面进程退出", d))

  const arg = mediaArg(process.argv)
  if (arg) win.webContents.once("did-finish-load", () => win?.webContents.send("open-file", arg))
  devSnapshot(win)

  if (process.env.ELECTRON_RENDERER_URL) win.loadURL(process.env.ELECTRON_RENDERER_URL)
  else win.loadFile(rendererIndex())
  return win
}

// 开发用截图（打包版不生效）：AVD_SNAPSHOT=输出.png，AVD_SNAPSHOT_DELAY=毫秒，AVD_SNAPSHOT_JS=截图前在页面里执行的脚本
function devSnapshot(w: BrowserWindow) {
  if (app.isPackaged || !process.env.AVD_SNAPSHOT) return
  const out = process.env.AVD_SNAPSHOT
  w.webContents.once("did-finish-load", () => {
    setTimeout(async () => {
      try {
        if (process.env.AVD_SNAPSHOT_JS) await w.webContents.executeJavaScript(process.env.AVD_SNAPSHOT_JS, true)
        await new Promise((r) => setTimeout(r, Number(process.env.AVD_SNAPSHOT_AFTER_JS || 800)))
        writeFileSync(out, (await w.webContents.capturePage()).toPNG())
      } catch (e) {
        console.error("snapshot failed", e)
      }
      if (process.env.AVD_SNAPSHOT_QUIT !== "0") app.quit()
    }, Number(process.env.AVD_SNAPSHOT_DELAY || 4000))
  })
}
