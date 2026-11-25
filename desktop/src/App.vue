<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue"
import Icon from "./components/Icon.vue"
import HomeView from "./components/HomeView.vue"
import MediaPanel from "./components/MediaPanel.vue"
import VerdictCard from "./components/VerdictCard.vue"
import FindingList from "./components/FindingList.vue"
import DetectorList from "./components/DetectorList.vue"
import { baseName, fmtSize, fmtTime, type AnalyzeResult, type DetectorInfo, type DetectorStatus, type Finding, type HistoryItem } from "./types"

const AUDIO_EXT = /\.(mp3|wav|m4a|aac|amr|flac|ogg|opus|wma)$/i
const HISTORY_KEY = "avd.history"

const file = ref<string | null>(null)
const job = ref<string | null>(null)
const pct = ref(0)
const stage = ref("")
const live = ref<Finding[]>([])
const result = ref<AnalyzeResult | null>(null)
const error = ref("")
const detectors = ref<DetectorInfo[]>([])
const status = ref<Record<string, DetectorStatus>>({})
const active = ref(-1)
const dragging = ref(false)
const panel = ref<InstanceType<typeof MediaPanel> | null>(null)
const detOpen = ref(true)   // 检测项清单：检测中展开当进度，出结果后收起
const history = ref<HistoryItem[]>(loadHistory())

const running = computed(() => !!job.value && !result.value && !error.value)
const findings = computed(() => (result.value ? result.value.findings : live.value))
const isVideo = computed(() => (result.value ? !!result.value.media.video : !AUDIO_EXT.test(file.value || "")))
const mediaUrl = computed(() => (file.value ? "media://file/" + encodeURIComponent(file.value) : ""))
const current = computed(() => detectors.value.find((d) => stage.value.startsWith(d.title + "："))?.name || "")
const shownDetectors = computed(() => {
  if (!result.value) return detectors.value
  // 结果里的顺序和状态为准（包括引擎新加、清单里没有的项）
  return result.value.detectors.map((s) => detectors.value.find((d) => d.name === s.name) || { name: s.name, title: s.title, desc: s.desc, needs: "any", uses_model: false })
})
const counts = computed(() => ({
  ai: findings.value.filter((f) => f.category === "ai" && f.severity !== "info").length,
  edit: findings.value.filter((f) => f.category === "edit" && f.severity !== "info").length,
}))
const detSummary = computed(() => {
  const s = result.value?.detectors || []
  const done = s.filter((d) => d.ok && !d.skipped).length
  const skip = s.filter((d) => d.ok && d.skipped).length
  const err = s.filter((d) => !d.ok).length
  return [`${done} 项完成`, skip ? `${skip} 项未运行` : "", err ? `${err} 项出错` : ""].filter(Boolean).join(" · ")
})
const chips = computed(() => {
  const m = result.value?.media
  if (!m) return []
  const c = [m.format.toUpperCase(), fmtTime(m.duration, false)]
  if (m.video) c.push(`${m.video.width}×${m.video.height}`, m.video.codec?.toUpperCase())
  if (m.audio) c.push(`${m.audio.codec?.toUpperCase()} ${m.audio.sample_rate ? Math.round(m.audio.sample_rate / 100) / 10 + "kHz" : ""}`.trim())
  c.push(fmtSize(m.size))
  return c.filter(Boolean)
})

function loadHistory(): HistoryItem[] {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]") } catch { return [] }
}
function saveHistory(r: AnalyzeResult) {
  const item: HistoryItem = { path: r.file, name: baseName(r.file), time: Date.now(), ai: r.ai.level, edit: r.edit.level, count: r.findings.filter((f) => f.severity !== "info").length }
  history.value = [item, ...history.value.filter((h) => h.path !== r.file)].slice(0, 20)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.value))
}
function clearHistory() {
  history.value = []
  localStorage.removeItem(HISTORY_KEY)
}

