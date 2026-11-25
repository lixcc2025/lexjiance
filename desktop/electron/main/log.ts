// 日志：用户数据目录 logs/main.log，超过 2MB 轮换一份。排查用户机器上的问题时让对方发这个文件。
// 不记录检测文件的内容；文件只记文件名（问题清单 P2-7）。换行会被转义，日志行不能被伪造。

import { appendFileSync, mkdirSync, renameSync, rmSync, statSync } from "fs"
import { join } from "path"
import { logDir } from "./paths"

const MAX = 2 * 1024 * 1024

function write(level: string, msg: string, extra?: unknown) {
  const line = `[${new Date().toISOString()}] [${level}] ${oneLine(msg)}${extra === undefined ? "" : " " + oneLine(safe(extra))}\n`
  if (level !== "DEBUG") process.stderr.write(line)
  try {
    const dir = logDir()
    mkdirSync(dir, { recursive: true })
    const f = join(dir, "main.log")
    try { if (statSync(f).size > MAX) renameSync(f, join(dir, "main.1.log")) } catch { /* 还没有文件 */ }
    appendFileSync(f, line)
  } catch { /* 写日志失败不影响使用 */ }
}

const oneLine = (s: string) => s.replace(/\r/g, "\\r").replace(/\n/g, "\\n")

function safe(v: unknown): string {
  try { return (v instanceof Error ? `${v.name}: ${v.message}` : JSON.stringify(v)).slice(0, 2000) } catch { return String(v) }
}

export function clearLogs() {
  for (const n of ["main.log", "main.1.log"]) rmSync(join(logDir(), n), { force: true })
}

export const log = {
  info: (m: string, x?: unknown) => write("INFO", m, x),
  warn: (m: string, x?: unknown) => write("WARN", m, x),
  error: (m: string, x?: unknown) => write("ERROR", m, x),
}
