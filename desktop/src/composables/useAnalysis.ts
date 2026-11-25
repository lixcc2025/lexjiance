// 一次检测的状态和操作（全局一份）：打开文件 → 开始检测 → 接收进度、疑点、结果；同时加载时间轴预览素材
import { computed, ref } from "vue"
import type { AnalyzeResult, DetectorInfo, DetectorStatus, EngineEvent, Finding, Preview } from "../types"
import { useHistory } from "./useHistory"

const AUDIO_EXT = /\.(mp3|wav|m4a|aac|amr|flac|ogg|opus|wma)$/i

const file = ref<string | null>(null)
const job = ref<string | null>(null)
const pct = ref(0)
const stage = ref("")
const live = ref<Finding[]>([])
const result = ref<AnalyzeResult | null>(null)
const error = ref("")
const status = ref<Record<string, DetectorStatus>>({})
const preview = ref<Preview | null>(null)
const detectors = ref<DetectorInfo[]>([])
let subscribed = false

export function useAnalysis() {
  const { add } = useHistory()

  const running = computed(() => !!job.value && !result.value && !error.value)
  const findings = computed(() => (result.value ? result.value.findings : live.value))
  const isVideo = computed(() => {
    if (result.value) return !!result.value.media.video
    if (preview.value) return preview.value.frames.length > 0
    return !AUDIO_EXT.test(file.value || "")
  })
  const current = computed(() => detectors.value.find((d) => stage.value.startsWith(d.title + "："))?.name || (stage.value.startsWith("云端") ? "cloud" : ""))

  function reset(path: string | null) {
    file.value = path
    job.value = null
    result.value = null
    error.value = ""
    live.value = []
    status.value = {}
    preview.value = null
    pct.value = 0
    stage.value = ""
  }

  async function start(path: string) {
    if (running.value && job.value) await window.avd.cancel(job.value)
    reset(path)
    stage.value = "启动检测引擎"
    const r = await window.avd.analyze(path)
    if (!r.ok) { error.value = r.error || "启动失败"; return }
    job.value = r.job!
    window.avd.preview(path).then((p) => { if (file.value === path) preview.value = p }).catch(() => {})
  }

  async function openExisting(path: string) {
    if (await window.avd.fileExists(path)) return start(path)
    reset(path)
    error.value = "找不到这个文件，可能已经被移动或删除。"
  }

  function cancel() { if (job.value) window.avd.cancel(job.value) }
  function close() { if (running.value) cancel(); reset(null) }

  function onEvent(ev: EngineEvent) {
    if (ev.job !== job.value) return
    if (ev.type === "progress") { pct.value = ev.pct; stage.value = ev.stage }
    else if (ev.type === "finding") live.value.push(ev)
    else if (ev.type === "detector") status.value = { ...status.value, [ev.name]: ev }
    else if (ev.type === "result") { result.value = ev; add(ev) }
    else if (ev.type === "error") error.value = ev.message
  }

  async function init() {
    if (subscribed) return
    subscribed = true
    window.avd.onEvent(onEvent)
    window.avd.onOpenFile((p) => start(p))
    window.avd.ready() // 监听挂好了，主进程可以把启动时带的文件交过来了
    detectors.value = await window.avd.listDetectors()
  }

  return { file, job, pct, stage, live, result, error, status, preview, detectors, running, findings, isVideo, current, start, openExisting, cancel, close, init }
}
