// 云端 AI 识别的接口约定和结果合并（纯函数，主进程用，单元测试覆盖）。接口说明见 docs/云端接口.md。
//
// 本机只做不用模型的检测；AI 合成语音、AI 生成画面、隐形水印这些要模型的检测在云端服务器（或单位内网服务器）上跑。

import type { AnalyzeResult, DetectorInfo, DetectorStatus, Finding } from "./schema"
import { sortFindings, verdict } from "./verdict"

export const CLOUD_API_VERSION = "v1"

// 云端检测项（界面上和本机检测项一起列出，带「云端」标记）
export const CLOUD_DETECTORS: DetectorInfo[] = [
  { name: "ai_voice", title: "AI 合成语音", desc: "声音克隆、语音合成", needs: "audio", uses_model: true, cloud: true },
  { name: "ai_video", title: "AI 生成画面", desc: "文生视频、换脸", needs: "video", uses_model: true, cloud: true },
  { name: "watermark", title: "隐形水印", desc: "AudioSeal 等 AI 水印", needs: "any", uses_model: true, cloud: true },
]

// 上传时附带的说明（multipart 的 meta 字段）
export interface CloudMeta {
  api: string
  client: { name: string; version: string; platform: string }
  duration: number
  sample_rate: number
  has_audio: boolean
  frames: { t: number; name: string }[]
}

// 服务器返回
export interface CloudResponse {
  detectors: DetectorStatus[]
  findings: Finding[]
}

const SEVERITIES = new Set(["info", "low", "medium", "high"])
const CATEGORIES = new Set(["ai", "edit", "source"])

// 服务器返回的内容不完全可信：字段缺的补默认、类型不对的丢掉，时间限制在文件时长内
export function sanitizeResponse(raw: unknown, duration: number | null): CloudResponse {
  const r = (raw && typeof raw === "object" ? raw : {}) as Record<string, unknown>
  const num = (v: unknown) => (typeof v === "number" && isFinite(v) ? v : null)
  const clamp = (v: number | null) => (v === null ? null : Math.max(0, duration ? Math.min(v, duration) : v))
  const findings: Finding[] = (Array.isArray(r.findings) ? r.findings : [])
    .filter((f: any) => f && typeof f.title === "string" && SEVERITIES.has(f.severity) && CATEGORIES.has(f.category))
    .slice(0, 500)
    .map((f: any) => ({
      detector: String(f.detector || "cloud"),
      category: f.category,
      severity: f.severity,
      title: String(f.title).slice(0, 200),
      detail: String(f.detail || "").slice(0, 2000),
      modality: ["file", "video", "audio"].includes(f.modality) ? f.modality : "file",
      start: clamp(num(f.start)),
      end: clamp(num(f.end)),
      evidence: f.evidence && typeof f.evidence === "object" ? f.evidence : {},
      signal: typeof f.signal === "string" && f.signal ? f.signal.slice(0, 40) : `cloud:${String(f.detector || "cloud").slice(0, 30)}`,
    }))
  const detectors: DetectorStatus[] = (Array.isArray(r.detectors) ? r.detectors : [])
    .filter((d: any) => d && typeof d.name === "string")
    .map((d: any) => ({
      name: String(d.name),
      title: String(d.title || CLOUD_DETECTORS.find((c) => c.name === d.name)?.title || d.name),
      desc: String(d.desc || CLOUD_DETECTORS.find((c) => c.name === d.name)?.desc || ""),
      ok: d.ok !== false,
      skipped: String(d.skipped || ""),
      error: String(d.error || ""),
      seconds: num(d.seconds) ?? 0,
    }))
  return { findings, detectors }
}

// 云端没跑（没配置、连不上、出错）时，给每个云端检测项一个状态，界面上显示原因
export function cloudSkipped(reason: string, error = false): DetectorStatus[] {
  return CLOUD_DETECTORS.map((d) => ({ name: d.name, title: d.title, desc: d.desc, ok: !error, skipped: error ? "" : reason, error: error ? reason : "", seconds: 0 }))
}

// 本机结果 + 云端结果 → 最终结果（重算两项结论）
export function mergeCloud(local: AnalyzeResult, cloud: CloudResponse | null, statuses?: DetectorStatus[]): AnalyzeResult {
  const extraStatus = cloud ? cloud.detectors : statuses || []
  // 云端没返回状态的检测项，标成「未返回」
  const filled = CLOUD_DETECTORS.map((d) => extraStatus.find((s) => s.name === d.name) || { name: d.name, title: d.title, desc: d.desc, ok: true, skipped: "服务器未返回", error: "", seconds: 0 })
  const others = extraStatus.filter((s) => !CLOUD_DETECTORS.some((d) => d.name === s.name))
  const detectors = [...local.detectors, ...filled, ...others]
  const findings = sortFindings([...local.findings, ...(cloud ? cloud.findings : [])])
  // 只有已知的云端检测项真正跑完才算「AI 模型跑过」；不认识的检测项只展示，不参与任何结论（问题清单 P0-2）
  const aiRan = filled.some((s) => s.ok && !s.skipped && !s.error)
  return { ...local, findings, detectors, ai: verdict(findings, "ai", aiRan), edit: verdict(findings, "edit") }
}
