<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import Icon from "./components/Icon.vue"
import Sidebar from "./components/Sidebar.vue"
import HomeHero from "./components/HomeHero.vue"
import Viewer from "./components/Viewer.vue"
import Timeline from "./components/Timeline.vue"
import VerdictPanel from "./components/VerdictPanel.vue"
import FindingsPanel from "./components/FindingsPanel.vue"
import { baseName, fmtSize, fmtTime, mediaUrl, type AnalyzeResult, type DetectorInfo, type DetectorStatus, type Finding, type HistoryItem, type Preview } from "./types"

const AUDIO_EXT = /\.(mp3|wav|m4a|aac|amr|flac|ogg|opus|wma)$/i
const HISTORY_KEY = "avd.history"

const mac = ref(false)
const theme = ref(localStorage.getItem("avd.theme") || "system")
function setTheme(t: string) { theme.value = t; localStorage.setItem("avd.theme", t); window.avd.setTheme(t) }
const file = ref<string | null>(null)
const job = ref<string | null>(null)
const pct = ref(0)
const stage = ref("")
const live = ref<Finding[]>([])
const result = ref<AnalyzeResult | null>(null)
const error = ref("")
const detectors = ref<DetectorInfo[]>([])
const status = ref<Record<string, DetectorStatus>>({})
const preview = ref<Preview | null>(null)
const active = ref(-1)
const now = ref(0)
const mediaDur = ref(0)
const dragging = ref(false)
const viewer = ref<InstanceType<typeof Viewer> | null>(null)
const history = ref<HistoryItem[]>(loadHistory())

const running = computed(() => !!job.value && !result.value && !error.value)
const findings = computed(() => (result.value ? result.value.findings : live.value))
const isVideo = computed(() => (result.value ? !!result.value.media.video : preview.value ? preview.value.frames.length > 0 || !AUDIO_EXT.test(file.value || "") : !AUDIO_EXT.test(file.value || "")))
const duration = computed(() => result.value?.media.duration || preview.value?.duration || mediaDur.value || 0)
const current = computed(() => detectors.value.find((d) => stage.value.startsWith(d.title + "："))?.name || "")
const chips = computed(() => {
  const m = result.value?.media
  if (!m) return []
  const c: string[] = [m.format.toUpperCase(), fmtTime(m.duration, false)]
  if (m.video) c.push(`${m.video.width}×${m.video.height}`, String(m.video.codec || "").toUpperCase())
  if (m.audio) c.push(`${String(m.audio.codec || "").toUpperCase()} ${m.audio.sample_rate ? Math.round(m.audio.sample_rate / 100) / 10 + "kHz" : ""}`.trim())
  c.push(fmtSize(m.size))
  return c.filter(Boolean)
})

function loadHistory(): HistoryItem[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]") } catch { return [] }
}
function saveHistory(r: AnalyzeResult) {
  const item: HistoryItem = { path: r.file, name: baseName(r.file), time: Date.now(), ai: r.ai.level, edit: r.edit.level, count: r.findings.filter((f) => f.severity !== "info").length }
  history.value = [item, ...history.value.filter((h) => h.path !== r.file)].slice(0, 30)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
}
function clearHistory() { history.value = []; localStorage.removeItem(HISTORY_KEY) }

async function start(path: string) {
  if (running.value && job.value) await window.avd.cancel(job.value)
  file.value = path
  result.value = null
  error.value = ""
  live.value = []
  status.value = {}
  preview.value = null
  active.value = -1
  now.value = 0
  mediaDur.value = 0
  pct.value = 0
  stage.value = "启动检测引擎"
  job.value = null
  const r = await window.avd.analyze(path)
  if (!r.ok) { error.value = r.error || "启动失败"; return }
  job.value = r.job!
  window.avd.preview(path).then((p) => { if (file.value === path) preview.value = p })
}
async function openFromHistory(path: string) {
  if (await window.avd.fileExists(path)) start(path)
  else { file.value = path; result.value = null; job.value = null; preview.value = null; error.value = "找不到这个文件，可能已经被移动或删除。" }
}
async function choose() { const p = await window.avd.pickFile(); if (p) start(p) }
function goHome() {
  if (running.value && job.value) window.avd.cancel(job.value)
  file.value = null; job.value = null; result.value = null; error.value = ""; preview.value = null
}
function showFolder() { if (file.value) window.avd.showInFolder(file.value) }
function cancel() { if (job.value) window.avd.cancel(job.value) }
function onDrop(e: DragEvent) {
  dragging.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) start(window.avd.pathOf(f))
}
function seekTo(t: number) { viewer.value?.seek(t) }
function select(i: number) {
  active.value = i
  const f = findings.value[i]
  if (f && f.start !== null) seekTo(Math.max(0, f.start - 1)) // 往前留 1 秒，看 / 听接缝前后
}
function playFinding(i: number) {
  active.value = i
  const f = findings.value[i]
  if (f && f.start !== null) viewer.value?.seek(Math.max(0, f.start - 1), true)
}

function onKey(e: KeyboardEvent) {
  if ((e.target as HTMLElement)?.tagName === "INPUT") return
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "o") { e.preventDefault(); choose(); return }
  if (!file.value) return
  if (e.key === " ") { e.preventDefault(); viewer.value?.toggle() }
  else if (e.key === "ArrowLeft") seekTo(now.value - (e.shiftKey ? 5 : 1))
  else if (e.key === "ArrowRight") seekTo(now.value + (e.shiftKey ? 5 : 1))
  else if (e.key === "Escape") active.value = -1
}

