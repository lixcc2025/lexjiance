<script setup lang="ts">
// 播放器 + 声音波形时间轴：疑点区间标在波形上，点疑点或点波形跳转
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue"
import { fmtTime, type Finding } from "../types"

const props = defineProps<{ url: string; isVideo: boolean; duration: number | null; findings: Finding[]; active: number }>()
const emit = defineEmits<{ (e: "select", index: number): void }>()

const media = ref<HTMLMediaElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const track = ref<HTMLDivElement | null>(null)
const now = ref(0)
const mediaDur = ref(0)
const peaks = ref<Float32Array | null>(null)
const waveState = ref<"loading" | "ok" | "none">("loading")
const hoverT = ref<number | null>(null)
const hoverX = ref(0)

const dur = computed(() => props.duration || mediaDur.value || 0)
const marks = computed(() =>
  props.findings
    .map((f, i) => ({ f, i }))
    .filter(({ f }) => f.start !== null && f.severity !== "info" && dur.value > 0)
    .map(({ f, i }) => {
      const s = f.start as number
      const e = f.end ?? s
      return { i, f, left: (100 * s) / dur.value, width: Math.max(0.5, (100 * (e - s)) / dur.value) }
    }),
)
const ticks = computed(() => (dur.value ? [0, 0.25, 0.5, 0.75, 1].map((r) => ({ r, t: r * dur.value })) : []))

const MAX_DECODE = 300 * 1024 * 1024 // 超过 300MB 的文件不画波形，免得占太多内存
async function loadWave(url: string) {
  peaks.value = null
  waveState.value = "loading"
  try {
    const res = await fetch(url)
    const len = Number(res.headers.get("content-length") || 0)
    if (len > MAX_DECODE) throw new Error("too big")
    const buf = await res.arrayBuffer()
    const ctx = new AudioContext()
    const audio = await ctx.decodeAudioData(buf)
    ctx.close()
    const ch = audio.getChannelData(0)
    const N = 1600
    const out = new Float32Array(N)
    const step = Math.max(1, Math.floor(ch.length / N))
    let max = 0
    for (let i = 0; i < N; i++) {
      let m = 0
      const end = Math.min(ch.length, (i + 1) * step)
      for (let j = i * step; j < end; j += 4) { const v = Math.abs(ch[j]); if (v > m) m = v }
      out[i] = m
      if (m > max) max = m
    }
    if (max > 0) for (let i = 0; i < N; i++) out[i] = Math.pow(out[i] / max, 0.7)
    peaks.value = out
    waveState.value = "ok"
  } catch {
    waveState.value = "none"
  }
  await nextTick()
  draw()
}

function draw() {
  const c = canvas.value
  if (!c) return
  const w = c.clientWidth
  const h = c.clientHeight
  const dpr = window.devicePixelRatio || 1
  c.width = w * dpr
  c.height = h * dpr
  const g = c.getContext("2d")!
  g.scale(dpr, dpr)
  g.clearRect(0, 0, w, h)
  const played = dur.value ? (now.value / dur.value) * w : 0
  if (peaks.value) {
    const p = peaks.value
    const bar = 2, gap = 1
    const n = Math.floor(w / (bar + gap))
    for (let i = 0; i < n; i++) {
      // 每根柱取对应区间里的最大值，不隔点取样（否则语音的波形会显得稀疏）
      const a = Math.floor((i / n) * p.length), b = Math.max(a + 1, Math.floor(((i + 1) / n) * p.length))
      let v = 0
      for (let k = a; k < b; k++) if (p[k] > v) v = p[k]
      const bh = Math.max(2, v * (h - 6))
      const x = i * (bar + gap)
      g.fillStyle = x < played ? "#3a63d6" : "#c3cbdc"
      g.fillRect(x, (h - bh) / 2, bar, bh)
    }
  } else {
    g.fillStyle = "#e4e8f0"
    g.fillRect(0, h / 2 - 2, w, 4)
    g.fillStyle = "#3a63d6"
    g.fillRect(0, h / 2 - 2, played, 4)
  }
}

function seek(t: number, play = true) {
  const m = media.value
  if (!m) return
  m.currentTime = Math.max(0, Math.min(t, dur.value || t))
  now.value = m.currentTime
  draw()
  if (play) m.play().catch(() => {})
}
defineExpose({ seek })

function onTrackClick(e: MouseEvent) {
  const r = track.value!.getBoundingClientRect()
  seek(((e.clientX - r.left) / r.width) * dur.value, false)
}
function onTrackMove(e: MouseEvent) {
  const r = track.value!.getBoundingClientRect()
  hoverX.value = e.clientX - r.left
  hoverT.value = (hoverX.value / r.width) * dur.value
}

let raf = 0
function tick() {
  if (media.value) now.value = media.value.currentTime
  draw()
  if (media.value && !media.value.paused) raf = requestAnimationFrame(tick)
}
function onPlay() { cancelAnimationFrame(raf); raf = requestAnimationFrame(tick) }

