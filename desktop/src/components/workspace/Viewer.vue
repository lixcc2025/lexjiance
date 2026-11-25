<script setup lang="ts">
// 播放器：自绘控制条（时间码、倍速、静音、全屏）。时间轴负责拖动定位，这里只管播放
import { onBeforeUnmount, ref } from "vue"
import Icon from "../common/Icon.vue"
import { fmtTime } from "../../types"

const props = defineProps<{ url: string; isVideo: boolean; art: string | null; name: string }>()
const emit = defineEmits<{ (e: "time", t: number): void; (e: "duration", d: number): void }>()

const el = ref<HTMLMediaElement | null>(null)
const box = ref<HTMLDivElement | null>(null)
const playing = ref(false)
const now = ref(0)
const dur = ref(0)
const rate = ref(1)
const muted = ref(false)
const RATES = [0.5, 0.75, 1, 1.5, 2]

let raf = 0
function loop() {
  if (el.value) { now.value = el.value.currentTime; emit("time", now.value) }
  if (playing.value) raf = requestAnimationFrame(loop)
}
function onPlay() { playing.value = true; cancelAnimationFrame(raf); raf = requestAnimationFrame(loop) }
function onPause() { playing.value = false; loop() }
function onMeta() { dur.value = el.value?.duration || 0; emit("duration", dur.value) }

function toggle() { const m = el.value; if (!m) return; m.paused ? m.play().catch(() => {}) : m.pause() }
function seek(t: number, play = false) {
  const m = el.value
  if (!m) return
  m.currentTime = Math.max(0, Math.min(t, dur.value || t))
  now.value = m.currentTime
  emit("time", now.value)
  if (play) m.play().catch(() => {})
}
function cycleRate() {
  rate.value = RATES[(RATES.indexOf(rate.value) + 1) % RATES.length]
  if (el.value) el.value.playbackRate = rate.value
}
function toggleMute() { muted.value = !muted.value; if (el.value) el.value.muted = muted.value }
function full() { box.value?.requestFullscreen?.() }
defineExpose({ seek, toggle, pause: () => el.value?.pause(), get time() { return now.value } })
onBeforeUnmount(() => cancelAnimationFrame(raf))
</script>

<template>
  <div ref="box" class="viewer" :class="{ audio: !isVideo }">
    <video v-if="isVideo" ref="el" :src="url" preload="metadata" @play="onPlay" @pause="onPause" @loadedmetadata="onMeta" @seeked="loop" @click="toggle" @ended="onPause" />
    <template v-else>
      <div class="art" :style="art ? { backgroundImage: `url(${art})` } : {}" />
      <div class="audio-face">
        <div class="disc"><Icon name="audio" :size="30" :stroke="1.6" /></div>
        <div class="an">{{ name }}</div>
        <div class="tc num">{{ fmtTime(now) }}<span> / {{ fmtTime(dur) }}</span></div>
      </div>
      <audio ref="el" :src="url" preload="metadata" @play="onPlay" @pause="onPause" @loadedmetadata="onMeta" @seeked="loop" @ended="onPause" />
    </template>

    <button v-if="!playing && isVideo" class="bigplay" @click="toggle"><Icon name="play" :size="22" :stroke="2" /></button>

    <div class="bar">
      <button class="flat icon" :title="playing ? '暂停（空格）' : '播放（空格）'" @click="toggle"><Icon :name="playing ? 'pause' : 'play'" :size="14" :stroke="2.2" /></button>
      <span class="time num">{{ fmtTime(now) }} <i>/</i> {{ fmtTime(dur) }}</span>
      <span class="grow" />
      <button class="flat pill num" title="播放速度" @click="cycleRate">{{ rate }}×</button>
      <button class="flat icon" :title="muted ? '取消静音' : '静音'" @click="toggleMute">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5L6 9H2v6h4l5 4z" /><path v-if="!muted" d="M15.5 8.5a5 5 0 0 1 0 7M19 5a10 10 0 0 1 0 14" /><path v-else d="M22 9l-6 6M16 9l6 6" /></svg>
      </button>
      <button v-if="isVideo" class="flat icon" title="全屏" @click="full">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" /></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.viewer { position: relative; border-radius: var(--radius); overflow: hidden; background: #000; border: 1px solid var(--border); height: 100%; min-height: 0; display: flex; }
video { width: 100%; height: 100%; object-fit: contain; display: block; background: #000; cursor: pointer; }
.viewer.audio { background: #0b0d12; }
.art { position: absolute; inset: 0; background-size: 100% 100%; filter: blur(2px) saturate(1.2); opacity: .55; transform: scale(1.04); }
.audio .art::after { content: ""; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(11, 13, 18, .2) 0%, rgba(11, 13, 18, .85) 85%); }
.audio-face { position: relative; margin: auto; display: flex; flex-direction: column; align-items: center; gap: 10px; color: #e6ecff; padding-bottom: 30px; }
.disc { width: 74px; height: 74px; border-radius: 22px; display: grid; place-items: center; background: rgba(255, 255, 255, .1); border: 1px solid rgba(255, 255, 255, .18); backdrop-filter: blur(10px); box-shadow: 0 10px 30px rgba(0, 0, 0, .35); }
.an { font-size: 14px; font-weight: 600; max-width: 80%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tc { font-size: 26px; font-weight: 500; letter-spacing: .5px; }
.tc span { font-size: 14px; color: rgba(230, 236, 255, .5); }
.bigplay { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); width: 58px; height: 58px; border-radius: 50%; padding: 0;
  background: rgba(20, 24, 34, .55); border: 1px solid rgba(255, 255, 255, .25); color: #fff; backdrop-filter: blur(12px); }
.audio .bigplay { top: auto; bottom: 64px; transform: translateX(-50%); width: 46px; height: 46px; }
.bigplay:hover { background: rgba(77, 141, 255, .75); color: #fff; }
.bar { position: absolute; left: 10px; right: 10px; bottom: 10px; height: 38px; display: flex; align-items: center; gap: 4px; padding: 0 6px;
  border-radius: 10px; background: rgba(14, 17, 24, .62); border: 1px solid rgba(255, 255, 255, .1); backdrop-filter: blur(14px); color: #dfe6f5; opacity: 0; transition: opacity .2s; }
.viewer:hover .bar, .audio .bar { opacity: 1; }
.bar button { color: #dfe6f5; height: 28px; }
.bar button:hover { background: rgba(255, 255, 255, .1); color: #fff; }
.bar .icon { width: 28px; }
.pill { font-size: 11.5px; padding: 0 8px; }
.time { font-size: 12px; margin-left: 4px; }
.time i { color: rgba(223, 230, 245, .4); font-style: normal; margin: 0 2px; }
.grow { flex: 1; }
@media (max-height: 760px) {
  .audio-face { gap: 6px; padding-bottom: 44px; }
  .disc { width: 50px; height: 50px; border-radius: 15px; }
  .tc { font-size: 20px; }
  .an { font-size: 13px; }
}
</style>
