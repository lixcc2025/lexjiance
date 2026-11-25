<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue"
import type { AnalyzeResult, Finding, Severity, Verdict } from "./types"

const file = ref<string | null>(null)
const job = ref<string | null>(null)
const pct = ref(0)
const stage = ref("")
const live = ref<Finding[]>([])          // 检测过程中陆续出来的疑点
const result = ref<AnalyzeResult | null>(null)
const error = ref("")
const showInfo = ref(false)              // 是否显示「说明」类条目
const expanded = ref<number | null>(null)
const dragging = ref(false)
const player = ref<HTMLMediaElement | null>(null)

const running = computed(() => !!job.value && !result.value && !error.value)
const isVideo = computed(() => !!result.value?.media.video || /\.(mp4|mov|m4v|avi|mkv|webm|3gp|flv|ts)$/i.test(file.value || ""))
const mediaUrl = computed(() => (file.value ? "media://" + encodeURIComponent(file.value) : ""))
const findings = computed(() => {
  const all = result.value ? result.value.findings : live.value
  return showInfo.value ? all : all.filter((f) => f.severity !== "info")
})
const marks = computed(() => {
  const d = result.value?.media.duration
  if (!d) return []
  return (result.value?.findings || [])
    .filter((f) => f.start !== null && f.severity !== "info")
    .map((f) => ({ f, left: (100 * (f.start as number)) / d, width: f.end !== null ? Math.max(0.6, (100 * ((f.end as number) - (f.start as number))) / d) : 0.6 }))
})

const SEV: Record<Severity, string> = { info: "说明", low: "轻微", medium: "可疑", high: "高度可疑" }
const CAT: Record<string, string> = { ai: "AI 生成", edit: "剪辑痕迹", source: "来源信息" }
const LEVEL: Record<Verdict["level"], string> = { none: "未发现", suspicious: "有疑点", likely: "高度可疑", unknown: "无法判断" }

function fmt(t: number | null) {
  if (t === null) return ""
  const m = Math.floor(t / 60)
  const s = t - m * 60
  return `${String(m).padStart(2, "0")}:${s.toFixed(2).padStart(5, "0")}`
}

async function start(path: string) {
  if (running.value && job.value) await window.avd.cancel(job.value)
  file.value = path
  result.value = null
  error.value = ""
  live.value = []
  pct.value = 0
  stage.value = "启动检测引擎"
  expanded.value = null
  const r = await window.avd.analyze(path)
  if (!r.ok) { error.value = r.error || "启动失败"; return }
  job.value = r.job!
}

async function choose() {
  const p = await window.avd.pickFile()
  if (p) start(p)
}

function onDrop(e: DragEvent) {
  dragging.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) start(window.avd.pathOf(f))
}

function cancelJob() {
  if (job.value) window.avd.cancel(job.value)
}

function seek(f: Finding) {
  if (f.start === null || !player.value) return
  player.value.currentTime = Math.max(0, f.start - 1)   // 往前留 1 秒，方便听 / 看接缝前后
  player.value.play()
}

let off: (() => void) | null = null
onMounted(() => {
  window.avd.onOpenFile((p) => start(p))
  off = window.avd.onEvent((ev) => {
    if (ev.job !== job.value) return
    if (ev.type === "progress") { pct.value = ev.pct; stage.value = ev.stage }
    else if (ev.type === "finding") live.value.push(ev as Finding)
    else if (ev.type === "result") result.value = ev as AnalyzeResult
    else if (ev.type === "error") error.value = ev.message
  })
})
onUnmounted(() => off && off())
</script>

<template>
  <div class="app" @dragover.prevent="dragging = true" @dragleave.prevent="dragging = false" @drop.prevent="onDrop">
    <header>
      <b>音视频检测</b>
      <span class="sub">判断是否 AI 生成、有无剪辑痕迹 · 本机离线检测，文件不上传</span>
      <span class="grow" />
      <button class="primary" @click="choose">选择文件</button>
    </header>

    <div v-if="!file" class="empty" :class="{ on: dragging }">
      <p>把视频或音频文件拖到这里，或点右上角「选择文件」</p>
      <p class="hint">支持 MP4、MOV、AVI、MKV、MP3、WAV、M4A、AMR 等常见格式</p>
    </div>

    <main v-else>
      <section class="left">
        <div class="filename" :title="file">{{ file }}</div>
        <video v-if="isVideo" ref="player" :src="mediaUrl" controls />
        <audio v-else ref="player" :src="mediaUrl" controls />
        <div v-if="marks.length" class="timeline" title="红色是疑点位置，点击疑点可跳转">
          <span v-for="(m, i) in marks" :key="i" class="mark" :class="m.f.severity" :style="{ left: m.left + '%', width: m.width + '%' }" @click="seek(m.f)" />
        </div>
        <div v-if="result" class="meta">
          <span>格式 {{ result.media.format }}</span>
          <span>时长 {{ fmt(result.media.duration) }}</span>
          <span v-if="result.media.video">画面 {{ result.media.video.width }}×{{ result.media.video.height }} {{ result.media.video.codec }}</span>
          <span v-if="result.media.audio">声音 {{ result.media.audio.codec }} {{ result.media.audio.sample_rate }}Hz</span>
        </div>
        <div v-if="result" class="detectors">
          <div class="h">检测项</div>
          <div v-for="d in result.detectors" :key="d.name" class="det">
            <span>{{ d.title }}</span>
            <span :class="d.ok ? (d.skipped ? 'skip' : 'done') : 'err'">{{ !d.ok ? "出错" : d.skipped ? "未运行：" + d.skipped : "完成" }}</span>
          </div>
        </div>
      </section>

      <section class="right">
        <div v-if="running" class="progress">
          <div class="bar"><i :style="{ width: pct * 100 + '%' }" /></div>
          <div class="stage">{{ stage }}</div>
          <button @click="cancelJob">取消</button>
        </div>
        <div v-if="error" class="error">{{ error }}</div>

        <div v-if="result" class="verdicts">
          <div class="verdict" :class="result.ai.level">
            <div class="k">AI 生成</div>
            <div class="v">{{ LEVEL[result.ai.level] }}</div>
            <div class="t">{{ result.ai.text }}</div>
          </div>
          <div class="verdict" :class="result.edit.level">
            <div class="k">剪辑痕迹</div>
            <div class="v">{{ LEVEL[result.edit.level] }}</div>
            <div class="t">{{ result.edit.text }}</div>
          </div>
        </div>

        <div class="list-head">
          <span>疑点 {{ findings.length }}</span>
          <label><input v-model="showInfo" type="checkbox" /> 显示来源信息</label>
        </div>
        <div class="list">
          <div v-for="(f, i) in findings" :key="i" class="item" :class="f.severity" @click="expanded = expanded === i ? null : i">
            <div class="row">
              <span class="sev">{{ SEV[f.severity] }}</span>
              <span class="cat">{{ CAT[f.category] }}</span>
              <span class="title">{{ f.title }}</span>
              <a v-if="f.start !== null" class="time" @click.stop="seek(f)">{{ fmt(f.start) }}<template v-if="f.end !== null"> – {{ fmt(f.end) }}</template> ▶</a>
            </div>
            <div v-if="expanded === i" class="more">
              <p>{{ f.detail }}</p>
              <pre v-if="Object.keys(f.evidence).length">{{ JSON.stringify(f.evidence, null, 2) }}</pre>
            </div>
          </div>
          <div v-if="result && !findings.length" class="none">没有发现疑点</div>
        </div>
        <p v-if="result" class="note">检测结果是辅助判断的线索，不是鉴定结论。需要作为证据使用时，应委托司法鉴定机构鉴定。</p>
      </section>
    </main>
  </div>
