// 一次检测：本机引擎（不用模型）→ 云端 AI 识别（启用时）→ 合并成一个结果推给页面。
// 进度：启用云端时本机占 0~60%，云端占 60~100%；不启用时本机占全部。
// 取消：结束整棵进程树（含 ffmpeg）；云端阶段取消也只回「检测已取消」，不产出结果、不进检测记录。
// 文件能不能检测由 ipc 先用 access.allowMedia 把关（必须是音视频文件），这里不再放行路径。

import type { ChildProcess } from "child_process"
import { basename } from "path"
import type { AnalyzeResult, EngineEvent } from "../../shared/schema"
import { engineStream } from "./engine"
import { killTree } from "./proc"
import { withCloud } from "./cloud"
import { getSettings } from "./settings"
import { log } from "./log"

type Send = (ev: EngineEvent) => void

interface Job { child: ChildProcess | null; abort: AbortController; done: boolean }
const jobs = new Map<string, Job>()

export function startAnalysis(file: string, send: Send): { ok: boolean; job?: string; error?: string } {
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6)
  const job: Job = { child: null, abort: new AbortController(), done: false }
  jobs.set(id, job)
  const cloudOn = getSettings().cloud.enabled
  const localShare = cloudOn ? 0.6 : 1
  const emit = (ev: any) => { if (!job.done) send({ job: id, ...ev }) }
  const finish = (ev: any) => { emit(ev); job.done = true; jobs.delete(id) }
  const cancelled = () => finish({ type: "error", message: "检测已取消" })
  log.info("开始检测", { file: basename(file), cloud: cloudOn }) // 日志只记文件名，不记完整路径（问题清单 P2-7）

  let local: AnalyzeResult | null = null
  job.child = engineStream(["analyze", file, "--jsonl"], (ev) => {
    if (ev.type === "progress") emit({ ...ev, pct: Number(ev.pct) * localShare })
    else if (ev.type === "result") local = ev as unknown as AnalyzeResult
    else if (ev.type === "error") finish(ev)
    else emit(ev)
  }, async (code, stderr) => {
    job.child = null
    if (job.done) return
    if (job.abort.signal.aborted) return cancelled()
    if (!local) return finish({ type: "error", message: code === -1 ? "检测引擎启动失败：" + stderr : `检测引擎异常退出（${code}）：${stderr.slice(-400)}` })
    try {
      const merged = await withCloud(file, local, (p, stage) => emit({ type: "progress", pct: localShare + (1 - localShare) * p, stage }), job.abort.signal)
      if (job.abort.signal.aborted) return cancelled()
      for (const d of merged.detectors.slice(local.detectors.length)) emit({ type: "detector", ...d })
      finish({ type: "result", ...merged })
    } catch {
      cancelled()
    }
  })
  return { ok: true, job: id }
}

export function cancelAnalysis(id: string) {
  const j = jobs.get(id)
  if (!j) return
  j.abort.abort()
  if (j.child) killTree(j.child)
}

export function cancelAll() {
  for (const id of [...jobs.keys()]) cancelAnalysis(id)
}
