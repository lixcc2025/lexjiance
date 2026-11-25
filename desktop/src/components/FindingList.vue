<script setup lang="ts">
// 疑点列表：按类别分页签，展开看依据（表格），点时间跳转
import { computed, ref } from "vue"
import Icon from "./Icon.vue"
import { CAT_TEXT, SEV_TEXT, fmtTime, type Category, type Finding } from "../types"

const props = defineProps<{ findings: Finding[]; active: number; live?: boolean }>()
const emit = defineEmits<{ (e: "select", index: number): void; (e: "seek", index: number): void }>()

type Tab = "issues" | Category
const tab = ref<Tab>("issues")
const open = ref<Set<number>>(new Set())

const indexed = computed(() => props.findings.map((f, i) => ({ f, i })))
const groups = computed(() => ({
  issues: indexed.value.filter((x) => x.f.severity !== "info"),
  ai: indexed.value.filter((x) => x.f.category === "ai"),
  edit: indexed.value.filter((x) => x.f.category === "edit"),
  source: indexed.value.filter((x) => x.f.category === "source"),
}))
const shown = computed(() => groups.value[tab.value])
const TABS: { key: Tab; label: string }[] = [
  { key: "issues", label: "全部疑点" },
  { key: "ai", label: "AI 生成" },
  { key: "edit", label: "剪辑痕迹" },
  { key: "source", label: "来源信息" },
]

function toggle(i: number) {
  const s = new Set(open.value)
  s.has(i) ? s.delete(i) : s.add(i)
  open.value = s
  emit("select", i)
}
function val(v: unknown): string {
  if (v === null || v === undefined) return "—"
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(3)
  if (typeof v === "object") return JSON.stringify(v)
  return String(v)
}
</script>

<template>
  <div class="findings card">
    <div class="tabs">
      <button v-for="t in TABS" :key="t.key" class="tab" :class="{ on: tab === t.key }" @click="tab = t.key">
        {{ t.label }}<span class="n">{{ groups[t.key].length }}</span>
      </button>
    </div>
    <div class="list">
      <div v-for="{ f, i } in shown" :key="i" class="item" :class="[f.severity, { active: active === i, open: open.has(i) }]">
        <div class="row" @click="toggle(i)">
          <span class="sev">{{ SEV_TEXT[f.severity] }}</span>
          <div class="body">
            <div class="title">{{ f.title }}</div>
            <div class="sub">{{ CAT_TEXT[f.category] }}<template v-if="f.modality !== 'file'"> · {{ f.modality === "video" ? "画面" : "声音" }}</template></div>
          </div>
          <button v-if="f.start !== null" class="time num" @click.stop="emit('seek', i)">
            <Icon name="play" :size="11" :stroke="2.4" />{{ fmtTime(f.start) }}<template v-if="f.end !== null && f.end !== f.start"> – {{ fmtTime(f.end) }}</template>
          </button>
          <Icon class="chev" name="chevron" :size="16" />
        </div>
        <div v-if="open.has(i)" class="more">
          <p v-if="f.detail">{{ f.detail }}</p>
          <table v-if="Object.keys(f.evidence).length">
            <tr v-for="(v, k) in f.evidence" :key="k"><th>{{ k }}</th><td>{{ val(v) }}</td></tr>
          </table>
        </div>
      </div>
      <div v-if="!shown.length" class="empty">
        <Icon :name="live ? 'clock' : 'shield'" :size="22" />
        <span>{{ live ? "正在检测…" : tab === "issues" ? "没有发现疑点" : "这一类没有内容" }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.findings { display: flex; flex-direction: column; min-height: 0; flex: 1; }
.tabs { display: flex; gap: 2px; padding: 8px 10px 0; border-bottom: 1px solid var(--line); }
.tab { height: 36px; border: none; border-radius: 0; background: none; color: var(--muted); padding: 0 12px; border-bottom: 2px solid transparent; }
.tab:hover { background: none; color: var(--text); }
.tab.on { color: var(--brand); border-bottom-color: var(--brand); font-weight: 600; }
.tab .n { font-size: 11px; background: var(--line-2); color: var(--muted); border-radius: 8px; padding: 0 6px; margin-left: 2px; font-weight: 400; }
.tab.on .n { background: var(--brand-weak); color: var(--brand); }
.list { overflow: auto; padding: 8px; flex: 1; display: flex; flex-direction: column; gap: 6px; }
.item { border: 1px solid var(--line-2); border-radius: 10px; transition: border-color .15s, box-shadow .15s; --c: var(--faint); --cb: var(--line-2); }
.item.low { --c: var(--low); --cb: var(--low-bg); }
.item.medium { --c: var(--warn); --cb: var(--warn-bg); }
.item.high { --c: var(--danger); --cb: var(--danger-bg); }
.item:hover { border-color: #d5dcea; }
.item.active { border-color: var(--c); box-shadow: 0 0 0 3px var(--cb); }
.row { display: flex; align-items: center; gap: 10px; padding: 10px 12px; cursor: pointer; }
.sev { font-size: 12px; font-weight: 600; color: var(--c); background: var(--cb); border-radius: 6px; padding: 2px 8px; white-space: nowrap; min-width: 52px; text-align: center; }
.item.info .sev { color: var(--muted); }
.body { flex: 1; min-width: 0; }
.title { line-height: 1.45; }
.sub { font-size: 12px; color: var(--faint); margin-top: 2px; }
.time { height: 26px; padding: 0 9px; font-size: 12px; color: var(--brand); border-color: #d6e0fb; background: #f5f8ff; gap: 5px; }
.time:hover { background: var(--brand-weak); color: var(--brand); }
.chev { color: var(--faint); transition: transform .15s; flex: none; }
.item.open .chev { transform: rotate(180deg); }
.more { padding: 0 14px 12px 74px; }
.more p { margin: 0 0 8px; font-size: 13px; line-height: 1.65; color: var(--text-2); }
table { border-collapse: collapse; width: 100%; font-size: 12px; }
th, td { text-align: left; padding: 5px 8px; border-top: 1px solid var(--line-2); vertical-align: top; }
th { color: var(--muted); font-weight: 400; width: 30%; white-space: nowrap; }
td { color: var(--text-2); word-break: break-all; font-family: ui-monospace, Menlo, Consolas, monospace; }
.empty { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 36px 0; color: var(--faint); font-size: 13px; }
</style>
