<script setup lang="ts">
// 检测项清单：检测中当进度步骤用，完成后显示每项的结果状态
import Icon from "./Icon.vue"
import type { DetectorInfo, DetectorStatus } from "../types"

defineProps<{ items: DetectorInfo[]; status: Record<string, DetectorStatus>; current: string; compact?: boolean }>()

function state(s: DetectorStatus | undefined, name: string, current: string) {
  if (!s) return name === current ? "run" : "wait"
  if (!s.ok) return "err"
  return s.skipped ? "skip" : "done"
}
</script>

<template>
  <div class="dets" :class="{ compact }">
    <div v-for="d in items" :key="d.name" class="det" :class="state(status[d.name], d.name, current)">
      <span class="dot">
        <Icon v-if="state(status[d.name], d.name, current) === 'done'" name="check" :size="12" :stroke="3" />
        <Icon v-else-if="state(status[d.name], d.name, current) === 'skip'" name="minus" :size="12" :stroke="3" />
        <Icon v-else-if="state(status[d.name], d.name, current) === 'err'" name="x" :size="12" :stroke="3" />
        <span v-else-if="state(status[d.name], d.name, current) === 'run'" class="spin" />
      </span>
      <div class="txt">
        <div class="t">{{ d.title }}<span v-if="d.uses_model" class="tag">模型</span></div>
        <div class="d">{{ d.desc }}</div>
      </div>
      <span class="st">
        <template v-if="status[d.name]?.skipped">{{ status[d.name].skipped }}</template>
        <template v-else-if="status[d.name] && !status[d.name].ok">出错</template>
        <template v-else-if="status[d.name]">{{ status[d.name].seconds < 0.1 ? "<0.1" : status[d.name].seconds.toFixed(1) }} 秒</template>
        <template v-else-if="d.name === current">检测中</template>
      </span>
    </div>
  </div>
</template>

<style scoped>
.dets { display: flex; flex-direction: column; }
.det { display: flex; align-items: center; gap: 12px; padding: 9px 0; border-top: 1px solid var(--line-2); }
.det:first-child { border-top: none; }
.dot { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; flex: none; border: 1.5px solid var(--line); color: #fff; }
.done .dot { background: var(--ok); border-color: var(--ok); }
.skip .dot { background: var(--unknown-bg); border-color: var(--unknown-bg); color: var(--muted); }
.err .dot { background: var(--danger); border-color: var(--danger); }
.run .dot { border-color: var(--brand-weak); }
.spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--brand-weak); border-top-color: var(--brand); animation: s .8s linear infinite; }
@keyframes s { to { transform: rotate(360deg); } }
.txt { flex: 1; min-width: 0; }
.t { font-size: 13px; color: var(--text); display: flex; align-items: center; gap: 6px; }
.wait .t, .skip .t { color: var(--muted); }
.tag { font-size: 10px; color: var(--brand); background: var(--brand-weak); border-radius: 4px; padding: 0 4px; }
.d { font-size: 12px; color: var(--faint); margin-top: 1px; }
.compact .d { display: none; }
.st { font-size: 12px; color: var(--muted); white-space: nowrap; }
.err .st { color: var(--danger); }
.run .st { color: var(--brand); }
</style>
