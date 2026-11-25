// 调检测引擎（Python 子进程）。两种用法：
//   engineStream：analyze 这种逐行输出 JSON 事件的
//   engineJson：preview / extract / detectors 这种最后打印一个 JSON 的

import { ChildProcess, execFile, spawn } from "child_process"
import { engineDir, ffmpegPaths, pythonPath } from "./paths"
import { log } from "./log"

function env(): NodeJS.ProcessEnv {
  const e: NodeJS.ProcessEnv = { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8", PYTHONDONTWRITEBYTECODE: "1", PYTHONPATH: engineDir() }
  const ff = ffmpegPaths()
  if (ff) { e.AVENGINE_FFMPEG = ff.ffmpeg; e.AVENGINE_FFPROBE = ff.ffprobe }
  return e
}

export function engineStream(args: string[], onEvent: (ev: Record<string, unknown>) => void, onExit: (code: number | null, stderr: string) => void): ChildProcess {
  const child = spawn(pythonPath(), ["-m", "avengine", ...args], { cwd: engineDir(), env: env(), windowsHide: true })
  let buf = ""
  let stderr = ""
  child.stdout!.setEncoding("utf8")
  child.stdout!.on("data", (chunk: string) => {
    buf += chunk
    let i: number
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim()
      buf = buf.slice(i + 1)
      if (!line) continue
      try { onEvent(JSON.parse(line)) } catch { /* 非 JSON 行忽略 */ }
    }
  })
  child.stderr!.setEncoding("utf8")
  child.stderr!.on("data", (c: string) => { stderr = (stderr + c).slice(-8000) })
  child.on("error", (err) => { log.error("引擎启动失败", { python: pythonPath(), err: err.message }); onExit(-1, err.message) })
  child.on("close", (code) => {
    if (code) log.warn("引擎异常退出", { code, stderr: stderr.slice(-1500) })
    onExit(code, stderr)
  })
  return child
}

export function engineJson<T>(args: string[], timeoutMs = 120000): Promise<T> {
  return new Promise((resolve, reject) => {
    execFile(pythonPath(), ["-m", "avengine", ...args], { cwd: engineDir(), env: env(), windowsHide: true, timeout: timeoutMs, maxBuffer: 32 << 20 },
      (err, out, errOut) => {
        let parsed: any = null
        try { parsed = JSON.parse(String(out)) } catch { /* 下面处理 */ }
        if (parsed && !parsed.error && !err) return resolve(parsed as T)
        const msg = parsed?.error || (err ? err.message : "引擎输出无法解析")
        log.warn("引擎命令失败", { args: args[0], msg, stderr: String(errOut).slice(-800) })
        reject(new Error(msg))
      })
  })
}
