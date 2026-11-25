// 云端 AI 识别客户端。接口说明：docs/云端接口.md
// 流程：引擎 extract 提取素材（16k 音轨 + 抽帧，不传原文件）→ POST {地址}/v1/detect → 合并结果 → 删临时素材

import { randomBytes } from "crypto"
import { readFileSync, rmSync } from "fs"
import { basename, join } from "path"
import { app } from "electron"
import type { AnalyzeResult, CloudHealth } from "../../shared/schema"
import { CLOUD_API_VERSION, CloudMeta, cloudSkipped, mergeCloud, sanitizeResponse } from "../../shared/cloud-protocol"
import { engineJson } from "./engine"
import { extractRoot, PLATFORM } from "./paths"
import { getCloudToken, getSettings } from "./settings"
import { log } from "./log"

const DETECT_TIMEOUT = 15 * 60 * 1000
const HEALTH_TIMEOUT = 8000

function headers(): Record<string, string> {
  const t = getCloudToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

function describe(e: unknown): string {
  const m = e instanceof Error ? e.message : String(e)
  if (/abort|timeout/i.test(m)) return "连接超时"
  if (/fetch failed|ECONNREFUSED|ENOTFOUND|EAI_AGAIN/i.test(m)) return "连不上服务器"
  return m.slice(0, 200)
}

export async function testCloud(): Promise<CloudHealth> {
  const s = getSettings()
  if (!s.cloud.url) return { ok: false, message: "还没填服务器地址" }
  try {
    const r = await fetch(`${s.cloud.url}/${CLOUD_API_VERSION}/health`, { headers: headers(), signal: AbortSignal.timeout(HEALTH_TIMEOUT) })
    if (r.status === 401 || r.status === 403) return { ok: false, message: "访问令牌不对或已过期" }
    if (!r.ok) return { ok: false, message: `服务器返回 ${r.status}` }
    const j: any = await r.json().catch(() => ({}))
    return { ok: true, message: "连接正常", version: j.version, models: Array.isArray(j.models) ? j.models : undefined }
  } catch (e) {
    return { ok: false, message: describe(e) }
  }
}

// 本机结果 → 加上云端结果。云端没启用或出错时，结果里写明原因（不影响本机结果）
export async function withCloud(file: string, local: AnalyzeResult, progress: (pct: number, stage: string) => void, signal: AbortSignal): Promise<AnalyzeResult> {
  const s = getSettings()
  if (!s.cloud.enabled) return mergeCloud(local, null, cloudSkipped("云端识别未启用"))
  if (!s.cloud.url) return mergeCloud(local, null, cloudSkipped("没填服务器地址"))

  const dir = join(extractRoot(), randomBytes(6).toString("hex"))
  const t0 = Date.now()
  try {
    progress(0, "云端 AI 识别：提取上传素材")
    const m = await engineJson<{ duration: number; audio: string | null; sample_rate: number; frames: { t: number; file: string }[] }>(["extract", file, "--out", dir], 10 * 60 * 1000)
    if (signal.aborted) throw new Error("已取消")
    const meta: CloudMeta = {
      api: CLOUD_API_VERSION,
      client: { name: "avdetect", version: app.getVersion(), platform: PLATFORM },
      duration: m.duration,
      sample_rate: m.sample_rate,
      has_audio: !!m.audio,
      frames: m.frames.map((f) => ({ t: f.t, name: basename(f.file) })),
    }
    const form = new FormData()
    form.append("meta", JSON.stringify(meta))
    if (m.audio) form.append("audio", new Blob([readFileSync(m.audio)], { type: "audio/flac" }), "audio.flac")
    for (const f of m.frames) form.append("frames", new Blob([readFileSync(f.file)], { type: "image/jpeg" }), basename(f.file))

    progress(0.3, "云端 AI 识别：上传并识别")
    const r = await fetch(`${s.cloud.url}/${CLOUD_API_VERSION}/detect`, {
      method: "POST", body: form, headers: headers(), signal: AbortSignal.any([signal, AbortSignal.timeout(DETECT_TIMEOUT)]),
    })
    if (r.status === 401 || r.status === 403) throw new Error("访问令牌不对或已过期")
    if (!r.ok) throw new Error(`服务器返回 ${r.status}`)
    const body = sanitizeResponse(await r.json(), local.media.duration)
    log.info("云端识别完成", { seconds: (Date.now() - t0) / 1000, findings: body.findings.length })
    progress(1, "云端 AI 识别：完成")
    return mergeCloud(local, body)
  } catch (e) {
    const msg = signal.aborted ? "已取消" : describe(e)
    log.warn("云端识别失败", msg)
    return mergeCloud(local, null, cloudSkipped(msg, true))
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
}