async function start(path: string) {
  if (running.value && job.value) await window.avd.cancel(job.value)
  file.value = path
  result.value = null
  error.value = ""
  live.value = []
  status.value = {}
  detOpen.value = true
  active.value = -1
  pct.value = 0
  stage.value = "启动检测引擎"
  job.value = null
  const r = await window.avd.analyze(path)
  if (!r.ok) { error.value = r.error || "启动失败"; return }
  job.value = r.job!
}
async function openFromHistory(path: string) {
  if (await window.avd.fileExists(path)) start(path)
  else { file.value = path; result.value = null; job.value = null; error.value = "找不到这个文件，可能已被移动或删除" }
}
async function choose() {
  const p = await window.avd.pickFile()
  if (p) start(p)
}
function goHome() {
  if (running.value && job.value) window.avd.cancel(job.value)
  file.value = null
  job.value = null
  result.value = null
  error.value = ""
}
function showFolder() { if (file.value) window.avd.showInFolder(file.value) }
function cancel() { if (job.value) window.avd.cancel(job.value) }
function onDrop(e: DragEvent) {
  dragging.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) start(window.avd.pathOf(f))
}
function seekTo(i: number) {
  active.value = i
  const f = findings.value[i]
  if (f?.start !== null && f?.start !== undefined) panel.value?.seek(Math.max(0, f.start - 1)) // 往前留 1 秒，听 / 看接缝前后
}

let off: (() => void) | null = null
onMounted(async () => {
  window.avd.onOpenFile((p) => start(p))
  off = window.avd.onEvent((ev) => {
    if (ev.job !== job.value) return
    if (ev.type === "progress") { pct.value = ev.pct; stage.value = ev.stage }
    else if (ev.type === "finding") live.value.push(ev as Finding)
    else if (ev.type === "detector") status.value = { ...status.value, [ev.name]: ev as DetectorStatus }
    else if (ev.type === "result") { result.value = ev as AnalyzeResult; detOpen.value = false; saveHistory(result.value) }
    else if (ev.type === "error") error.value = ev.message
  })
  detectors.value = await window.avd.listDetectors()
})
onUnmounted(() => off && off())
</script>

<template>
  <div class="app" @dragover.prevent="dragging = true" @dragleave.self.prevent="dragging = false" @drop.prevent="onDrop">
    <header>
      <div class="brand" @click="goHome">
        <div class="logo">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round"><path d="M3 12h2l2-5 3 10 3-12 3 9 2-2h3" /></svg>
        </div>
        <div>
          <div class="name">音视频检测</div>
          <div class="tagline">AI 生成 · 剪辑痕迹</div>
        </div>
      </div>
      <span class="grow" />
      <template v-if="file">
        <button class="ghost" @click="goHome"><Icon name="back" :size="16" />首页</button>
        <button v-if="result" @click="showFolder"><Icon name="folder" :size="16" />所在文件夹</button>
        <button v-if="result || error" @click="start(file!)"><Icon name="refresh" :size="16" />重新检测</button>
      </template>
      <button class="primary" @click="choose"><Icon name="upload" :size="16" />{{ file ? "检测其他文件" : "选择文件" }}</button>
    </header>

    <HomeView v-if="!file" :history="history" :dragging="dragging" @pick="choose" @open="openFromHistory" @clear="clearHistory" />

    <main v-else>
      <div class="filebar card">
        <div class="ficon"><Icon :name="isVideo ? 'video' : 'audio'" :size="22" /></div>
        <div class="fmeta">
          <div class="fname" :title="file">{{ baseName(file) }}</div>
          <div class="fpath" :title="file">{{ file }}</div>
        </div>
        <div class="chips num">
          <span v-for="c in chips" :key="c">{{ c }}</span>
        </div>
      </div>

      <div class="grid">
        <div class="col left">
          <MediaPanel ref="panel" :url="mediaUrl" :is-video="isVideo" :duration="result?.media.duration ?? null"
            :findings="findings" :active="active" @select="(i) => (active = i)" />
          <div class="card box">
            <div class="box-h" :class="{ click: !!result }" @click="result && (detOpen = !detOpen)">
              <span>检测项</span>
              <span v-if="result" class="box-sum">{{ detSummary }}<Icon name="chevron" :size="14" :class="{ up: detOpen }" /></span>
            </div>
            <DetectorList v-if="detOpen || !result" :items="shownDetectors" :status="status" :current="current" />
          </div>
        </div>

        <div class="col right">
          <div v-if="error" class="error card">
            <Icon name="alert" :size="18" />
            <div><b>检测没有完成</b><div>{{ error }}</div></div>
          </div>

          <div v-else-if="running || !result" class="progress card">
            <div class="p-top">
              <div>
                <div class="p-label">正在检测</div>
                <div class="p-stage">{{ stage || "准备中" }}</div>
              </div>
              <div class="p-pct num">{{ Math.round(pct * 100) }}<small>%</small></div>
            </div>
            <div class="bar"><i :style="{ width: Math.max(2, pct * 100) + '%' }" /></div>
            <div class="p-foot">
              <span>已发现 {{ live.filter((f) => f.severity !== "info").length }} 个疑点</span>
              <button class="ghost small" @click="cancel">取消</button>
            </div>
          </div>

          <div v-else class="verdicts">
            <VerdictCard label="AI 生成" icon="sparkles" :verdict="result.ai" :count="counts.ai" />
            <VerdictCard label="剪辑痕迹" icon="scissors" :verdict="result.edit" :count="counts.edit" />
          </div>

          <FindingList :findings="findings" :active="active" :live="running" @select="(i) => (active = i)" @seek="seekTo" />
        </div>
      </div>

      <footer><Icon name="info" :size="13" />检测结果是辅助判断的线索，不是鉴定结论。需要作为证据使用时，应委托司法鉴定机构鉴定。</footer>
    </main>

    <div v-if="dragging && file" class="drop-mask"><div><Icon name="upload" :size="28" />松开即可检测这个文件</div></div>
  </div>
