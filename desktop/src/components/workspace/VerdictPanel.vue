<script setup lang="ts">
// 结论区：检测中显示进度环和检测项流水线；完成后显示两项结论和检测项状态
import { computed } from "vue"
import Icon from "../common/Icon.vue"
import { LEVEL_TEXT, LEVEL_TONE, type AnalyzeResult, type DetectorInfo, type DetectorStatus, type Finding, type Verdict } from "../../types"

const props = defineProps<{
  result: AnalyzeResult | null
  error: string
  pct: number
  stage: string
  detectors: DetectorInfo[]
  status: Record<string, DetectorStatus>
  current: string
  live: Finding[]
}>()
const emit = defineEmits<{ (e: "cancel"): void; (e: "retry"): void }>()

const R = 34
const C = 2 * Math.PI * R
const ICON: Record<Verdict["level"], string> = { none: "shield", suspicious: "alert", likely: "octagon", unknown: "help" }
const issues = computed(() => (props.result?.findings || props.live).filter((f) => f.severity !== "info"))
const count = (cat: string) => issues.value.filter((f) => f.category === cat).length
const totalSec = computed(() => (props.result?.detectors || []).reduce((s, d) => s + d.seconds, 0))
const items = computed(() =>
  props.result
    ? props.result.detectors.map((s) => ({ name: s.name, title: s.title, cloud: props.detectors.find((d) => d.name === s.name)?.cloud }))
    : props.detectors,
)
function state(name: string) {
  const s = props.status[name] || props.result?.detectors.find((d) => d.name === name)
  if (!s) return name === props.current || (props.current === "cloud" && isCloud(name)) ? "run" : "wait"
  if (!s.ok) return "err"
  return s.skipped ? "skip" : "done"
}
const isCloud = (name: string) => !!props.detectors.find((d) => d.name === name)?.cloud
function reason(name: string) {
  const s = props.status[name] || props.result?.detectors.find((d) => d.name === name)
  return s ? (s.error || s.skipped || "完成") : ""
}
function note(name: string) {
  const s = props.status[name] || props.result?.detectors.find((d) => d.name === name)
  if (!s) return name === props.current || (props.current === "cloud" && isCloud(name)) ? "检测中" : ""
  if (!s.ok) return "出错"
  if (s.skipped) return ""
  return s.seconds < 0.1 ? "<0.1s" : s.seconds.toFixed(1) + "s"
}
</script>

