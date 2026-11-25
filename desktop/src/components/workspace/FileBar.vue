<script setup lang="ts">
// 工作台顶部：文件名、路径、格式信息，重新检测、打开所在位置
import { computed } from "vue"
import Icon from "../common/Icon.vue"
import { baseName, fmtSize, fmtTime, type AnalyzeResult } from "../../types"

const props = defineProps<{ file: string; result: AnalyzeResult | null; isVideo: boolean; canRetry: boolean; mac: boolean }>()
const emit = defineEmits<{ (e: "retry"): void; (e: "reveal"): void }>()

const chips = computed(() => {
  const m = props.result?.media
  if (!m) return []
  const c: string[] = [m.format.toUpperCase(), fmtTime(m.duration, false)]
  if (m.video) c.push(`${m.video.width}×${m.video.height}`, String(m.video.codec || "").toUpperCase())
  if (m.audio) c.push(`${String(m.audio.codec || "").toUpperCase()} ${m.audio.sample_rate ? Math.round(m.audio.sample_rate / 100) / 10 + "kHz" : ""}`.trim())
  c.push(fmtSize(m.size))
  return c.filter(Boolean)
})
</script>

<template>
  <header class="bar" :class="{ drag: mac }">
    <div class="fi"><Icon :name="isVideo ? 'video' : 'audio'" :size="16" /></div>
    <div class="fn">
      <div class="name">{{ baseName(file) }}</div>
      <div class="path selectable nodrag" :title="file">{{ file }}</div>
    </div>
    <div class="chips num"><span v-for="c in chips" :key="c">{{ c }}</span></div>
    <div class="acts nodrag">
      <button v-if="canRetry" class="flat" title="重新检测" @click="emit('retry')"><Icon name="refresh" :size="14" />重新检测</button>
      <button class="flat" :title="mac ? '在访达中显示' : '打开文件所在的文件夹'" @click="emit('reveal')"><Icon name="folder" :size="14" />{{ mac ? "在访达中显示" : "打开所在位置" }}</button>
    </div>
  </header>
</template>

<style scoped>
.bar { height: 60px; flex: none; display: flex; align-items: center; gap: 12px; padding: 0 16px 0 18px; border-bottom: 1px solid var(--border); background: var(--surface); }
.fi { width: 32px; height: 32px; border-radius: 9px; display: grid; place-items: center; color: var(--accent-2); background: var(--accent-bg); flex: none; }
.fn { min-width: 0; flex: 0 1 auto; max-width: 34%; }
.name { font-size: 14px; font-weight: 650; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.path { font-size: 11px; color: var(--faint); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-top: 2px; }
.chips { display: flex; gap: 5px; flex-wrap: nowrap; overflow: hidden; flex: 1; }
.chips span { font-size: 11px; color: var(--text-2); background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px; padding: 2px 7px; white-space: nowrap; }
.acts { display: flex; gap: 4px; flex: none; }
.acts button { height: 28px; font-size: 12px; }
@media (max-width: 1320px) { .chips span:nth-child(n + 5) { display: none; } }
@media (max-width: 1120px) { .chips { display: none; } .fn { max-width: none; flex: 1; } .acts button { padding: 0 8px; } }
@media (max-height: 760px) { .bar { height: 50px; } }
</style>