</template>

<style scoped>
.app { height: 100%; display: flex; flex-direction: column; position: relative; }
header { display: flex; align-items: center; gap: 8px; padding: 10px 18px; background: var(--panel); border-bottom: 1px solid var(--line); }
.brand { display: flex; align-items: center; gap: 10px; cursor: pointer; margin-right: 8px; }
.logo { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; background: linear-gradient(135deg, #2346a8, #4a74e8); box-shadow: 0 2px 8px rgba(35, 70, 168, .3); }
.name { font-weight: 650; font-size: 15px; letter-spacing: .5px; }
.tagline { font-size: 11px; color: var(--muted); }
.grow { flex: 1; }

main { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 14px; padding: 16px 18px 10px; }
.filebar { display: flex; align-items: center; gap: 14px; padding: 12px 16px; }
.ficon { width: 42px; height: 42px; border-radius: 10px; background: var(--brand-weak); color: var(--brand); display: grid; place-items: center; flex: none; }
.fmeta { min-width: 0; flex: 1; }
.fname { font-size: 16px; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fpath { font-size: 12px; color: var(--faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; max-width: 50%; }
.chips span { font-size: 12px; color: var(--text-2); background: var(--line-2); border-radius: 6px; padding: 3px 8px; white-space: nowrap; }

.grid { flex: 1; min-height: 0; display: flex; gap: 14px; }
.col { display: flex; flex-direction: column; gap: 14px; min-width: 0; min-height: 0; }
.left { flex: 1.2; overflow: auto; }
.right { flex: 1; }
.box { padding: 12px 16px 8px; flex: none; }
.box-h { display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 13px; color: var(--text-2); padding-bottom: 4px; }
.box-h.click { cursor: pointer; }
.box-sum { display: inline-flex; align-items: center; gap: 4px; font-weight: 400; font-size: 12px; color: var(--muted); }
.box-sum .up { transform: rotate(180deg); }

.verdicts { display: flex; gap: 12px; }
.progress { padding: 16px 18px 12px; }
.p-top { display: flex; justify-content: space-between; align-items: flex-end; }
.p-label { font-size: 12px; color: var(--muted); }
.p-stage { font-size: 14px; margin-top: 4px; color: var(--text); }
.p-pct { font-size: 30px; font-weight: 650; color: var(--brand); line-height: 1; }
.p-pct small { font-size: 14px; margin-left: 2px; }
.bar { height: 6px; background: var(--line-2); border-radius: 3px; overflow: hidden; margin: 12px 0 8px; }
.bar i { display: block; height: 100%; background: linear-gradient(90deg, #2346a8, #4a74e8); border-radius: 3px; transition: width .3s; }
.p-foot { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--muted); }
button.small { height: 26px; padding: 0 10px; font-size: 12px; }
.error { display: flex; gap: 12px; padding: 14px 16px; color: var(--danger); background: var(--danger-bg); box-shadow: none; }
.error div div { color: var(--text-2); font-size: 13px; margin-top: 4px; }

footer { display: flex; align-items: center; gap: 6px; justify-content: center; font-size: 12px; color: var(--faint); padding: 2px 0; }

.drop-mask { position: absolute; inset: 0; background: rgba(35, 70, 168, .12); backdrop-filter: blur(2px); display: grid; place-items: center; pointer-events: none; }
.drop-mask div { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 26px 40px; border-radius: 16px; background: #fff; color: var(--brand); border: 2px dashed var(--brand-2); font-size: 15px; }
</style>
