// 主进程：窗口、选文件、调检测引擎（Python 子进程，逐行 JSON 事件）、本地媒体回放协议。
// 全程离线：文件不上传，引擎在本机跑（法院、检察院多在内网）。
import { app, BrowserWindow, dialog, ipcMain, Menu, nativeTheme, protocol, screen, shell } from "electron"
import { spawn, execFile, ChildProcess } from "child_process"
import { createReadStream, existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "fs"
import { createHash } from "crypto"
import { Readable } from "stream"
import { extname, join, resolve } from "path"

const MEDIA_EXT = ["mp4", "mov", "m4v", "avi", "mkv", "webm", "3gp", "flv", "ts", "mp3", "wav", "m4a", "aac", "amr", "flac", "ogg", "opus", "wma"]

// 回放用的协议：渲染进程用 media://file/<编码后的本机路径> 播放被检测的文件，不放开 file://。
// 要注册成 standard，Chromium 的媒体管线才会对它发分段请求
protocol.registerSchemesAsPrivileged([{ scheme: "media", privileges: { standard: true, secure: true, stream: true, supportFetchAPI: true, bypassCSP: true } }])

let win: BrowserWindow | null = null
const jobs = new Map<string, ChildProcess>()

// 引擎位置：打包后在 resources/engine，Python 在 resources/python（打包脚本以后补）；开发时用仓库里的 engine 和系统 Python
function engineCommand(): { cmd: string; cwd: string } {
  if (app.isPackaged) {
    const res = process.resourcesPath
    const py = process.platform === "win32" ? join(res, "python", "python.exe") : join(res, "python", "bin", "python3")
    return { cmd: py, cwd: join(res, "engine") }
  }
  const cwd = resolve(__dirname, "../../../engine")
  const cmd = process.env.AVENGINE_PYTHON || (process.platform === "win32" ? "python" : "python3")
  return { cmd, cwd }
}

// 平台：开发时可用 AVD_PLATFORM=win32 在别的系统上模拟 Windows 的窗口样式（云端截图检查用）
const PLATFORM = (!app.isPackaged && process.env.AVD_PLATFORM) || process.platform
const IS_MAC = PLATFORM === "darwin"
const TITLEBAR_H = 40 // Windows 标题栏高度（右上角系统按钮的高度）

// Windows 右上角的最小化 / 最大化 / 关闭按钮由系统画，颜色跟主题走
function overlayColors() {
  return nativeTheme.shouldUseDarkColors ? { color: "#161920", symbolColor: "#aab2c2" } : { color: "#ffffff", symbolColor: "#4b5466" }
}

function createWindow() {
  // 初始大小按屏幕可用区域算：1366×768 笔记本、1920×1080 开 150% 缩放（实际 1280×720）也放得下
  // 1366×768 开 125% 缩放、去掉任务栏只剩约 1093×580，最小尺寸按这个定
  const wa = screen.getPrimaryDisplay().workAreaSize
  const fixed = !app.isPackaged && /^(\d+)x(\d+)$/.exec(process.env.AVD_WINDOW_SIZE || "") // 开发用：固定窗口大小检查小屏布局
  win = new BrowserWindow({
    width: fixed ? Number(fixed[1]) : Math.min(1360, Math.round(wa.width * 0.94)),
    height: fixed ? Number(fixed[2]) : Math.min(860, Math.round(wa.height * 0.94)),
    ...(fixed ? { x: 0, y: 0 } : {}),
    minWidth: 940,
    minHeight: 560,
    title: "音视频检测",
    // macOS：标题栏融进窗口、红绿灯嵌在侧栏上，侧栏用系统半透明材质
    // Windows：自绘标题栏，系统按钮用「窗口控件覆盖」嵌在右上角
    ...(IS_MAC
      ? { titleBarStyle: "hiddenInset" as const, trafficLightPosition: { x: 18, y: 20 }, vibrancy: "sidebar" as const, visualEffectState: "active" as const, backgroundColor: "#00000000" }
      : { titleBarStyle: "hidden" as const, titleBarOverlay: { ...overlayColors(), height: TITLEBAR_H }, backgroundColor: nativeTheme.shouldUseDarkColors ? "#0f1115" : "#f5f6f8" }),
    webPreferences: {
      preload: join(__dirname, "../preload/index.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  // 用「打开方式」或命令行带文件启动：页面加载完直接开始检测
  const argFile = process.argv.slice(1).reverse().find((a) => !a.startsWith("-") && MEDIA_EXT.some((x) => a.toLowerCase().endsWith("." + x)) && existsSync(a))
  if (argFile) win.webContents.once("did-finish-load", () => win?.webContents.send("open-file", resolve(argFile)))
  // 开发用截图（打包版不生效）：AVD_SNAPSHOT=输出.png，AVD_SNAPSHOT_DELAY=毫秒，AVD_SNAPSHOT_JS=截图前在页面里执行的脚本
  if (!app.isPackaged && process.env.AVD_SNAPSHOT) {
    const out = process.env.AVD_SNAPSHOT
    win.webContents.once("did-finish-load", () => {
      setTimeout(async () => {
        try {
          if (process.env.AVD_SNAPSHOT_JS) await win?.webContents.executeJavaScript(process.env.AVD_SNAPSHOT_JS, true)
          await new Promise((r) => setTimeout(r, Number(process.env.AVD_SNAPSHOT_AFTER_JS || 800)))
          const img = await win!.webContents.capturePage()
          writeFileSync(out, img.toPNG())
        } catch (e) {
          console.error("snapshot failed", e)
        }
        if (process.env.AVD_SNAPSHOT_QUIT !== "0") app.quit()
      }, Number(process.env.AVD_SNAPSHOT_DELAY || 4000))
    })
  }
  if (process.env.ELECTRON_RENDERER_URL) win.loadURL(process.env.ELECTRON_RENDERER_URL)
  else win.loadFile(join(__dirname, "../renderer/index.html"))
}

ipcMain.handle("pick-file", async () => {
  const r = await dialog.showOpenDialog(win!, {
    title: "选择要检测的视频或音频",
    properties: ["openFile"],
    filters: [{ name: "视频 / 音频", extensions: MEDIA_EXT }, { name: "所有文件", extensions: ["*"] }],
  })
  return r.canceled ? null : r.filePaths[0]
})

// 开始检测：返回任务号；事件通过 engine-event 推给渲染进程
ipcMain.handle("analyze", (_e, file: string) => {
  if (typeof file !== "string" || !existsSync(file)) return { ok: false, error: "文件不存在" }
  allow(file)
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
  const { cmd, cwd } = engineCommand()
  const child = spawn(cmd, ["-m", "avengine", "analyze", file, "--jsonl"], {
    cwd,
    env: { ...process.env, PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
    windowsHide: true,
  })
  jobs.set(id, child)
  const send = (ev: Record<string, unknown>) => win?.webContents.send("engine-event", { job: id, ...ev })
  let buf = ""
  let stderr = ""
  let gotResult = false
  child.stdout.setEncoding("utf8")
  child.stdout.on("data", (chunk: string) => {
    buf += chunk
    let i: number
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 1)
      if (!line) continue
      try {
        const ev = JSON.parse(line)
        if (ev.type === "result" || ev.type === "error") gotResult = true
        send(ev)
      } catch {
        /* 非 JSON 行忽略 */
      }
    }
  })
  child.stderr.setEncoding("utf8")
  child.stderr.on("data", (c: string) => { stderr = (stderr + c).slice(-4000) })
  child.on("error", (err) => { gotResult = true; send({ type: "error", message: "检测引擎启动失败：" + err.message }) })
  child.on("close", (code) => {
    jobs.delete(id)
    if (!gotResult) send({ type: "error", message: code === null ? "检测已取消" : `检测引擎异常退出（${code}）：${stderr.slice(-500)}` })
  })
  return { ok: true, job: id }
})

// 检测项清单（界面上的进度步骤用）
ipcMain.handle("list-detectors", () => new Promise((res) => {
  const { cmd, cwd } = engineCommand()
  execFile(cmd, ["-m", "avengine", "detectors", "--json"], { cwd, windowsHide: true, timeout: 20000, env: { ...process.env, PYTHONUTF8: "1" } },
    (err, out) => { try { res(err ? [] : JSON.parse(String(out))) } catch { res([]) } })
}))

// media:// 只放行用户打开过的文件和预览素材目录，不能拿它读本机其他文件
const allowed = new Set<string>()
const PREVIEW_ROOT = join(app.getPath("temp"), "avdetect-preview")
// Windows 路径不分大小写，统一转小写再比
const norm = (p: string) => (process.platform === "win32" ? resolve(p).toLowerCase() : resolve(p))
function allow(p: string) { allowed.add(norm(p)) }
function isAllowed(p: string) { const r = norm(p); return allowed.has(r) || r.startsWith(norm(PREVIEW_ROOT) + (process.platform === "win32" ? "\\" : "/")) }

// 时间轴预览素材（缩略帧、波形、频谱图）：按「路径 + 大小 + 修改时间」缓存，同一个文件第二次打开不重算
ipcMain.handle("preview", (_e, file: string) => new Promise((res) => {
  if (typeof file !== "string" || !existsSync(file)) return res(null)
  const st = statSync(file)
  const key = createHash("sha1").update(`${resolve(file)}|${st.size}|${st.mtimeMs}`).digest("hex").slice(0, 16)
  const dir = join(PREVIEW_ROOT, key)
  const cache = join(dir, "preview.json")
  if (existsSync(cache)) { try { return res(JSON.parse(readFileSync(cache, "utf8"))) } catch { /* 坏缓存重算 */ } }
  mkdirSync(dir, { recursive: true })
  const { cmd, cwd } = engineCommand()
  execFile(cmd, ["-m", "avengine", "preview", file, "--out", dir], { cwd, windowsHide: true, timeout: 600000, maxBuffer: 16 << 20, env: { ...process.env, PYTHONUTF8: "1" } },
    (err, out) => {
      try {
        const r = JSON.parse(String(out))
        if (r.error) return res(null)
        writeFileSync(cache, JSON.stringify(r))
        res(r)
      } catch { res(null) }
    })
}))

// 主题：跟随系统 / 浅色 / 深色。改 nativeTheme 会同时影响 macOS 侧栏材质和页面的 prefers-color-scheme
ipcMain.handle("set-theme", (_e, t: string) => { nativeTheme.themeSource = t === "light" || t === "dark" ? t : "system" })
nativeTheme.on("updated", () => {
  if (!IS_MAC && win && !win.isDestroyed()) {
    try { win.setTitleBarOverlay({ ...overlayColors(), height: TITLEBAR_H }) } catch { /* 不支持的系统忽略 */ }
  }
})

ipcMain.handle("app-info", () => ({ platform: PLATFORM, version: app.getVersion(), titlebar: IS_MAC ? 0 : TITLEBAR_H }))

ipcMain.handle("show-in-folder", (_e, p: string) => { if (typeof p === "string" && existsSync(p)) shell.showItemInFolder(p) })

ipcMain.handle("file-exists", (_e, p: string) => typeof p === "string" && existsSync(p))

ipcMain.handle("cancel", (_e, id: string) => {
  const c = jobs.get(id)
  if (c) c.kill()
  return true
})

// media:// 回放：支持 Range 分段读取。证据视频往往很大，MP4 的索引常在文件末尾，不支持分段就播不了、拖不动进度
const MIME: Record<string, string> = {
  ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska",
  ".avi": "video/x-msvideo", ".3gp": "video/3gpp", ".ts": "video/mp2t", ".flv": "video/x-flv",
  ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".aac": "audio/aac", ".flac": "audio/flac",
  ".ogg": "audio/ogg", ".opus": "audio/ogg", ".amr": "audio/amr", ".wma": "audio/x-ms-wma",
  ".png": "image/png", ".jpg": "image/jpeg",
}
function serveMedia(req: Request): Response {
  const p = decodeURIComponent(new URL(req.url).pathname.slice(1))
  if (!isAllowed(p)) return new Response("forbidden", { status: 403 })
  let size: number
  try {
    const st = statSync(p)
    if (!st.isFile()) throw new Error()
    size = st.size
  } catch {
    return new Response("not found", { status: 404 })
  }
  const type = MIME[extname(p).toLowerCase()] || "application/octet-stream"
  const m = /bytes=(\d*)-(\d*)/.exec(req.headers.get("range") || "")
  if (!m || (m[1] === "" && m[2] === "")) {
    const body = Readable.toWeb(createReadStream(p)) as unknown as ReadableStream
    return new Response(body, { status: 200, headers: { "Content-Type": type, "Content-Length": String(size), "Accept-Ranges": "bytes" } })
  }
  let start: number, end: number
  if (m[1] === "") { start = Math.max(0, size - Number(m[2])); end = size - 1 }          // bytes=-500：最后 500 字节
  else { start = Number(m[1]); end = m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1) }
  if (start >= size || start > end) return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } })
  const body = Readable.toWeb(createReadStream(p, { start, end })) as unknown as ReadableStream
  return new Response(body, {
    status: 206,
    headers: { "Content-Type": type, "Content-Length": String(end - start + 1), "Content-Range": `bytes ${start}-${end}/${size}`, "Accept-Ranges": "bytes" },
  })
}

app.whenReady().then(() => {
  // macOS 要有应用菜单，复制粘贴、退出这些快捷键才能用；其他平台不要菜单栏
  if (IS_MAC) {
    Menu.setApplicationMenu(Menu.buildFromTemplate([
      { label: "音视频检测", submenu: [{ role: "about", label: "关于" }, { type: "separator" }, { role: "hide", label: "隐藏" }, { role: "quit", label: "退出" }] },
      { label: "文件", submenu: [{ label: "打开…", accelerator: "CmdOrCtrl+O", click: () => win?.webContents.send("menu", "open") }, { role: "close", label: "关闭窗口" }] },
      { label: "编辑", submenu: [{ role: "copy", label: "拷贝" }, { role: "paste", label: "粘贴" }, { role: "selectAll", label: "全选" }] },
      { label: "窗口", submenu: [{ role: "minimize", label: "最小化" }, { role: "zoom", label: "缩放" }, { role: "togglefullscreen", label: "全屏" }] },
    ]))
  } else Menu.setApplicationMenu(null)
  protocol.handle("media", (req) => serveMedia(req))
  createWindow()
})

app.on("window-all-closed", () => {
  for (const c of jobs.values()) c.kill()
  app.quit()
})
