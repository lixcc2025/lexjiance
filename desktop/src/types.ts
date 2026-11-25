// 引擎输出的结构（对应 engine/avengine/models.py）和 preload 暴露的接口
export type Severity = "info" | "low" | "medium" | "high"
export interface Finding {
  detector: string
  category: "ai" | "edit" | "source"
  severity: Severity
  title: string
  detail: string
  modality: "file" | "video" | "audio"
  start: number | null
  end: number | null
  evidence: Record<string, unknown>
}
export interface Verdict { level: "none" | "suspicious" | "likely" | "unknown"; text: string; score: number | null }
export interface DetectorStatus { name: string; title: string; ok: boolean; skipped: string; error: string; seconds: number }
export interface AnalyzeResult {
  file: string
  media: { format: string; duration: number | null; size: number; video: any; audio: any }
  ai: Verdict
  edit: Verdict
  findings: Finding[]
  detectors: DetectorStatus[]
}

declare global {
  interface Window {
    avd: {
      pickFile(): Promise<string | null>
      pathOf(file: File): string
      analyze(file: string): Promise<{ ok: boolean; job?: string; error?: string }>
      cancel(job: string): Promise<boolean>
      onOpenFile(cb: (path: string) => void): void
      onEvent(cb: (ev: any) => void): () => void
    }
  }
}
