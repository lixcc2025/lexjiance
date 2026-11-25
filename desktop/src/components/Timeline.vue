<script setup lang="ts">
// 多轨时间轴：画面缩略帧 / 声音波形 / 频谱 / 剪辑痕迹 / AI 生成，共用一根播放头。点击或拖动定位
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue"
import Icon from "./Icon.vue"
import { SEV_COLOR, fmtTime, mediaUrl, type Finding, type Preview } from "../types"

const props = defineProps<{
  duration: number
  preview: Preview | null
  findings: Finding[]
  active: number
  now: number
  scanning: boolean
  isVideo: boolean
}>()
const emit = defineEmits<{ (e: "seek", t: number): void; (e: "select", i: number): void }>()

const tracks = ref<HTMLDivElement | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const hoverX = ref<number | null>(null)
const width = ref(800)
const dragging = ref(false)

const dur = computed(() => props.duration || props.preview?.duration || 0)
const pct = (t: number) => (dur.value ? (100 * t) / dur.value : 0)

// 刻度：让主刻度大约 8~12 个
const ticks = computed(() => {
  const d = dur.value
  if (!d) return []
  const steps = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600]
  const step = steps.find((s) => d / s <= 12) || 3600
  const out = []
  for (let t = 0; t <= d + 1e-6; t += step) out.push(t)
  return out.map((t) => ({ t, left: pct(t) }))
})

type Mark = { i: number; f: Finding; left: number; width: number; point: boolean }
function marksOf(cat: "edit" | "ai"): Mark[] {
  return props.findings
    .map((f, i) => ({ f, i }))
    .filter(({ f }) => f.category === cat && f.start !== null && f.severity !== "info")
    .map(({ f, i }) => {
      const s = f.start as number
      const e = f.end ?? s
      return { i, f, left: pct(s), width: Math.max(0, pct(e) - pct(s)), point: e - s < dur.value / 400 }
    })
}
const editMarks = computed(() => marksOf("edit"))
const aiMarks = computed(() => marksOf("ai"))
// 没有位置的 AI 疑点（比如元数据标识）作用于整个文件
const aiWhole = computed(() => props.findings.map((f, i) => ({ f, i })).filter(({ f }) => f.category === "ai" && f.start === null && f.severity !== "info"))
const activeRange = computed(() => {
  const f = props.findings[props.active]
  if (!f || f.start === null) return null
  return { left: pct(f.start), width: Math.max(0.3, pct(f.end ?? f.start) - pct(f.start)) }
})
const hoverT = computed(() => (hoverX.value === null || !dur.value ? null : (hoverX.value / width.value) * dur.value))

function draw() {
  const c = canvas.value
  if (!c) return
  const w = c.clientWidth, h = c.clientHeight
  const dpr = window.devicePixelRatio || 1
  c.width = Math.round(w * dpr); c.height = Math.round(h * dpr)
  const g = c.getContext("2d")!
  g.scale(dpr, dpr)
  g.clearRect(0, 0, w, h)
  const p = props.preview?.waveform || []
  if (!p.length) return
  const css = getComputedStyle(c)
  const base = css.getPropertyValue("--wave").trim() || "#3d4a63"
  const played = css.getPropertyValue("--wave-played").trim() || "#6f9dff"
  const regions = props.findings.filter((f) => f.start !== null && f.severity !== "info").map((f) => [f.start as number, (f.end ?? f.start) as number, SEV_COLOR[f.severity]] as const)
  const sevColor: Record<string, string> = { "var(--low)": css.getPropertyValue("--low").trim(), "var(--warn)": css.getPropertyValue("--warn").trim(), "var(--danger)": css.getPropertyValue("--danger").trim() }
  const bar = 2, gap = 1
  const n = Math.floor(w / (bar + gap))
  const nowX = dur.value ? (props.now / dur.value) * w : 0
  for (let i = 0; i < n; i++) {
    const a = Math.floor((i / n) * p.length), b = Math.max(a + 1, Math.floor(((i + 1) / n) * p.length))
    let v = 0
    for (let k = a; k < b; k++) if (p[k] > v) v = p[k]
    const x = i * (bar + gap)
    const t = (x / w) * dur.value
    const hit = regions.find(([s, e]) => t >= s - dur.value / n && t <= e + dur.value / n)
    const bh = Math.max(1.5, v * (h - 8))
    g.globalAlpha = x <= nowX ? 1 : 0.9
    g.fillStyle = hit ? sevColor[hit[2]] || "#ff5b61" : x <= nowX ? played : base
    g.fillRect(x, (h - bh) / 2, bar, bh)
  }
  g.globalAlpha = 1
}

function posToTime(clientX: number) {
  const r = tracks.value!.getBoundingClientRect()
  return Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * dur.value
}
function down(e: MouseEvent) { dragging.value = true; emit("seek", posToTime(e.clientX)) }
function move(e: MouseEvent) {
  const r = tracks.value!.getBoundingClientRect()
  hoverX.value = Math.max(0, Math.min(r.width, e.clientX - r.left))
  if (dragging.value) emit("seek", posToTime(e.clientX))
}
function up() { dragging.value = false }

