// 主进程和页面共用的数据结构。
// 检测结果对应引擎的 engine/avengine/models.py；改了那边要同步这里。

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
  signal?: string // 证据类型（ts_gap、noise_floor……），结论用它判断不同证据是否互相印证
}
export interface Verdict { level: Level; text: string; score: number | null }
export interface DetectorStatus { name: string; title: string; desc: string; ok: boolean; skipped: string; error: string; seconds: number }
export interface DetectorInfo { name: string; title: string; desc: string; needs: string; uses_model: boolean; cloud?: boolean }
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

// 检测过程中推给页面的事件（engine-event）
export type EngineEvent =
  | { job: string; type: "progress"; pct: number; stage: string }
  | ({ job: string; type: "finding" } & Finding)
  | ({ job: string; type: "detector" } & DetectorStatus)
  | ({ job: string; type: "result" } & AnalyzeResult)
  | { job: string; type: "error"; message: string }

export type Theme = "system" | "light" | "dark"

// 设置（存在用户数据目录的 settings.json；云端令牌单独加密保存，不发给页面）
export interface Settings {
  theme: Theme
  // insecure：地址是公网上的 http 明文；allowInsecure：用户已确认仍要使用
  cloud: { enabled: boolean; url: string; hasToken: boolean; insecure: boolean; allowInsecure: boolean }
  keepHistory: boolean // 是否在本机保留检测记录（含文件路径）
}
export interface SettingsPatch {
  theme?: Theme
  keepHistory?: boolean
  cloud?: { enabled?: boolean; url?: string; token?: string | null; allowInsecure?: boolean } // token：null 清除，undefined 不改
}

export interface AppInfo { platform: string; version: string; titlebar: number }
export interface CloudHealth { ok: boolean; message: string; version?: string; models?: string[] }

// preload 暴露给页面的接口（window.avd）
export interface Bridge {
  pickFile(): Promise<string | null>
  pathOf(file: File): string
  analyze(file: string): Promise<{ ok: boolean; job?: string; error?: string }>
  cancel(job: string): Promise<boolean>
  listDetectors(): Promise<DetectorInfo[]>
  preview(path: string): Promise<Preview | null>
  appInfo(): Promise<AppInfo>
  getSettings(): Promise<Settings>
  saveSettings(patch: SettingsPatch): Promise<Settings>
  testCloud(): Promise<CloudHealth>
  cacheSize(): Promise<number>
  clearCache(): Promise<void>
  openLogs(): Promise<void>
  clearLogs(): Promise<void>
  ready(): void // 页面的事件监听都挂好了（之后主进程才把启动时带的文件交过来）
  showInFolder(path: string): Promise<void>
  fileExists(path: string): Promise<boolean>
  onOpenFile(cb: (path: string) => void): () => void
  onMenu(cb: (cmd: string) => void): () => void
  onEvent(cb: (ev: EngineEvent) => void): () => void
}