<template>
  <div class="vp panel">
    <div v-if="error" class="err">
      <div class="err-ic"><Icon name="alert" :size="20" /></div>
      <div class="err-t">检测没有完成</div>
      <div class="err-d selectable">{{ error }}</div>
      <button @click="emit('retry')"><Icon name="refresh" :size="14" />重新检测</button>
    </div>

    <template v-else-if="!result">
      <div class="run">
        <div class="ring">
          <svg width="84" height="84" viewBox="0 0 84 84">
            <circle cx="42" cy="42" :r="R" class="trk" />
            <circle cx="42" cy="42" :r="R" class="val" :stroke-dasharray="C" :stroke-dashoffset="C * (1 - pct)" />
          </svg>
          <div class="ring-t num">{{ Math.round(pct * 100) }}<small>%</small></div>
        </div>
        <div class="run-txt">
          <div class="label">正在检测</div>
          <div class="run-stage">{{ stage || "准备中…" }}</div>
          <div class="run-found">已发现 <b>{{ issues.length }}</b> 个疑点</div>
        </div>
        <button class="flat cancel" @click="emit('cancel')">取消</button>
      </div>
    </template>

    <template v-else>
      <div class="verdicts">
        <div class="v" :class="LEVEL_TONE[result.ai.level]">
          <div class="v-top"><span class="label"><Icon name="sparkles" :size="12" />AI 生成</span><span v-if="count('ai')" class="cnt">{{ count("ai") }}</span></div>
          <div class="v-main"><span class="v-ic"><Icon :name="ICON[result.ai.level]" :size="20" :stroke="2.1" /></span><span class="v-lv">{{ LEVEL_TEXT[result.ai.level] }}</span></div>
          <div class="v-txt">{{ result.ai.text }}</div>
        </div>
        <div class="v" :class="LEVEL_TONE[result.edit.level]">
          <div class="v-top"><span class="label"><Icon name="scissors" :size="12" />剪辑痕迹</span><span v-if="count('edit')" class="cnt">{{ count("edit") }}</span></div>
          <div class="v-main"><span class="v-ic"><Icon :name="ICON[result.edit.level]" :size="20" :stroke="2.1" /></span><span class="v-lv">{{ LEVEL_TEXT[result.edit.level] }}</span></div>
          <div class="v-txt">{{ result.edit.text }}</div>
        </div>
      </div>
    </template>

    <div v-if="!error" class="pipe">
      <div class="pipe-h"><span class="label">检测项</span><span v-if="result" class="pipe-sum num">{{ result.detectors.filter((d) => d.ok && !d.skipped).length }}/{{ result.detectors.length }} 项已运行 · 用时 {{ totalSec < 0.1 ? "<0.1" : totalSec.toFixed(1) }}s</span></div>
      <div class="steps">
        <div v-for="d in items" :key="d.name" class="step" :class="state(d.name)" :title="reason(d.name)">
          <span class="dot">
            <Icon v-if="state(d.name) === 'done'" name="check" :size="10" :stroke="3.2" />
            <Icon v-else-if="state(d.name) === 'skip'" name="minus" :size="10" :stroke="3.2" />
            <Icon v-else-if="state(d.name) === 'err'" name="x" :size="10" :stroke="3.2" />
            <i v-else-if="state(d.name) === 'run'" class="spin" />
          </span>
          <span class="st">{{ d.title }}<em v-if="d.cloud">云端</em></span>
          <span class="nt">{{ note(d.name) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.vp { padding: 14px; display: flex; flex-direction: column; gap: 14px; }
.run { display: flex; align-items: center; gap: 16px; padding: 4px 2px; }
.ring { position: relative; width: 84px; height: 84px; flex: none; }
.ring svg { transform: rotate(-90deg); }
.trk { fill: none; stroke: var(--surface-3); stroke-width: 7; }
.val { fill: none; stroke: var(--accent); stroke-width: 7; stroke-linecap: round; transition: stroke-dashoffset .35s; filter: drop-shadow(0 0 6px var(--accent-glow)); }
.ring-t { position: absolute; inset: 0; display: grid; place-items: center; font-size: 20px; font-weight: 600; }
.ring-t small { font-size: 11px; color: var(--muted); }
.run-txt { flex: 1; min-width: 0; }
.run-stage { font-size: 13.5px; margin: 6px 0 8px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.run-found { font-size: 12px; color: var(--muted); }
.run-found b { color: var(--warn); font-weight: 600; }
.cancel { align-self: flex-start; }

.verdicts { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.v { --c: var(--unknown); --cb: var(--unknown-bg); position: relative; border-radius: 10px; padding: 12px 12px 13px; overflow: hidden;
  background: linear-gradient(160deg, var(--cb) 0%, transparent 70%), var(--surface-2); border: 1px solid color-mix(in srgb, var(--c) 30%, transparent); animation: rise .4s ease both; }
.v.ok { --c: var(--ok); --cb: var(--ok-bg); } .v.warn { --c: var(--warn); --cb: var(--warn-bg); } .v.danger { --c: var(--danger); --cb: var(--danger-bg); }
.v + .v { animation-delay: .08s; }
.v-top { display: flex; align-items: center; justify-content: space-between; }
.v-top .label { display: inline-flex; gap: 5px; align-items: center; }
.cnt { min-width: 20px; height: 20px; border-radius: 10px; display: grid; place-items: center; font-size: 11px; font-weight: 700; color: #fff; background: var(--c); padding: 0 6px; }
.v-main { display: flex; align-items: center; gap: 9px; margin: 10px 0 8px; }
.v-ic { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; color: var(--c); background: var(--cb); box-shadow: 0 0 18px color-mix(in srgb, var(--c) 30%, transparent); }
.v-lv { font-size: 21px; font-weight: 700; color: var(--c); letter-spacing: 1px; white-space: nowrap; }
.v-txt { font-size: 12px; color: var(--text-2); line-height: 1.55; }

.err { display: flex; flex-direction: column; align-items: flex-start; gap: 8px; padding: 6px 2px; }
.err-ic { width: 38px; height: 38px; border-radius: 10px; display: grid; place-items: center; color: var(--danger); background: var(--danger-bg); }
.err-t { font-size: 15px; font-weight: 600; }
.err-d { color: var(--text-2); font-size: 12.5px; line-height: 1.6; }

.pipe { border-top: 1px solid var(--border); padding-top: 12px; }
@media (max-height: 760px) {
  .vp { padding: 10px 12px; gap: 10px; }
  .v { padding: 10px; }
  .v-main { margin: 6px 0 4px; }
  .v-lv { font-size: 18px; }
  .v-ic { width: 28px; height: 28px; }
  .v-txt { font-size: 11.5px; line-height: 1.45; }
  .pipe { padding-top: 8px; }
  .step { height: 20px; }
  .ring { width: 64px; height: 64px; } .ring svg { width: 64px; height: 64px; }
}
@media (max-width: 1120px) { .nt { display: none; } .v-txt { display: none; } .v-lv { font-size: 16px; letter-spacing: 0; } .v-ic { width: 26px; height: 26px; } .v-main { gap: 7px; } }
.pipe-h { display: flex; justify-content: space-between; margin-bottom: 8px; }
.pipe-sum { font-size: 11px; color: var(--muted); }
.steps { display: grid; grid-template-columns: 1fr 1fr; gap: 4px 12px; }
.step { display: flex; align-items: center; gap: 7px; min-width: 0; height: 24px; }
.dot { width: 16px; height: 16px; border-radius: 50%; display: grid; place-items: center; flex: none; border: 1.5px solid var(--border-2); color: #fff; }
.done .dot { background: var(--ok); border-color: var(--ok); }
.skip .dot { background: var(--surface-3); border-color: var(--surface-3); color: var(--muted); }
.err .dot { background: var(--danger); border-color: var(--danger); }
.run .dot { border-color: transparent; }
.spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid var(--accent-bg); border-top-color: var(--accent); animation: spin .8s linear infinite; }
.st { font-size: 12px; color: var(--text-2); white-space: nowrap; display: flex; align-items: center; gap: 4px; }
.wait .st, .skip .st { color: var(--muted); }
.st em { font-style: normal; font-size: 9.5px; color: var(--accent-2); background: var(--accent-bg); border-radius: 3px; padding: 0 3px; }
.nt { margin-left: auto; font-size: 10.5px; color: var(--faint); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 70px; }
.run .nt { color: var(--accent-2); }
</style>
