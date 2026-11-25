// 调检测引擎（Python 子进程）。两种用法：
//   engineStream：analyze 这种逐行输出 JSON 事件的
//   engineJson：preview / extract / detectors 这种最后打印一个 JSON 的，可以用 AbortSignal 取消
// 取消 / 超时一律「结束整棵进程树」（问题清单 P1-2）：只杀 Python 的话，它调起的 ffmpeg 会变成孤儿继续读证据文件。
//   Windows：taskkill /T /F；macOS / Linux：子进程单独成组（detached），kill 整个进程组。

import { ChildProcess, spawn } from "child_process"
import { killTree } from "./proc"
import { engineDir, ffmpegPaths, pythonPath } from "./paths"
import { log } from "./log"

function env(): NodeJS.ProcessEnv {
  const e: NodeJS.ProcessEnv = { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8", PYTHONDONTWRITEBYTECODE: "1", PYTHONPATH: engineDir() }
  const ff = ffmpegPaths()
  if (ff) { e.AVENGINE_FFMPEG = ff.ffmpeg; e.AVENGINE_FFPROBE = ff.ffprobe }
  return e
}

function start(args: string[]): ChildProcess {
  return spawn(pythonPath(), ["-m", "avengine", ...args], {
    cwd: engineDir(), env: env(), windowsHide: true,
    detached: process.platform !== "win32", // POSIX：单独成组，才能一次杀掉整组（含 ffmpeg）
  })
}

export function engineStream(args: string[], onEvent: (ev: Record<string, unknown>) => void, onExit: (code: number | null, stderr: string) => void): ChildProcess {
  const child = start(args)
  let buf = ""
  let stderr = ""
  let done = false
  const exit = (code: number | null, msg: string) => { if (!done) { done = true; onExit(code, msg) } }
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
  child.on("error", (err) => { log.error("引擎启动失败", { python: pythonPath(), err: err.message }); exit(-1, err.message) })
  child.on("close", (code) => {
    if (code) log.warn("引擎异常退出", { code, stderr: stderr.slice(-1500) })
    exit(code, stderr)
  })
  return child
}

// 一次性命令。超时或取消都会结束整棵进程树，并且等进程真正退出后才 reject（调用方之后再删临时目录才安全，问题清单 P1-3）
export function engineJson<T>(args: string[], timeoutMs = 120000, signal?: AbortSignal): Promise<T> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new Error("已取消"))
    const child = start(args)
    const out: Buffer[] = []
    let size = 0
    let errOut = ""
    let why = ""
    const stop = (reason: string) => { if (!why) { why = reason; killTree(child) } }
    const timer = setTimeout(() => stop(`超时（${Math.round(timeoutMs / 1000)} 秒）`), timeoutMs)
    const onAbort = () => stop("已取消")
    signal?.addEventListener("abort", onAbort, { once: true })
    child.stdout!.on("data", (b: Buffer) => {
      size += b.length
      if (size > 32 << 20) stop("输出过大")
      else out.push(b)
    })
    child.stderr!.setEncoding("utf8")
    child.stderr!.on("data", (c: string) => { errOut = (errOut + c).slice(-4000) })
    child.on("error", (e) => { why ||= e.message })
    child.on("close", (code) => {
      clearTimeout(timer)
      signal?.removeEventListener("abort", onAbort)
      let parsed: any = null
      try { parsed = JSON.parse(Buffer.concat(out).toString("utf8")) } catch { /* 下面处理 */ }
      if (!why && code === 0 && parsed && !parsed.error) return resolve(parsed as T)
      const msg = why || parsed?.error || `引擎命令失败（${code}）`
      if (why !== "已取消") log.warn("引擎命令失败", { cmd: args[0], msg, stderr: errOut.slice(-800) })
      reject(new Error(msg))
    })
  })
}
