// 时间轴预览素材（缩略帧、波形、频谱图）。按「路径 + 大小 + 修改时间」缓存在临时目录，同一个文件第二次打开不重算。
// 问题清单 P3-7：IO 全部异步（不卡主进程）；容量上限 1GB，超了先删最久没用的；超过 30 天没用的启动时清掉。
// 缓存里有证据的缩略图，设置里可以一键清理。

import { createHash } from "crypto"
import { promises as fs } from "fs"
import { join, resolve } from "path"
import type { Preview } from "../../shared/schema"
import { engineJson } from "./engine"
import { previewRoot } from "./paths"
import { log } from "./log"

const MAX_BYTES = 1024 * 1024 * 1024
const MAX_AGE_MS = 30 * 24 * 3600 * 1000
const running = new Map<string, Promise<Preview | null>>()

export async function getPreview(file: string): Promise<Preview | null> {
  let st
  try { st = await fs.stat(file) } catch { return null }
  const key = createHash("sha1").update(`${resolve(file)}|${st.size}|${st.mtimeMs}`).digest("hex").slice(0, 16)
  const dir = join(previewRoot(), key)
  const cache = join(dir, "preview.json")
  try {
    const r = JSON.parse(await fs.readFile(cache, "utf8"))
    const now = new Date()
    await fs.utimes(dir, now, now).catch(() => {}) // 记一下最近使用时间，给容量清理用
    return r
  } catch { /* 没有缓存或坏了，重算 */ }
  const pending = running.get(key)
  if (pending) return pending
  const p = (async () => {
    await fs.rm(dir, { recursive: true, force: true })
    await fs.mkdir(dir, { recursive: true, mode: 0o700 })
    const r = await engineJson<Preview>(["preview", file, "--out", dir], 600000)
    await fs.writeFile(cache, JSON.stringify(r))
    void trimCache(key)
    return r
  })()
    .catch((e) => { log.warn("生成预览素材失败", String(e?.message || e)); return null })
    .finally(() => running.delete(key))
  running.set(key, p)
  return p
}

async function dirSize(d: string): Promise<number> {
  let n = 0
  for (const e of await fs.readdir(d, { withFileTypes: true }).catch(() => [])) {
    const p = join(d, e.name)
    n += e.isDirectory() ? await dirSize(p) : (await fs.stat(p).catch(() => ({ size: 0 }))).size
  }
  return n
}

export async function cacheSize(): Promise<number> {
  return dirSize(previewRoot())
}

// 删超过 30 天没用的；总量超过上限时从最久没用的开始删。keep：刚生成的那份不删
export async function trimCache(keep?: string) {
  const root = previewRoot()
  const entries = await fs.readdir(root, { withFileTypes: true }).catch(() => [])
  const items: { name: string; mtime: number; size: number }[] = []
  for (const e of entries) {
    if (!e.isDirectory()) continue
    const p = join(root, e.name)
    const st = await fs.stat(p).catch(() => null)
    if (!st) continue
    items.push({ name: e.name, mtime: st.mtimeMs, size: await dirSize(p) })
  }
  items.sort((a, b) => a.mtime - b.mtime)
  let total = items.reduce((s, x) => s + x.size, 0)
  const now = Date.now()
  for (const it of items) {
    if (it.name === keep) continue
    if (now - it.mtime > MAX_AGE_MS || total > MAX_BYTES) {
      await fs.rm(join(root, it.name), { recursive: true, force: true })
      total -= it.size
    }
  }
}

// 只删我们自己的预览目录
export async function clearCache() {
  await fs.rm(previewRoot(), { recursive: true, force: true })
}
