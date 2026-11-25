// 主窗口。
// macOS：标题栏融进窗口、红绿灯嵌在侧栏上，侧栏用系统半透明材质
// Windows：自绘标题栏，最小化 / 最大化 / 关闭用系统的「窗口控件覆盖」（titleBarOverlay），颜色跟主题走
// 安全（问题清单 P2-2）：只允许停留在我们自己的页面（打包后的 index.html 或开发服务器同源），拒绝新窗口和一切权限请求。
// 启动时带的文件（打开方式）：等页面说「准备好了」再交过去，免得页面还没挂监听就丢了。

import { app, BrowserWindow, nativeTheme, screen, session } from "electron"
import { writeFileSync } from "fs"
import { resolve } from "path"
import { pathToFileURL } from "url"
import { isMediaFile } from "./access"
import { access } from "./media-protocol"
import { IS_MAC, preloadPath, rendererIndex } from "./paths"
import { log } from "./log"

export const TITLEBAR_H = 40
export { MEDIA_EXT } from "./access"

let win: BrowserWindow | null = null
let rendererReady = false
let pendingFile: string | null = null
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
  const f = argv.slice(1).reverse().find((a) => !a.startsWith("-") && isMediaFile(resolve(a)))
  return f ? resolve(f) : null
}

// 系统交来的文件（可信来源）：加进回放白名单，交给页面；页面还没准备好就先存着
export function openFileInWindow(path: string) {
  if (!access.allowMedia(path)) return
  const w = mainWindow()
  if (!w || !rendererReady) { pendingFile = path; return }
  if (w.isMinimized()) w.restore()
  w.focus()
  w.webContents.send("open-file", path)
}

export function markRendererReady() {
  rendererReady = true
  if (pendingFile) { const f = pendingFile; pendingFile = null; openFileInWindow(f) }
}

function isOwnUrl(url: string): boolean {
  try {
    if (process.env.ELECTRON_RENDERER_URL) return new URL(url).origin === new URL(process.env.ELECTRON_RENDERER_URL).origin
    return url.split("#")[0] === pathToFileURL(rendererIndex()).href
  } catch {
    return false
  }
}

export function createMainWindow(): BrowserWindow {
  // 初始大小按屏幕可用区域算；最小 940×560：1366×768 开 125% 缩放、去掉任务栏约 1093×580 也放得下
  const wa = screen.getPrimaryDisplay().workAreaSize
  const fixed = !app.isPackaged && /^(\d+)x(\d+)$/.exec(process.env.AVD_WINDOW_SIZE || "") // 开发用：固定窗口大小检查小屏布局
  rendererReady = false
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
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }))
  win.webContents.on("will-navigate", (e, url) => { if (!isOwnUrl(url)) { e.preventDefault(); log.warn("拦截了页面跳转") } })
  win.webContents.on("will-redirect", (e, url) => { if (!isOwnUrl(url)) e.preventDefault() })
  win.webContents.on("render-process-gone", (_e, d) => log.error("页面进程退出", d))
  // 摄像头、麦克风、通知、地理位置……一律不给
  session.defaultSession.setPermissionRequestHandler((_wc, _perm, cb) => cb(false))
  session.defaultSession.setPermissionCheckHandler(() => false)

  const arg = mediaArg(process.argv)
  if (arg) openFileInWindow(arg)
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