let ro: ResizeObserver | null = null
onMounted(() => {
  ro = new ResizeObserver(() => { width.value = tracks.value?.clientWidth || 800; draw() })
  if (tracks.value) ro.observe(tracks.value)
  window.addEventListener("mouseup", up)
})
onBeforeUnmount(() => { ro?.disconnect(); window.removeEventListener("mouseup", up) })
watch(() => [props.preview, props.findings.length, props.now, props.duration], () => draw(), { flush: "post" })
</script>

<template>
  <div class="tl panel">
    <div class="tl-head">
      <span class="label">时间轴</span>
      <span class="legend"><i class="sw edit" />剪辑痕迹</span>
      <span class="legend"><i class="sw ai" />AI 生成</span>
      <span class="grow" />
      <span v-if="scanning" class="scan-tip"><span class="spin" />正在分析</span>
      <span class="tc num">{{ fmtTime(now) }}</span>
    </div>

    <div class="grid">
      <div class="labels">
        <div class="lb ruler-lb" />
        <div v-if="isVideo" class="lb h-frames"><Icon name="video" :size="13" />画面</div>
        <div class="lb h-wave"><Icon name="wave" :size="13" />波形</div>
        <div class="lb h-spec"><Icon name="layers" :size="13" />频谱</div>
        <div class="lb h-mark"><Icon name="scissors" :size="13" />剪辑痕迹</div>
        <div class="lb h-mark"><Icon name="sparkles" :size="13" />AI 生成</div>
      </div>

      <div ref="tracks" class="tracks" @mousedown="down" @mousemove="move" @mouseleave="hoverX = null">
        <div class="ruler">
          <span v-for="t in ticks" :key="t.t" class="tick" :style="{ left: t.left + '%' }"><b class="num">{{ fmtTime(t.t, false) }}</b></span>
        </div>

        <div v-if="isVideo" class="lane h-frames frames">
          <img v-for="(f, k) in preview?.frames || []" :key="k" :src="mediaUrl(f.path)" draggable="false"
            :style="{ left: (100 * k) / (preview?.frames.length || 1) + '%', width: 100 / (preview?.frames.length || 1) + '%' }" />
          <div v-if="!preview" class="ph shimmer" />
        </div>
        <div class="lane h-wave">
          <canvas ref="canvas" />
          <div v-if="!preview" class="ph shimmer" />
          <div v-else-if="!preview.waveform.length" class="none">没有声音</div>
        </div>
        <div class="lane h-spec spec">
          <img v-if="preview?.spectrogram" :src="mediaUrl(preview.spectrogram)" draggable="false" />
          <div v-else-if="!preview" class="ph shimmer" />
          <div v-else class="none">没有声音</div>
        </div>
        <div class="lane h-mark marks">
          <div v-for="m in editMarks" :key="m.i" class="mk" :class="[m.f.severity, { point: m.point, on: m.i === active }]"
            :style="{ left: m.left + '%', width: m.point ? '0' : m.width + '%' }" :title="m.f.title" @mousedown.stop @click.stop="emit('select', m.i)" />
        </div>
        <div class="lane h-mark marks">
          <div v-for="w in aiWhole" :key="'w' + w.i" class="whole" :class="[w.f.severity, { on: w.i === active }]" @mousedown.stop @click.stop="emit('select', w.i)">
            <span>整个文件 · {{ w.f.title }}</span>
          </div>
          <div v-for="m in aiMarks" :key="m.i" class="mk" :class="[m.f.severity, { point: m.point, on: m.i === active }]"
            :style="{ left: m.left + '%', width: m.point ? '0' : m.width + '%' }" :title="m.f.title" @mousedown.stop @click.stop="emit('select', m.i)" />
        </div>

        <div v-if="activeRange" class="focus" :style="{ left: activeRange.left + '%', width: activeRange.width + '%' }" />
        <div v-if="scanning" class="beam" />
        <div v-if="hoverT !== null && !dragging" class="hover" :style="{ left: hoverX + 'px' }"><span class="num">{{ fmtTime(hoverT) }}</span></div>
        <div class="playhead" :style="{ left: pct(now) + '%' }"><i /></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tl { padding: 10px 14px 12px; display: flex; flex-direction: column; }
.tl-head { display: flex; align-items: center; gap: 14px; margin-bottom: 8px; }
.legend { display: inline-flex; align-items: center; gap: 5px; font-size: 11px; color: var(--muted); }
.sw { width: 10px; height: 10px; border-radius: 3px; }
.sw.edit { background: var(--warn); } .sw.ai { background: var(--danger); }
.grow { flex: 1; }
.tc { font-size: 13px; color: var(--text); background: var(--surface-3); border-radius: 6px; padding: 3px 8px; }
.scan-tip { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--accent-2); }
.spin { width: 11px; height: 11px; border-radius: 50%; border: 2px solid var(--accent-bg); border-top-color: var(--accent-2); animation: spin .8s linear infinite; }

