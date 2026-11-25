// 主进程：窗口、选文件、调检测引擎（Python 子进程，逐行 JSON 事件）、本地媒体回放协议。
// 全程离线：文件不上传，引擎在本机跑（法院、检察院多在内网）。
import { app, BrowserWindow, dialog, ipcMain, Menu, protocol, shell } from "electron"
import { spawn, execFile, ChildProcess } from "child_process"
import { createReadStream, existsSync, statSync } from "fs"
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

function createWindow() {
  win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    title: "音视频检测",
    backgroundColor: "#f4f6fa",
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
}
function serveMedia(req: Request): Response {
  const p = decodeURIComponent(new URL(req.url).pathname.slice(1))
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
  Menu.setApplicationMenu(null) // 不要 Electron 默认的英文菜单
  protocol.handle("media", (req) => serveMedia(req))
  createWindow()
})

app.on("window-all-closed", () => {
  for (const c of jobs.values()) c.kill()
  app.quit()
})
