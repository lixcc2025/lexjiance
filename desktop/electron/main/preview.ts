// 时间轴预览素材（缩略帧、波形、频谱图）。按「路径 + 大小 + 修改时间」缓存在临时目录，同一个文件第二次打开不重算。

import { createHash } from "crypto"
import { existsSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync, writeFileSync } from "fs"
import { join, resolve } from "path"
import type { Preview } from "../../shared/schema"
import { engineJson } from "./engine"
import { previewRoot } from "./paths"

const running = new Map<string, Promise<Preview | null>>()

export function getPreview(file: string): Promise<Preview | null> {
  if (!existsSync(file)) return Promise.resolve(null)
  const st = statSync(file)
  const key = createHash("sha1").update(`${resolve(file)}|${st.size}|${st.mtimeMs}`).digest("hex").slice(0, 16)
  const dir = join(previewRoot(), key)
  const cache = join(dir, "preview.json")
  if (existsSync(cache)) {
    try { return Promise.resolve(JSON.parse(readFileSync(cache, "utf8"))) } catch { /* 坏缓存重算 */ }
  }
  const pending = running.get(key)
  if (pending) return pending
  mkdirSync(dir, { recursive: true })
  const p = engineJson<Preview>(["preview", file, "--out", dir], 600000)
    .then((r) => { writeFileSync(cache, JSON.stringify(r)); return r })
    .catch(() => null)
    .finally(() => running.delete(key))
  running.set(key, p)
  return p
}

function dirSize(d: string): number {
  let n = 0
  for (const e of readdirSync(d, { withFileTypes: true })) {
    const p = join(d, e.name)
    n += e.isDirectory() ? dirSize(p) : statSync(p).size
  }
  return n
}

export function cacheSize(): number {
  try { return dirSize(previewRoot()) } catch { return 0 }
}

// 只删我们自己的预览目录
export function clearCache() {
  rmSync(previewRoot(), { recursive: true, force: true })
}
