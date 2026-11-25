<script setup lang="ts">
// 首页：拖放区 + 最近检测
import { ref } from "vue"
import Icon from "./Icon.vue"
import { LEVEL_TEXT, type HistoryItem, type Level } from "../types"

defineProps<{ history: HistoryItem[]; dragging: boolean }>()
const emit = defineEmits<{ (e: "pick"): void; (e: "open", path: string): void; (e: "clear"): void }>()
const hover = ref(-1)

const CAPS = [
  { icon: "sparkles", tone: "a", t: "AI 生成标识", d: "读取国标隐式标识、内容凭证和元数据里的 AI 工具名" },
  { icon: "scissors", tone: "b", t: "剪辑痕迹", d: "时间戳断档、异常关键帧、音画不同步，标出具体位置" },
  { icon: "cpu", tone: "c", t: "AI 合成识别", d: "识别声音克隆、合成语音和 AI 生成画面", soon: true },
]
const FORMATS = ["MP4", "MOV", "AVI", "MKV", "MP3", "WAV", "M4A", "AMR"]
const tone = (l: Level) => ({ none: "ok", suspicious: "warn", likely: "danger", unknown: "unknown" })[l]

function when(t: number) {
  const d = new Date(t)
  const today = new Date()
  const hm = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`
  if (d.toDateString() === today.toDateString()) return "今天 " + hm
  return `${d.getMonth() + 1}月${d.getDate()}日 ${hm}`
}
</script>

<template>
  <div class="home">
    <div class="drop card" :class="{ on: dragging }" @click="emit('pick')">
      <div class="badge"><Icon name="upload" :size="30" :stroke="1.6" /></div>
      <h1>把视频或音频拖到这里</h1>
      <p class="lead">检测是否 AI 生成、有没有剪辑痕迹，并标出可疑的位置</p>
      <button class="primary big" @click.stop="emit('pick')"><Icon name="file" :size="16" />选择文件</button>
      <div class="formats">
        <span v-for="f in FORMATS" :key="f">{{ f }}</span>
        <span class="more">等常见格式</span>
      </div>
      <div class="privacy"><Icon name="lock" :size="14" />本机检测，文件不会离开这台电脑</div>
    </div>

    <div class="caps">
      <div v-for="c in CAPS" :key="c.t" class="cap card">
        <div class="cap-ico" :class="c.tone"><Icon :name="c.icon" :size="18" /></div>
        <div>
          <div class="cap-t">{{ c.t }}<span v-if="c.soon" class="soon">即将支持</span></div>
          <div class="cap-d">{{ c.d }}</div>
        </div>
      </div>
    </div>

    <div class="recent">
      <div class="recent-head">
        <span>最近检测</span>
        <button v-if="history.length" class="ghost small" @click="emit('clear')">清空</button>
      </div>
      <div v-if="!history.length" class="recent-empty">还没有检测记录</div>
      <div v-else class="recent-list card">
        <div v-for="(h, i) in history" :key="h.path + h.time" class="recent-item" @mouseenter="hover = i" @mouseleave="hover = -1" @click="emit('open', h.path)">
          <div class="ico"><Icon :name="/\.(mp3|wav|m4a|aac|amr|flac|ogg|opus|wma)$/i.test(h.name) ? 'audio' : 'video'" :size="18" /></div>
          <div class="nm">
            <div class="t" :title="h.path">{{ h.name }}</div>
            <div class="s">{{ when(h.time) }} · {{ h.count ? h.count + " 个疑点" : "无疑点" }}</div>
          </div>
          <span class="pill" :class="tone(h.ai)">AI {{ LEVEL_TEXT[h.ai] }}</span>
          <span class="pill" :class="tone(h.edit)">剪辑 {{ LEVEL_TEXT[h.edit] }}</span>
          <span class="go" :class="{ show: hover === i }">重新检测 <Icon name="refresh" :size="14" /></span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.home { flex: 1; overflow: auto; padding: 28px 32px 32px; display: flex; flex-direction: column; align-items: center; gap: 28px; }
.drop {
  width: 100%; max-width: 880px; padding: 44px 24px 30px; text-align: center; cursor: pointer;
  border: 1.5px dashed #c8d1e3; box-shadow: none; transition: border-color .2s, background .2s;
  background: linear-gradient(180deg, #fbfcff 0%, #ffffff 100%);
}
.drop:hover, .drop.on { border-color: var(--brand-2); background: #f5f8ff; }
.badge { width: 64px; height: 64px; margin: 0 auto 16px; border-radius: 18px; display: grid; place-items: center; color: var(--brand); background: var(--brand-weak); }
h1 { font-size: 22px; margin: 0 0 8px; font-weight: 600; letter-spacing: .5px; }
.lead { color: var(--muted); margin: 0 0 22px; }
button.big { height: 40px; padding: 0 22px; font-size: 15px; }
.formats { display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; margin-top: 22px; }
.formats span { font-size: 12px; color: var(--muted); background: var(--line-2); padding: 2px 8px; border-radius: 4px; }
.formats .more { background: none; }
.privacy { display: inline-flex; gap: 6px; align-items: center; margin-top: 18px; font-size: 12px; color: var(--ok); }

.caps { width: 100%; max-width: 880px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: -8px; }
.cap { display: flex; gap: 12px; padding: 14px 16px; }
.cap-ico { width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center; flex: none; }
.cap-ico.a { color: #7a4ad9; background: #f1ebff; }
.cap-ico.b { color: var(--warn); background: var(--warn-bg); }
.cap-ico.c { color: var(--brand); background: var(--brand-weak); }
.cap-t { font-weight: 600; font-size: 14px; display: flex; align-items: center; gap: 6px; }
.cap-d { font-size: 12px; color: var(--muted); margin-top: 4px; line-height: 1.5; }
.soon { font-size: 10px; font-weight: 400; color: var(--muted); background: var(--line-2); border-radius: 4px; padding: 0 5px; }
.recent { width: 100%; max-width: 880px; }
.recent-head { display: flex; align-items: center; justify-content: space-between; color: var(--text-2); font-weight: 600; margin-bottom: 10px; }
button.small { height: 26px; padding: 0 10px; font-size: 12px; font-weight: 400; }
.recent-empty { color: var(--faint); font-size: 13px; padding: 12px 2px; }
.recent-list { overflow: hidden; }
.recent-item { display: flex; align-items: center; gap: 12px; padding: 12px 16px; cursor: pointer; border-top: 1px solid var(--line-2); }
.recent-item:first-child { border-top: none; }
.recent-item:hover { background: #f8faff; }
.ico { width: 34px; height: 34px; border-radius: 8px; background: var(--line-2); color: var(--text-2); display: grid; place-items: center; flex: none; }
.nm { flex: 1; min-width: 0; }
.nm .t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.nm .s { font-size: 12px; color: var(--muted); margin-top: 2px; }
.pill { font-size: 12px; padding: 2px 8px; border-radius: 10px; white-space: nowrap; }
.pill.ok { color: var(--ok); background: var(--ok-bg); }
.pill.warn { color: var(--warn); background: var(--warn-bg); }
.pill.danger { color: var(--danger); background: var(--danger-bg); }
.pill.unknown { color: var(--unknown); background: var(--unknown-bg); }
.go { font-size: 12px; color: var(--brand); display: inline-flex; gap: 4px; align-items: center; opacity: 0; width: 76px; transition: opacity .15s; }
.go.show { opacity: 1; }
</style>
