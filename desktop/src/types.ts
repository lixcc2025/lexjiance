// 引擎输出的结构（对应 engine/avengine/models.py）和 preload 暴露的接口

export type Severity = "info" | "low" | "medium" | "high"
export type Category = "ai" | "edit" | "source"
export type Level = "none" | "suspicious" | "likely" | "unknown"

export interface Finding {
  detector: string
  category: Category
  severity: Severity
  title: string
  detail: string
  modality: "file" | "video" | "audio"
  start: number | null
  end: number | null
  evidence: Record<string, unknown>
}
export interface Verdict { level: Level; text: string; score: number | null }
export interface DetectorStatus { name: string; title: string; desc: string; ok: boolean; skipped: string; error: string; seconds: number }
export interface DetectorInfo { name: string; title: string; desc: string; needs: string; uses_model: boolean }
export interface MediaSummary {
  format: string
  duration: number | null
  size: number
  video: { codec: string; width: number; height: number; fps: string } | null
  audio: { codec: string; sample_rate: number; channels: number } | null
}
export interface AnalyzeResult {
  file: string
  media: MediaSummary
  ai: Verdict
  edit: Verdict
  findings: Finding[]
  detectors: DetectorStatus[]
}
export interface Preview {
  duration: number
  waveform: number[]
  spectrogram: string | null
  frames: { t: number; path: string }[]
}
export interface HistoryItem { path: string; name: string; time: number; ai: Level; edit: Level; count: number }

declare global {
  interface Window {
    avd: {
      pickFile(): Promise<string | null>
      pathOf(file: File): string
      analyze(file: string): Promise<{ ok: boolean; job?: string; error?: string }>
      cancel(job: string): Promise<boolean>
      listDetectors(): Promise<DetectorInfo[]>
      preview(path: string): Promise<Preview | null>
      setTheme(t: string): Promise<void>
      appInfo(): Promise<{ platform: string; version: string }>
      onMenu(cb: (cmd: string) => void): void
      showInFolder(path: string): Promise<void>
      fileExists(path: string): Promise<boolean>
      onOpenFile(cb: (path: string) => void): void
      onEvent(cb: (ev: any) => void): () => void
    }
  }
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