.grid { display: flex; gap: 10px; }
.labels { width: 78px; flex: none; display: flex; flex-direction: column; gap: 4px; }
.lb { display: flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--muted); padding-left: 2px; }
.ruler-lb { height: 18px; }
.h-frames { height: 46px; } .h-wave { height: 58px; } .h-spec { height: 58px; } .h-mark { height: 24px; }

.tracks { position: relative; flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px; cursor: crosshair; }
.ruler { position: relative; height: 18px; border-bottom: 1px solid var(--border); }
.tick { position: absolute; top: 0; bottom: 0; border-left: 1px solid var(--border-2); }
.tick b { position: absolute; left: 4px; top: 1px; font-size: 10px; font-weight: 400; color: var(--muted); white-space: nowrap; }
.tick:last-child b { left: auto; right: 4px; }
.lane { position: relative; border-radius: 6px; background: var(--lane); overflow: hidden; border: 1px solid var(--border); }
.frames img { position: absolute; top: 0; height: 100%; object-fit: cover; border-right: 1px solid rgba(0, 0, 0, .35); opacity: .92; }
.lane canvas { position: absolute; inset: 0; width: 100%; height: 100%; }
.spec { background: #000004; }
.spec img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: fill; image-rendering: auto; }
.none { position: absolute; inset: 0; display: grid; place-items: center; font-size: 11px; color: var(--faint); }
.ph { position: absolute; inset: 0; }
.shimmer { background: linear-gradient(90deg, transparent 0%, rgba(127, 140, 170, .12) 50%, transparent 100%); background-size: 50% 100%; background-repeat: no-repeat; animation: sh 1.4s linear infinite; }
@keyframes sh { from { background-position: -50% 0; } to { background-position: 150% 0; } }

.marks { background: transparent; border-style: dashed; }
.mk { position: absolute; top: 3px; bottom: 3px; min-width: 3px; border-radius: 4px; cursor: pointer; --c: var(--low); background: color-mix(in srgb, var(--c) 35%, transparent); border: 1px solid var(--c); }
.mk.medium { --c: var(--warn); } .mk.high { --c: var(--danger); }
.mk.point { width: 0 !important; min-width: 0; border: none; background: none; }
.mk.point::before { content: ""; position: absolute; left: -6px; top: 50%; width: 10px; height: 10px; margin-top: -5px; transform: rotate(45deg); background: var(--c); border-radius: 2px; box-shadow: 0 0 0 2px var(--surface); }
.mk.on, .mk:hover { box-shadow: 0 0 0 2px color-mix(in srgb, var(--c) 45%, transparent), 0 0 14px var(--c); }
.whole { position: absolute; inset: 3px 0; border-radius: 4px; cursor: pointer; display: flex; align-items: center; padding: 0 8px; overflow: hidden; --c: var(--danger);
  background: repeating-linear-gradient(135deg, color-mix(in srgb, var(--c) 22%, transparent) 0 8px, color-mix(in srgb, var(--c) 10%, transparent) 8px 16px); border: 1px solid color-mix(in srgb, var(--c) 60%, transparent); }
.whole.medium { --c: var(--warn); }
.whole span { font-size: 11px; color: var(--text); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.whole.on { box-shadow: 0 0 0 2px color-mix(in srgb, var(--c) 45%, transparent); }

.focus { position: absolute; top: 18px; bottom: 0; min-width: 2px; background: rgba(255, 255, 255, .06); border-left: 1px dashed var(--border-2); border-right: 1px dashed var(--border-2); pointer-events: none; }
.playhead { position: absolute; top: 0; bottom: -2px; width: 2px; margin-left: -1px; background: var(--accent-2); box-shadow: 0 0 10px var(--accent-glow); pointer-events: none; }
.playhead i { position: absolute; top: -1px; left: -5px; width: 12px; height: 12px; background: var(--accent-2); clip-path: polygon(0 0, 100% 0, 100% 55%, 50% 100%, 0 55%); }
.hover { position: absolute; top: 18px; bottom: 0; border-left: 1px solid var(--border-2); pointer-events: none; }
.hover span { position: absolute; top: -18px; left: 4px; font-size: 10px; color: var(--text); background: var(--surface-3); border-radius: 4px; padding: 1px 5px; white-space: nowrap; }
.beam { position: absolute; top: 18px; bottom: 0; width: 120px; pointer-events: none; animation: beam 2.2s linear infinite;
  background: linear-gradient(90deg, transparent, rgba(126, 171, 255, .16) 80%, rgba(170, 200, 255, .65) 100%); border-right: 1px solid rgba(190, 215, 255, .8); }
@keyframes beam { from { left: -120px; } to { left: 100%; } }
</style>
