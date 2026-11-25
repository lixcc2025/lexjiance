<script setup lang="ts">
// 疑点检查器：疑点 / 来源信息两个页签；选中的展开说明和依据，时间轴上同步高亮
import { computed, nextTick, ref, watch } from "vue"
import Icon from "./Icon.vue"
import { CAT_TEXT, SEV_TEXT, fmtTime, type Finding } from "../types"

const props = defineProps<{ findings: Finding[]; active: number; running: boolean }>()
const emit = defineEmits<{ (e: "select", i: number): void; (e: "seek", i: number): void }>()

const tab = ref<"issues" | "source">("issues")
const list = ref<HTMLDivElement | null>(null)
const rows = computed(() => props.findings.map((f, i) => ({ f, i })))
const issues = computed(() => rows.value.filter((x) => x.f.severity !== "info"))
const source = computed(() => rows.value.filter((x) => x.f.severity === "info"))
const shown = computed(() => (tab.value === "issues" ? issues.value : source.value))

function val(v: unknown): string {
  if (v === null || v === undefined) return "—"
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : String(Math.round(v * 1000) / 1000)
  if (typeof v === "object") return JSON.stringify(v)
  return String(v)
}
function pick(i: number) {
  emit("select", props.active === i ? -1 : i)
}
// 时间轴上点了某个疑点：切到对应页签并滚动到它
watch(() => props.active, async (i) => {
  const f = props.findings[i]
  if (!f) return
  tab.value = f.severity === "info" ? "source" : "issues"
  await nextTick()
  list.value?.querySelector(`[data-i="${i}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" })
})
</script>

<template>
  <div class="fp panel">
    <div class="tabs">
      <button class="tab flat" :class="{ on: tab === 'issues' }" @click="tab = 'issues'">疑点<span class="n">{{ issues.length }}</span></button>
      <button class="tab flat" :class="{ on: tab === 'source' }" @click="tab = 'source'">来源信息<span class="n">{{ source.length }}</span></button>
    </div>
    <div ref="list" class="list">
      <div v-for="{ f, i } in shown" :key="i" :data-i="i" class="it" :class="[f.severity, { on: active === i }]" @click="pick(i)">
        <div class="row">
          <span class="sev">{{ SEV_TEXT[f.severity] }}</span>
          <div class="body">
            <div class="ti">{{ f.title }}</div>
            <div class="meta">
              <span>{{ CAT_TEXT[f.category] }}</span>
              <span v-if="f.modality !== 'file'">· {{ f.modality === "video" ? "画面" : "声音" }}</span>
              <span v-if="f.start !== null" class="num tm">· {{ fmtTime(f.start) }}<template v-if="f.end !== null && f.end !== f.start"> – {{ fmtTime(f.end) }}</template></span>
            </div>
          </div>
          <button v-if="f.start !== null" class="go flat icon" title="跳到这里播放" @click.stop="emit('seek', i)"><Icon name="play" :size="11" :stroke="2.4" /></button>
        </div>
        <div v-if="active === i" class="more selectable" @click.stop>
          <p v-if="f.detail">{{ f.detail }}</p>
          <div v-if="Object.keys(f.evidence).length" class="ev">
            <template v-for="(v, k) in f.evidence" :key="k">
              <div v-if="v && typeof v === 'object' && !Array.isArray(v)" class="kv grp"><span class="k">{{ k }}</span></div>
              <div v-for="(v2, k2) in (v && typeof v === 'object' && !Array.isArray(v) ? v : {})" :key="k + '.' + k2" class="kv sub"><span class="k">{{ k2 }}</span><span class="v num">{{ val(v2) }}</span></div>
              <div v-if="!(v && typeof v === 'object' && !Array.isArray(v))" class="kv"><span class="k">{{ k }}</span><span class="v num">{{ val(v) }}</span></div>
            </template>
          </div>
        </div>
      </div>
      <div v-if="!shown.length" class="empty">
        <Icon :name="running ? 'search' : 'shield'" :size="22" />
        <span>{{ running ? "正在检测，发现的疑点会出现在这里" : tab === "issues" ? "没有发现疑点" : "没有来源信息" }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.fp { display: flex; flex-direction: column; min-height: 0; flex: 1; overflow: hidden; }
.tabs { display: flex; gap: 4px; padding: 8px 10px; border-bottom: 1px solid var(--border); }
.tab { height: 28px; padding: 0 10px; color: var(--muted); font-weight: 500; }
.tab.on { color: var(--text); background: var(--surface-3); }
.n { font-size: 10.5px; color: var(--muted); background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 0 5px; margin-left: 2px; }
.list { flex: 1; overflow: auto; padding: 8px; display: flex; flex-direction: column; gap: 6px; }
.it { --c: var(--unknown); position: relative; border-radius: 9px; background: var(--surface-2); border: 1px solid var(--border); cursor: pointer; transition: border-color .15s, background .15s; animation: rise .3s ease both; }
.it::before { content: ""; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px; border-radius: 0 3px 3px 0; background: var(--c); }
.it.low { --c: var(--low); } .it.medium { --c: var(--warn); } .it.high { --c: var(--danger); }
.it:hover { border-color: var(--border-2); }
.it.on { border-color: color-mix(in srgb, var(--c) 55%, transparent); background: color-mix(in srgb, var(--c) 7%, var(--surface-2)); }
.row { display: flex; align-items: center; gap: 10px; padding: 10px 10px 10px 14px; }
.sev { font-size: 10.5px; font-weight: 700; color: var(--c); border: 1px solid color-mix(in srgb, var(--c) 45%, transparent); border-radius: 5px; padding: 1px 6px; white-space: nowrap; }
.info .sev { color: var(--muted); }
.body { flex: 1; min-width: 0; }
.ti { font-size: 13px; line-height: 1.45; color: var(--text); }
.meta { font-size: 11px; color: var(--muted); margin-top: 3px; display: flex; gap: 4px; flex-wrap: wrap; }
.tm { color: var(--accent-2); }
.go { width: 26px; height: 26px; border-radius: 50%; color: var(--accent-2); background: var(--accent-bg); flex: none; }
.go:hover { background: var(--accent); color: #fff; }
.more { padding: 0 12px 12px 14px; cursor: default; }
.more p { margin: 0 0 10px; font-size: 12.5px; line-height: 1.7; color: var(--text-2); }
.ev { border-radius: 8px; background: var(--lane); border: 1px solid var(--border); overflow: hidden; }
.kv { display: flex; gap: 10px; padding: 6px 10px; font-size: 11.5px; border-top: 1px solid var(--border); }
.kv:first-child { border-top: none; }
.k { color: var(--muted); flex: none; min-width: 120px; }
.kv.grp .k { color: var(--text-2); font-weight: 600; }
.kv.sub { padding-left: 22px; }
.v { color: var(--text-2); word-break: break-all; font-size: 11.5px; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 44px 12px; color: var(--faint); font-size: 12px; text-align: center; }
</style>
