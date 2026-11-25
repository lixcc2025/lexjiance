// 云端 AI 识别客户端。接口说明：docs/云端接口.md
// 流程：引擎 extract 提取素材（16k 音轨 + 抽帧，不传原文件）→ POST {地址}/v1/detect → 合并结果 → 删临时素材
//
// 问题清单 P1-3 / P2-3 / P2-4 / P2-8：
// - 提取阶段也能取消（结束整棵进程树），等进程退出后才删临时目录
// - 临时目录只有本人能读（0700）；启动和退出时清扫残留（sweepExtracts）
// - 公网 http 明文地址没确认过就不发令牌和素材
// - 响应体最多 5MB

import { randomBytes } from "crypto"
import { mkdirSync, openAsBlob, rmSync } from "fs"
import { basename, join } from "path"
import { app } from "electron"
import type { AnalyzeResult, CloudHealth } from "../../shared/schema"
import { CLOUD_API_VERSION, CloudMeta, LIMITS, cloudSkipped, mergeCloud, sanitizeResponse } from "../../shared/cloud-protocol"
import { engineJson } from "./engine"
import { extractRoot, PLATFORM } from "./paths"
import { cloudSendAllowed, getCloudToken, getSettings } from "./settings"
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

// 读 JSON，最多 LIMITS.responseBytes 字节
async function readJsonCapped(r: Response): Promise<unknown> {
  const len = Number(r.headers.get("content-length") || 0)
  if (len > LIMITS.responseBytes) throw new Error("服务器返回的内容过大")
  if (!r.body) return null
  const reader = r.body.getReader()
  const parts: Uint8Array[] = []
  let size = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    size += value.length
    if (size > LIMITS.responseBytes) { await reader.cancel(); throw new Error("服务器返回的内容过大") }
    parts.push(value)
  }
  try { return JSON.parse(Buffer.concat(parts).toString("utf8")) } catch { throw new Error("服务器返回的不是 JSON") }
}

export function sweepExtracts() {
  rmSync(extractRoot(), { recursive: true, force: true })
}

export async function testCloud(): Promise<CloudHealth> {
  const s = getSettings()
  if (!s.cloud.url) return { ok: false, message: "还没填服务器地址" }
  if (!cloudSendAllowed()) return { ok: false, message: "公网 http 明文地址，需要先确认风险或改用 https" }
  try {
    const r = await fetch(`${s.cloud.url}/${CLOUD_API_VERSION}/health`, { headers: headers(), signal: AbortSignal.timeout(HEALTH_TIMEOUT) })
    if (r.status === 401 || r.status === 403) return { ok: false, message: "访问令牌不对或已过期" }
    if (!r.ok) return { ok: false, message: `服务器返回 ${r.status}` }
    const j: any = await readJsonCapped(r).catch(() => ({}))
    return { ok: true, message: "连接正常", version: typeof j?.version === "string" ? j.version.slice(0, 40) : undefined, models: Array.isArray(j?.models) ? j.models.slice(0, 10).map((m: unknown) => String(m).slice(0, 60)) : undefined }
  } catch (e) {
    return { ok: false, message: describe(e) }
  }
}

// 本机结果 → 加上云端结果。云端没启用或出错时，结果里写明原因（不影响本机结果）。取消时抛出「已取消」
export async function withCloud(file: string, local: AnalyzeResult, progress: (pct: number, stage: string) => void, signal: AbortSignal): Promise<AnalyzeResult> {
  const s = getSettings()
  if (!s.cloud.enabled) return mergeCloud(local, null, cloudSkipped("云端识别未启用"))
  if (!s.cloud.url) return mergeCloud(local, null, cloudSkipped("没填服务器地址"))
  if (!cloudSendAllowed()) return mergeCloud(local, null, cloudSkipped("公网 http 地址未确认，没有上传", true))

  const dir = join(extractRoot(), randomBytes(6).toString("hex"))
  mkdirSync(dir, { recursive: true, mode: 0o700 })
  const t0 = Date.now()
  try {
    progress(0, "云端 AI 识别：提取上传素材")
    const m = await engineJson<{ duration: number; audio: string | null; sample_rate: number; frames: { t: number; file: string }[] }>(["extract", file, "--out", dir], 10 * 60 * 1000, signal)
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
    // openAsBlob：从磁盘流式读，长录音不用整块读进内存
    if (m.audio) form.append("audio", await openAsBlob(m.audio, { type: "audio/flac" }), "audio.flac")
    for (const f of m.frames) form.append("frames", await openAsBlob(f.file, { type: "image/jpeg" }), basename(f.file))

    progress(0.3, "云端 AI 识别：上传并识别")
    const r = await fetch(`${s.cloud.url}/${CLOUD_API_VERSION}/detect`, {
      method: "POST", body: form, headers: headers(), signal: AbortSignal.any([signal, AbortSignal.timeout(DETECT_TIMEOUT)]),
    })
    if (r.status === 401 || r.status === 403) throw new Error("访问令牌不对或已过期")
    if (!r.ok) throw new Error(`服务器返回 ${r.status}`)
    const body = sanitizeResponse(await readJsonCapped(r), local.media.duration)
    log.info("云端识别完成", { seconds: (Date.now() - t0) / 1000, findings: body.findings.length })
    progress(1, "云端 AI 识别：完成")
    return mergeCloud(local, body)
  } catch (e) {
    if (signal.aborted) throw new Error("已取消")
    const msg = describe(e)
    log.warn("云端识别失败", msg)
    return mergeCloud(local, null, cloudSkipped(msg, true))
  } finally {
    // engineJson 在进程真正退出后才返回 / 抛出，这里删目录不会和写入冲突
    rmSync(dir, { recursive: true, force: true })
  }
}
