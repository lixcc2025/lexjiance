// 日志：用户数据目录 logs/main.log，超过 2MB 轮换一份。排查用户机器上的问题时让对方发这个文件。
// 不记录检测文件的内容，只记录路径和出错信息。

import { appendFileSync, mkdirSync, renameSync, statSync } from "fs"
import { join } from "path"
import { logDir } from "./paths"

const MAX = 2 * 1024 * 1024

function write(level: string, msg: string, extra?: unknown) {
  const line = `[${new Date().toISOString()}] [${level}] ${msg}${extra === undefined ? "" : " " + safe(extra)}\n`
  if (level !== "DEBUG") process.stderr.write(line)
  try {
    const dir = logDir()
    mkdirSync(dir, { recursive: true })
    const f = join(dir, "main.log")
    try { if (statSync(f).size > MAX) renameSync(f, join(dir, "main.1.log")) } catch { /* 还没有文件 */ }
    appendFileSync(f, line)
  } catch { /* 写日志失败不影响使用 */ }
}

function safe(v: unknown): string {
  try { return (v instanceof Error ? `${v.name}: ${v.message}` : JSON.stringify(v)).slice(0, 2000) } catch { return String(v) }
}

export const log = {
  info: (m: string, x?: unknown) => write("INFO", m, x),
  warn: (m: string, x?: unknown) => write("WARN", m, x),
  error: (m: string, x?: unknown) => write("ERROR", m, x),
}
