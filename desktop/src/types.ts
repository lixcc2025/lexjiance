// 页面用的类型和显示用的小工具。数据结构本身在 shared/schema.ts（主进程和页面共用）。
import type { Bridge, Level, Severity, Category } from "../shared/schema"
export type * from "../shared/schema"

export interface HistoryItem { path: string; name: string; time: number; ai: Level; edit: Level; count: number }

declare global {
  interface Window { avd: Bridge }
}

export const SEV_TEXT: Record<Severity, string> = { info: "说明", low: "轻微", medium: "可疑", high: "高度可疑" }
export const CAT_TEXT: Record<Category, string> = { ai: "AI 生成", edit: "剪辑痕迹", source: "来源信息" }
export const LEVEL_TEXT: Record<Level, string> = { none: "未发现", suspicious: "有疑点", likely: "高度可疑", unknown: "无法判断" }

export function fmtTime(t: number | null | undefined, ms = true): string {
  if (t === null || t === undefined || !isFinite(t)) return "--:--"
  const h = Math.floor(t / 3600)
  const m = Math.floor((t % 3600) / 60)
  const s = t % 60
  const ss = ms ? s.toFixed(1).padStart(4, "0") : String(Math.floor(s)).padStart(2, "0")
  return (h ? `${h}:${String(m).padStart(2, "0")}` : String(m).padStart(2, "0")) + ":" + ss
}

export function fmtSize(n: number): string {
  if (n >= 1 << 30) return (n / (1 << 30)).toFixed(2) + " GB"
  if (n >= 1 << 20) return (n / (1 << 20)).toFixed(1) + " MB"
  if (n >= 1 << 10) return (n / (1 << 10)).toFixed(0) + " KB"
  return n + " B"
}

export function baseName(p: string): string {
  return p.split(/[\\/]/).pop() || p
}

export const mediaUrl = (p: string) => "media://file/" + encodeURIComponent(p)
export const SEV_COLOR: Record<Severity, string> = { info: "var(--unknown)", low: "var(--low)", medium: "var(--warn)", high: "var(--danger)" }
export const LEVEL_TONE: Record<Level, string> = { none: "ok", suspicious: "warn", likely: "danger", unknown: "unknown" }
