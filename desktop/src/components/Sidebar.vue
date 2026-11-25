<script setup lang="ts">
// 侧栏：品牌、新建检测、检测记录、引擎状态。macOS 下透明，露出系统半透明材质
import Icon from "./Icon.vue"
import { LEVEL_TONE, type HistoryItem } from "../types"

defineProps<{ history: HistoryItem[]; active: string | null; engineReady: boolean; mac: boolean; theme: string }>()
const emit = defineEmits<{ (e: "new"): void; (e: "open", p: string): void; (e: "home"): void; (e: "clear"): void; (e: "theme", t: string): void }>()
const THEMES = [
  { k: "system", t: "自动", d: "M12 3v18 M12 21a9 9 0 0 0 0-18 M12 21a9 9 0 0 1 0-18" },
  { k: "light", t: "浅色", d: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10z M12 1v2 M12 21v2 M4.2 4.2l1.4 1.4 M18.4 18.4l1.4 1.4 M1 12h2 M21 12h2 M4.2 19.8l1.4-1.4 M18.4 5.6l1.4-1.4" },
  { k: "dark", t: "深色", d: "M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" },
]

const isAudio = (n: string) => /\.(mp3|wav|m4a|aac|amr|flac|ogg|opus|wma)$/i.test(n)
function when(t: number) {
  const d = new Date(t)
  const now = new Date()
  const hm = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
  if (d.toDateString() === now.toDateString()) return hm
  const y = new Date(now.getTime() - 864e5)
  if (d.toDateString() === y.toDateString()) return "昨天"
  return `${d.getMonth() + 1}/${d.getDate()}`
}
</script>

<template>
  <aside class="side" :class="{ mac }">
    <div v-if="mac" class="top drag">
      <div class="brand nodrag" @click="emit('home')">
        <div class="logo">
          <svg viewBox="0 0 32 32" width="20" height="20"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#9cc0ff" /><stop offset="1" stop-color="#ffffff" /></linearGradient></defs>
            <path d="M3 16h4l3-8 4 16 4-12 3 7 2-3h6" fill="none" stroke="url(#lg)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" /></svg>
        </div>
        <div>
          <div class="name">音视频检测</div>
          <div class="sub">MEDIA FORENSICS</div>
        </div>
      </div>
    </div>

    <button class="primary new" @click="emit('new')"><Icon name="plus" :size="15" :stroke="2.2" />新建检测<span class="kbd">{{ mac ? "⌘O" : "Ctrl+O" }}</span></button>

    <div class="sec">
      <span class="label">检测记录</span>
      <button v-if="history.length" class="flat tiny" @click="emit('clear')">清空</button>
    </div>
    <div class="list">
      <div v-if="!history.length" class="empty">检测过的文件会出现在这里</div>
      <div v-for="h in history" :key="h.path + h.time" class="item" :class="{ on: h.path === active }" :title="h.path" @click="emit('open', h.path)">
        <div class="ic"><Icon :name="isAudio(h.name) ? 'audio' : 'video'" :size="14" /></div>
        <div class="nm">
          <div class="t">{{ h.name }}</div>
          <div class="s">
            <span class="dot" :class="LEVEL_TONE[h.ai]" title="AI 生成" />
            <span class="dot" :class="LEVEL_TONE[h.edit]" title="剪辑痕迹" />
            <span>{{ h.count ? h.count + " 个疑点" : "无疑点" }}</span>
          </div>
        </div>
        <span class="time num">{{ when(h.time) }}</span>
      </div>
    </div>

    <div class="status">
      <div class="st"><span class="led" :class="engineReady ? 'ok' : 'off'" />本机检测引擎<b>{{ engineReady ? "就绪" : "未就绪" }}</b></div>
      <div class="st"><span class="led off" />云端 AI 识别<b>未连接</b></div>
      <div class="themes">
        <button v-for="m in THEMES" :key="m.k" class="flat" :class="{ on: theme === m.k }" :title="m.t" @click="emit('theme', m.k)">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path v-for="(d, i) in m.d.split(' M')" :key="i" :d="i ? 'M' + d : d" /></svg>
          {{ m.t }}
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.side { width: 248px; flex: none; display: flex; flex-direction: column; background: var(--sidebar); border-right: 1px solid var(--border); }
.side.mac { background: transparent; }
.top { height: 92px; padding: 44px 18px 0; }
.mac .top { padding-top: 46px; }
.side:not(.mac) .new { margin-top: 14px; }
@media (max-width: 1180px) { .side { width: 220px; } .time { display: none; } }
@media (max-width: 1040px) { .side { width: 196px; } .kbd { display: none; } }
@media (max-height: 760px) { .mac .top { height: 78px; padding-top: 40px; } .new { margin-bottom: 12px; } .item { padding: 6px 10px; } }
.brand { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.logo { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; background: linear-gradient(145deg, #3a6fe0 0%, #1d3a8a 100%); box-shadow: 0 0 0 1px rgba(255, 255, 255, .12) inset, 0 6px 16px rgba(45, 95, 220, .35); }
.name { font-size: 14px; font-weight: 650; letter-spacing: .4px; }
.sub { font-size: 9.5px; letter-spacing: 1.6px; color: var(--muted); margin-top: 2px; }
.new { margin: 14px 14px 18px; height: 36px; font-weight: 600; }
.kbd { margin-left: auto; font-size: 11px; opacity: .7; font-weight: 400; }
.new { justify-content: flex-start; padding: 0 12px; }
.sec { display: flex; align-items: center; justify-content: space-between; padding: 0 18px 6px; }
.tiny { height: 22px; padding: 0 6px; font-size: 11px; color: var(--muted); }
.list { flex: 1; overflow: auto; padding: 0 8px; }
.empty { color: var(--faint); font-size: 12px; padding: 10px; line-height: 1.6; }
.item { display: flex; align-items: center; gap: 9px; padding: 8px 10px; border-radius: 8px; cursor: pointer; margin-bottom: 1px; }
.item:hover { background: rgba(127, 140, 170, .1); }
.item.on { background: var(--accent-bg); }
.item.on .t { color: var(--text); }
.ic { width: 28px; height: 28px; border-radius: 7px; display: grid; place-items: center; background: var(--surface-3); color: var(--text-2); flex: none; }
.item.on .ic { background: var(--accent); color: #fff; }
.nm { flex: 1; min-width: 0; }
.t { font-size: 12.5px; color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.s { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--muted); margin-top: 3px; }
.s span:last-child { margin-left: 3px; }
.dot { width: 7px; height: 7px; border-radius: 50%; background: var(--unknown); }
.dot.ok { background: var(--ok); } .dot.warn { background: var(--warn); } .dot.danger { background: var(--danger); }
.time { font-size: 10.5px; color: var(--faint); align-self: flex-start; margin-top: 2px; }
.status { padding: 12px 18px 16px; border-top: 1px solid var(--border); display: flex; flex-direction: column; gap: 7px; }
.st { display: flex; align-items: center; gap: 8px; font-size: 11.5px; color: var(--muted); }
.st b { margin-left: auto; font-weight: 500; color: var(--text-2); }
.led { width: 7px; height: 7px; border-radius: 50%; background: var(--faint); }
.led.ok { background: var(--ok); box-shadow: 0 0 8px var(--ok); }
.themes { display: flex; gap: 2px; margin-top: 6px; padding: 2px; border-radius: 8px; background: rgba(127, 140, 170, .12); }
.themes button { flex: 1; height: 24px; padding: 0 4px; font-size: 11px; gap: 4px; color: var(--muted); border-radius: 6px; }
.themes button.on { background: var(--surface); color: var(--text); box-shadow: 0 1px 2px rgba(0, 0, 0, .15); }
</style>