</template>

<style scoped>
.app { height: 100vh; display: flex; flex-direction: column; }
header { display: flex; align-items: center; gap: 12px; padding: 10px 16px; background: #fff; border-bottom: 1px solid #e5e6eb; }
header .sub { color: #86909c; font-size: 13px; }
.grow { flex: 1; }
.empty { flex: 1; margin: 24px; border: 2px dashed #c9cdd4; border-radius: 12px; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #4e5969; }
.empty.on { border-color: #2f5bea; background: #eef2ff; }
.empty .hint { color: #86909c; font-size: 13px; }
main { flex: 1; display: flex; gap: 16px; padding: 16px; min-height: 0; }
.left { flex: 1.2; display: flex; flex-direction: column; gap: 10px; min-width: 0; overflow: auto; }
.right { flex: 1; display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.filename { font-size: 13px; color: #4e5969; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
video { width: 100%; max-height: 50vh; background: #000; border-radius: 8px; }
audio { width: 100%; }
.timeline { position: relative; height: 14px; background: #e5e6eb; border-radius: 7px; }
.mark { position: absolute; top: 0; height: 14px; border-radius: 3px; cursor: pointer; background: #f7ba1e; }
.mark.medium { background: #ff7d00; }
.mark.high { background: #f53f3f; }
.meta { display: flex; flex-wrap: wrap; gap: 12px; font-size: 13px; color: #4e5969; }
.detectors { background: #fff; border-radius: 8px; padding: 10px 12px; font-size: 13px; }
.detectors .h { font-weight: 600; margin-bottom: 6px; }
.det { display: flex; justify-content: space-between; padding: 3px 0; }
.det .done { color: #00b42a; } .det .skip { color: #86909c; } .det .err { color: #f53f3f; }
.progress { background: #fff; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; gap: 8px; }
.bar { height: 6px; background: #e5e6eb; border-radius: 3px; overflow: hidden; }
.bar i { display: block; height: 100%; background: #2f5bea; transition: width .2s; }
.stage { font-size: 13px; color: #4e5969; }
.error { background: #ffece8; color: #cb2634; border-radius: 8px; padding: 10px 12px; }
.verdicts { display: flex; gap: 10px; }
.verdict { flex: 1; background: #fff; border-radius: 8px; padding: 12px; border-left: 4px solid #c9cdd4; }
.verdict.none { border-color: #00b42a; } .verdict.suspicious { border-color: #ff7d00; } .verdict.likely { border-color: #f53f3f; }
.verdict .k { font-size: 13px; color: #86909c; } .verdict .v { font-size: 20px; font-weight: 600; margin: 2px 0; } .verdict .t { font-size: 13px; color: #4e5969; }
.list-head { display: flex; justify-content: space-between; font-size: 13px; color: #4e5969; }
.list { flex: 1; overflow: auto; display: flex; flex-direction: column; gap: 6px; }
.item { background: #fff; border-radius: 8px; padding: 8px 10px; cursor: pointer; border-left: 3px solid #c9cdd4; }
.item.low { border-color: #f7ba1e; } .item.medium { border-color: #ff7d00; } .item.high { border-color: #f53f3f; }
.row { display: flex; align-items: baseline; gap: 8px; font-size: 14px; }
.sev, .cat { font-size: 12px; color: #86909c; white-space: nowrap; }
.title { flex: 1; }
.time { font-size: 12px; color: #2f5bea; white-space: nowrap; }
.more p { font-size: 13px; color: #4e5969; margin: 6px 0; }
.more pre { font-size: 12px; background: #f7f8fa; padding: 8px; border-radius: 6px; white-space: pre-wrap; word-break: break-all; margin: 0; }
.none { color: #86909c; font-size: 13px; padding: 8px; }
.note { font-size: 12px; color: #86909c; margin: 0; }
</style>
