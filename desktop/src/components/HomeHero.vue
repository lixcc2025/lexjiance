<script setup lang="ts">
// 首页：扫描动画插画 + 拖放区 + 能力说明
import Icon from "./Icon.vue"

defineProps<{ dragging: boolean; mac: boolean }>()
const emit = defineEmits<{ (e: "pick"): void }>()

// 插画用的波形：固定种子，每次一样
const BARS = Array.from({ length: 72 }, (_, i) => {
  const x = i / 71
  const env = Math.sin(Math.PI * x) ** 0.6
  const v = 0.25 + 0.75 * Math.abs(Math.sin(i * 1.7) * Math.cos(i * 0.43) + 0.35 * Math.sin(i * 0.19))
  return Math.max(0.08, Math.min(1, env * v))
})
const CAPS = [
  { icon: "sparkles", tone: "violet", t: "AI 生成标识", d: "国标隐式标识、内容凭证、元数据里的生成工具" },
  { icon: "scissors", tone: "amber", t: "剪辑痕迹", d: "时间戳断档、异常关键帧、音画不同步，精确到秒" },
  { icon: "cpu", tone: "blue", t: "AI 合成识别", d: "声音克隆、合成语音、AI 生成画面", soon: true },
]
</script>

<template>
  <div class="home">
    <div class="drag topbar" />
    <div class="hero">
      <div class="art" aria-hidden="true">
        <svg viewBox="0 0 720 150" preserveAspectRatio="none">
          <defs>
            <linearGradient id="bar" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7eabff" /><stop offset="1" stop-color="#3a63d6" /></linearGradient>
            <linearGradient id="beam" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7eabff" stop-opacity="0" /><stop offset="1" stop-color="#7eabff" stop-opacity=".55" /></linearGradient>
          </defs>
          <g>
            <rect v-for="(v, i) in BARS" :key="i" :x="i * 10 + 2" :y="75 - v * 62" width="5" :height="v * 124" rx="2.5"
              :fill="i >= 41 && i <= 47 ? '#ff5b61' : 'url(#bar)'" :opacity="i >= 41 && i <= 47 ? 0.95 : 0.85" />
          </g>
          <rect x="406" y="4" width="76" height="142" rx="6" fill="#ff5b61" opacity=".1" stroke="#ff5b61" stroke-opacity=".5" stroke-dasharray="4 4" />
          <g class="beam"><rect x="-90" y="0" width="90" height="150" fill="url(#beam)" /><rect x="-2" y="0" width="2" height="150" fill="#cfe0ff" /></g>
        </svg>
        <div class="tag"><span class="led" />疑点 00:41.6 – 00:47.2</div>
      </div>

      <h1>鉴别音视频的真实性</h1>
      <p class="lead">拖入录音或视频，检测是否 AI 生成、有没有剪辑痕迹，疑点精确到秒</p>

      <div class="drop" :class="{ on: dragging }" @click="emit('pick')">
        <Icon name="upload" :size="20" />
        <span>把文件拖到这里，或</span>
        <button class="primary" @click.stop="emit('pick')">选择文件</button>
        <span class="kbd">{{ mac ? "⌘O" : "Ctrl+O" }}</span>
      </div>
      <div class="formats">MP4 · MOV · AVI · MKV · MP3 · WAV · M4A · AMR 等常见格式</div>

      <div class="caps">
        <div v-for="c in CAPS" :key="c.t" class="cap">
          <div class="ci" :class="c.tone"><Icon :name="c.icon" :size="17" /></div>
          <div class="ct">{{ c.t }}<span v-if="c.soon" class="soon">即将支持</span></div>
          <div class="cd">{{ c.d }}</div>
        </div>
      </div>

      <div class="privacy"><Icon name="lock" :size="13" />本机离线检测，文件不会上传</div>
    </div>
  </div>
</template>

<style scoped>
.home { flex: 1; position: relative; overflow: auto; background:
  radial-gradient(1200px 500px at 50% -10%, rgba(77, 141, 255, .16), transparent 60%),
  radial-gradient(600px 300px at 85% 110%, rgba(255, 91, 97, .07), transparent 60%), var(--bg); }
.topbar { position: absolute; top: 0; left: 0; right: 0; height: 40px; }
.hero { max-width: 860px; margin: 0 auto; padding: 72px 40px 40px; display: flex; flex-direction: column; align-items: center; text-align: center; animation: rise .5s ease both; }
.art { position: relative; width: 100%; max-width: 640px; height: 132px; margin-bottom: 34px; }
.art svg { width: 100%; height: 100%; overflow: hidden; -webkit-mask-image: linear-gradient(90deg, transparent 0%, #000 7%, #000 93%, transparent 100%); }
.beam { animation: sweep 4.2s cubic-bezier(.45, .05, .55, .95) infinite; }
@keyframes sweep { from { transform: translateX(0); } to { transform: translateX(810px); } }
.tag { position: absolute; left: 57%; top: -14px; display: inline-flex; align-items: center; gap: 6px; font-size: 11px; font-family: var(--mono);
  color: var(--danger); background: var(--surface); border: 1px solid color-mix(in srgb, var(--danger) 45%, transparent); box-shadow: 0 4px 14px rgba(255, 91, 97, .18); padding: 3px 9px; border-radius: 20px; backdrop-filter: blur(6px); }
.tag .led { width: 6px; height: 6px; border-radius: 50%; background: #ff5b61; box-shadow: 0 0 8px #ff5b61; animation: pulse 1.6s infinite; }
h1 { font-size: 30px; font-weight: 700; letter-spacing: 1px; margin: 0 0 10px; }
.lead { color: var(--text-2); font-size: 14px; margin: 0 0 30px; }
.drop { display: flex; align-items: center; gap: 12px; padding: 14px 16px 14px 22px; border-radius: 14px; cursor: pointer; color: var(--text-2);
  background: var(--surface); border: 1px dashed var(--border-2); box-shadow: var(--shadow); transition: all .2s; min-width: 460px; }
.drop:hover, .drop.on { border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-bg), var(--shadow); color: var(--text); }
.drop button { margin-left: auto; height: 34px; padding: 0 18px; }
.kbd { font-size: 11px; color: var(--muted); font-family: var(--mono); }
.formats { margin-top: 12px; font-size: 11.5px; color: var(--muted); letter-spacing: .3px; }
.caps { margin-top: 44px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; width: 100%; }
.cap { text-align: left; padding: 16px; border-radius: 12px; background: var(--surface); border: 1px solid var(--border); }
.ci { width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center; margin-bottom: 12px; }
.ci.violet { color: #b28cff; background: rgba(160, 120, 255, .14); }
.ci.amber { color: var(--warn); background: var(--warn-bg); }
.ci.blue { color: var(--accent-2); background: var(--accent-bg); }
.ct { font-weight: 600; font-size: 13.5px; display: flex; align-items: center; gap: 6px; }
.cd { color: var(--muted); font-size: 12px; margin-top: 6px; line-height: 1.55; }
.soon { font-size: 10px; font-weight: 500; color: var(--muted); border: 1px solid var(--border-2); border-radius: 4px; padding: 0 5px; }
.privacy { margin-top: 26px; display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ok); }
</style>
