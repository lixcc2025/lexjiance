// 主进程：窗口、选文件、调检测引擎（Python 子进程，逐行 JSON 事件）、本地媒体回放协议。
// 全程离线：文件不上传，引擎在本机跑（法院、检察院多在内网）。
import { app, BrowserWindow, dialog, ipcMain, Menu, net, protocol } from "electron"
import { spawn, ChildProcess } from "child_process"
import { existsSync } from "fs"
import { join, resolve } from "path"
import { pathToFileURL } from "url"

const MEDIA_EXT = ["mp4", "mov", "m4v", "avi", "mkv", "webm", "3gp", "flv", "ts", "mp3", "wav", "m4a", "aac", "amr", "flac", "ogg", "opus", "wma"]

// 回放用的协议：渲染进程用 media://本机路径 播放被检测的文件，不放开 file://
protocol.registerSchemesAsPrivileged([{ scheme: "media", privileges: { stream: true, supportFetchAPI: true, bypassCSP: true } }])

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

ipcMain.handle("cancel", (_e, id: string) => {
  const c = jobs.get(id)
  if (c) c.kill()
  return true
})

app.whenReady().then(() => {
  Menu.setApplicationMenu(null) // 不要 Electron 默认的英文菜单
  protocol.handle("media", (req) => {
    const p = decodeURIComponent(req.url.slice("media://".length))
    return net.fetch(pathToFileURL(p).toString())
  })
  createWindow()
})

app.on("window-all-closed", () => {
  for (const c of jobs.values()) c.kill()
  app.quit()
})