let off: (() => void) | null = null
onMounted(async () => {
  const info = await window.avd.appInfo()
  mac.value = info.platform === "darwin"
  document.body.classList.toggle("mac", mac.value)
  window.avd.setTheme(theme.value)
  window.avd.onOpenFile((p) => start(p))
  window.avd.onMenu((c) => { if (c === "open") choose() })
  off = window.avd.onEvent((ev) => {
    if (ev.job !== job.value) return
    if (ev.type === "progress") { pct.value = ev.pct; stage.value = ev.stage }
    else if (ev.type === "finding") live.value.push(ev as Finding)
    else if (ev.type === "detector") status.value = { ...status.value, [ev.name]: ev as DetectorStatus }
    else if (ev.type === "result") { result.value = ev as AnalyzeResult; saveHistory(result.value) }
    else if (ev.type === "error") error.value = ev.message
  })
  window.addEventListener("keydown", onKey)
  detectors.value = await window.avd.listDetectors()
})
onBeforeUnmount(() => { off && off(); window.removeEventListener("keydown", onKey) })
</script>

<template>
  <div class="shell" @dragover.prevent="dragging = true" @dragleave.self.prevent="dragging = false" @drop.prevent="onDrop">
    <Sidebar :history="history" :active="file" :engine-ready="detectors.length > 0" :mac="mac" :theme="theme" @new="choose" @open="openFromHistory" @home="goHome" @clear="clearHistory" @theme="setTheme" />

    <section class="main">
      <HomeHero v-if="!file" :dragging="dragging" :mac="mac" @pick="choose" />

      <template v-else>
        <header class="bar drag">
          <div class="fi"><Icon :name="isVideo ? 'video' : 'audio'" :size="16" /></div>
          <div class="fn">
            <div class="name">{{ baseName(file) }}</div>
            <div class="path selectable nodrag" :title="file">{{ file }}</div>
          </div>
          <div class="chips num">
            <span v-for="c in chips" :key="c">{{ c }}</span>
          </div>
          <div class="acts nodrag">
            <button v-if="result || error" class="flat" title="重新检测" @click="start(file!)"><Icon name="refresh" :size="14" />重新检测</button>
            <button class="flat" :title="mac ? '在访达中显示' : '在文件夹中显示'" @click="showFolder"><Icon name="folder" :size="14" />{{ mac ? "在访达中显示" : "所在文件夹" }}</button>
          </div>
        </header>

        <div class="work">
          <div class="stage-col">
            <div class="viewer-wrap">
              <Viewer ref="viewer" :key="file" :url="mediaUrl(file)" :is-video="isVideo" :name="baseName(file)"
                :art="preview?.spectrogram ? mediaUrl(preview.spectrogram) : null" @time="(t) => (now = t)" @duration="(d) => (mediaDur = d)" />
            </div>
            <Timeline :duration="duration" :preview="preview" :findings="findings" :active="active" :now="now" :scanning="running" :is-video="isVideo"
              @seek="seekTo" @select="select" />
          </div>
          <div class="side-col">
            <VerdictPanel :result="result" :error="error" :pct="pct" :stage="stage" :detectors="detectors" :status="status" :current="current" :live="live"
              @cancel="cancel" @retry="start(file!)" />
            <FindingsPanel :findings="findings" :active="active" :running="running" @select="select" @seek="playFinding" />
          </div>
        </div>

        <footer class="status">
          <span><Icon name="info" :size="12" />检测结果是辅助判断的线索，不是鉴定结论；作为证据使用应委托司法鉴定机构</span>
          <span class="grow" />
          <span class="keys">空格 播放 · ←/→ 1 秒 · Shift+←/→ 5 秒</span>
        </footer>
      </template>
    </section>

    <div v-if="dragging" class="mask"><div class="mask-box"><Icon name="upload" :size="26" />松开即可开始检测</div></div>
  </div>
</template>

<style scoped>
.shell { height: 100%; display: flex; position: relative; }
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--bg); }

.bar { height: 60px; flex: none; display: flex; align-items: center; gap: 12px; padding: 0 16px 0 18px; border-bottom: 1px solid var(--border); background: var(--surface); }
.fi { width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center; color: var(--accent-2); background: var(--accent-bg); flex: none; }
.fn { min-width: 0; flex: 0 1 auto; max-width: 34%; }
.name { font-size: 14px; font-weight: 650; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.path { font-size: 11px; color: var(--faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px; }
.chips { display: flex; gap: 5px; flex-wrap: nowrap; overflow: hidden; flex: 1; }
.chips span { font-size: 11px; color: var(--text-2); background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px; padding: 2px 7px; white-space: nowrap; }
.acts { display: flex; gap: 4px; flex: none; }
.acts button { height: 28px; font-size: 12px; }

.work { flex: 1; min-height: 0; display: flex; gap: 12px; padding: 12px; }
.stage-col { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 12px; }
.viewer-wrap { flex: 1; min-height: 200px; }
.side-col { width: 384px; flex: none; display: flex; flex-direction: column; gap: 12px; min-height: 0; }

.status { height: 28px; flex: none; display: flex; align-items: center; gap: 8px; padding: 0 16px; font-size: 11px; color: var(--faint); border-top: 1px solid var(--border); background: var(--surface); }
.status span { display: inline-flex; align-items: center; gap: 5px; }
.grow { flex: 1; }
.keys { font-family: var(--mono); font-size: 10.5px; }

.mask { position: absolute; inset: 0; z-index: 10; display: grid; place-items: center; pointer-events: none; background: rgba(10, 14, 24, .45); backdrop-filter: blur(4px); }
.mask-box { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 28px 44px; border-radius: 18px; color: var(--accent-2); font-size: 14px;
  background: var(--surface); border: 1.5px dashed var(--accent); box-shadow: 0 0 0 6px var(--accent-bg), 0 20px 60px rgba(0, 0, 0, .4); }
</style>
