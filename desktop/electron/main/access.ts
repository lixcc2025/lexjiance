// 哪些本机文件可以通过 media:// 给页面读（纯 Node，单元测试覆盖）。问题清单 P2-1、P2-6：
// - 只接受可信来源加进来：打开文件对话框、系统传来的文件（打开方式 / 第二个实例 / 拖到 Dock），
//   以及页面传来的、确实是普通文件且扩展名是音视频的（拖进窗口、检测记录）
// - 预览素材目录里主进程自己生成的文件
// - 比较前先 realpath（防符号链接绕过），Windows 和 macOS 不分大小写；目录前缀用 path.relative 判断，不用字符串 startsWith

import { realpathSync, statSync } from "fs"
import { extname, isAbsolute, relative, resolve } from "path"

export const MEDIA_EXT = ["mp4", "mov", "m4v", "avi", "mkv", "webm", "3gp", "flv", "ts", "mp3", "wav", "m4a", "aac", "amr", "flac", "ogg", "opus", "wma"]

const FOLD = process.platform === "win32" || process.platform === "darwin"

function real(p: string): string | null {
  try { return realpathSync.native(resolve(p)) } catch { return null }
}
const key = (p: string) => (FOLD ? p.toLowerCase() : p)

export function isMediaFile(p: unknown): p is string {
  if (typeof p !== "string" || !p || p.length > 4096 || !isAbsolute(p)) return false
  if (!MEDIA_EXT.includes(extname(p).slice(1).toLowerCase())) return false
  try { return statSync(p).isFile() } catch { return false }
}

export class Access {
  private files = new Set<string>()
  constructor(private roots: () => string[]) {}

  // 加一个可以读的文件；不是音视频文件就拒绝（返回 false）
  allowMedia(p: unknown): boolean {
    if (!isMediaFile(p)) return false
    const r = real(p)
    if (!r) return false
    this.files.add(key(r))
    return true
  }

  isAllowed(p: string): boolean {
    const r = real(p)
    if (!r) return false
    if (this.files.has(key(r))) return true
    return this.roots().some((root) => {
      const rr = real(root)
      if (!rr) return false
      const rel = relative(key(rr), key(r))
      return !!rel && !rel.startsWith("..") && !isAbsolute(rel)
    })
  }
}
