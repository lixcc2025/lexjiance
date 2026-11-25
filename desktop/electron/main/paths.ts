// 各种文件位置：检测引擎、Python 运行时、ffmpeg、缓存、日志。
//
// 打包后（resources/ 下，打包脚本放进去）：
//   engine/   引擎源码（avengine 包）
//   python/   Python 运行时（Windows：嵌入版 python.exe；macOS：python-build-standalone 的 bin/python3）
//   ffmpeg/   ffmpeg、ffprobe
// 开发时：引擎用仓库里的 ../engine；Python 依次用 AVENGINE_PYTHON、engine/.venv、系统 python；
// ffmpeg 优先用 build/runtime/<平台>/ffmpeg（跑过打包准备脚本时），否则用系统 PATH。

import { app } from "electron"
import { existsSync } from "fs"
import { join, resolve } from "path"

// 平台：开发时可用 AVD_PLATFORM=win32 在别的系统上模拟 Windows 的窗口样式
export const PLATFORM = (!app.isPackaged && process.env.AVD_PLATFORM) || process.platform
export const IS_MAC = PLATFORM === "darwin"
export const IS_WIN = process.platform === "win32"
const EXE = IS_WIN ? ".exe" : ""

const DESKTOP_ROOT = resolve(__dirname, "../..")          // 开发时：desktop/
const REPO_ROOT = resolve(DESKTOP_ROOT, "..")
const DEV_RUNTIME = join(DESKTOP_ROOT, "build", "runtime", `${process.platform}-${process.arch}`)

function runtimeRoot(): string | null {
  if (app.isPackaged) return process.resourcesPath
  return existsSync(DEV_RUNTIME) ? DEV_RUNTIME : null
}

export function engineDir(): string {
  return app.isPackaged ? join(process.resourcesPath, "engine") : join(REPO_ROOT, "engine")
}

// 打包后用自带的 Python；开发时不用 build/runtime 里的（Windows 嵌入版只认它旁边的 engine 副本，改了代码不生效）
export function pythonPath(): string {
  if (app.isPackaged) return IS_WIN ? join(process.resourcesPath, "python", "python.exe") : join(process.resourcesPath, "python", "bin", "python3")
  if (process.env.AVENGINE_PYTHON) return process.env.AVENGINE_PYTHON
  const venv = IS_WIN ? join(engineDir(), ".venv", "Scripts", "python.exe") : join(engineDir(), ".venv", "bin", "python")
  if (existsSync(venv)) return venv
  return IS_WIN ? "python" : "python3"
}

// 自带的 ffmpeg；没有就返回 null，引擎自己从 PATH 找
export function ffmpegPaths(): { ffmpeg: string; ffprobe: string } | null {
  const rt = runtimeRoot()
  if (!rt) return null
  const ffmpeg = join(rt, "ffmpeg", "ffmpeg" + EXE)
  const ffprobe = join(rt, "ffmpeg", "ffprobe" + EXE)
  return existsSync(ffmpeg) && existsSync(ffprobe) ? { ffmpeg, ffprobe } : null
}

export const previewRoot = () => join(app.getPath("temp"), "avdetect-preview")
export const extractRoot = () => join(app.getPath("temp"), "avdetect-upload")
export const logDir = () => join(app.getPath("userData"), "logs")
export const settingsFile = () => join(app.getPath("userData"), "settings.json")
export const tokenFile = () => join(app.getPath("userData"), "cloud-token.bin")
export const preloadPath = () => join(__dirname, "../preload/index.js")
export const rendererIndex = () => join(__dirname, "../renderer/index.html")