let ro: ResizeObserver | null = null
onMounted(() => {
  loadWave(props.url)
  ro = new ResizeObserver(() => draw())
  if (canvas.value) ro.observe(canvas.value)
})
onBeforeUnmount(() => { ro?.disconnect(); cancelAnimationFrame(raf) })
watch(() => props.url, (u) => loadWave(u))
</script>

<template>
  <div class="panel card">
    <div class="stage" :class="{ audio: !isVideo }">
      <video v-if="isVideo" ref="media" :src="url" controls preload="metadata"
        @loadedmetadata="mediaDur = (media as HTMLMediaElement).duration" @play="onPlay" @seeked="tick" />
      <div v-else class="audio-art">
        <div class="disc"><svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z" /><path d="M19 11a7 7 0 0 1-14 0" /><path d="M12 18v3" /></svg></div>
        <audio ref="media" :src="url" controls preload="metadata"
          @loadedmetadata="mediaDur = (media as HTMLMediaElement).duration" @play="onPlay" @seeked="tick" />
      </div>
    </div>

    <div class="timeline">
      <div class="tl-head">
        <span>{{ isVideo ? "声音波形与疑点位置" : "波形与疑点位置" }}</span>
        <span class="num now">{{ fmtTime(now) }} / {{ fmtTime(dur) }}</span>
      </div>
      <div ref="track" class="track" @click="onTrackClick" @mousemove="onTrackMove" @mouseleave="hoverT = null">
        <canvas ref="canvas" />
        <div v-if="waveState === 'loading'" class="wave-tip">正在生成波形…</div>
        <div v-else-if="waveState === 'none'" class="wave-tip">{{ isVideo ? "没有声音或无法生成波形" : "无法生成波形" }}</div>
        <div v-for="m in marks" :key="m.i" class="region" :class="[m.f.severity, { active: m.i === active }]"
          :style="{ left: m.left + '%', width: m.width + '%' }" :title="m.f.title"
          @click.stop="emit('select', m.i); seek(Math.max(0, (m.f.start as number) - 1))" />
        <div class="playhead" :style="{ left: (dur ? (now / dur) * 100 : 0) + '%' }" />
        <div v-if="hoverT !== null" class="hover" :style="{ left: hoverX + 'px' }"><span class="num">{{ fmtTime(hoverT) }}</span></div>
      </div>
      <div class="ticks num">
        <span v-for="t in ticks" :key="t.r" :style="{ left: t.r * 100 + '%' }">{{ fmtTime(t.t, false) }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel { overflow: hidden; display: flex; flex-direction: column; flex: none; }
.stage { background: #0e1424; display: flex; align-items: center; justify-content: center; }
.stage video { width: 100%; max-height: 42vh; aspect-ratio: 16 / 9; display: block; background: #000; }
.stage.audio { background: linear-gradient(135deg, #1f3577 0%, #2d4fae 100%); padding: 26px 24px 18px; }
.audio-art { width: 100%; display: flex; flex-direction: column; align-items: center; gap: 16px; color: #dfe7ff; }
.disc { width: 76px; height: 76px; border-radius: 50%; display: grid; place-items: center; background: rgba(255, 255, 255, .12); border: 1px solid rgba(255, 255, 255, .2); }
.audio-art audio { width: 100%; max-width: 560px; }
.timeline { padding: 12px 16px 10px; }
.tl-head { display: flex; justify-content: space-between; font-size: 12px; color: var(--muted); margin-bottom: 8px; }
.tl-head .now { color: var(--text-2); }
.track { position: relative; height: 64px; cursor: pointer; border-radius: 8px; background: #f7f9fc; }
.track canvas { position: absolute; inset: 4px 0; width: 100%; height: calc(100% - 8px); }
.wave-tip { position: absolute; inset: 0; display: grid; place-items: center; font-size: 12px; color: var(--faint); pointer-events: none; }
.region { position: absolute; top: 0; bottom: 0; border-radius: 3px; background: rgba(201, 160, 0, .16); border-left: 2px solid var(--low); transition: background .15s; }
.region.medium { background: rgba(217, 122, 0, .18); border-left-color: var(--warn); }
.region.high { background: rgba(210, 59, 59, .18); border-left-color: var(--danger); }
.region:hover, .region.active { background: rgba(210, 59, 59, .32); }
.region.medium:hover, .region.medium.active { background: rgba(217, 122, 0, .34); }
.playhead { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; background: var(--brand); border-radius: 1px; pointer-events: none; }
.hover { position: absolute; top: -24px; transform: translateX(-50%); pointer-events: none; }
.hover span { font-size: 11px; background: #1a2233; color: #fff; padding: 2px 6px; border-radius: 4px; }
.ticks { position: relative; height: 16px; margin-top: 4px; font-size: 11px; color: var(--faint); }
.ticks span { position: absolute; transform: translateX(-50%); }
.ticks span:first-child { transform: none; }
.ticks span:last-child { transform: translateX(-100%); }
</style>
