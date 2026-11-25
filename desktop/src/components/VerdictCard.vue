<script setup lang="ts">
import Icon from "./Icon.vue"
import { LEVEL_TEXT, type Verdict } from "../types"

defineProps<{ label: string; icon: string; verdict: Verdict; count: number }>()
const ICON = { none: "shield", suspicious: "alert", likely: "octagon", unknown: "help" }
</script>

<template>
  <div class="verdict card" :class="verdict.level">
    <div class="top">
      <span class="label"><Icon :name="icon" :size="15" />{{ label }}</span>
      <span v-if="count" class="count">{{ count }} 个疑点</span>
    </div>
    <div class="main">
      <div class="sym"><Icon :name="ICON[verdict.level]" :size="26" :stroke="2" /></div>
      <div class="lv">{{ LEVEL_TEXT[verdict.level] }}</div>
    </div>
    <div class="txt">{{ verdict.text }}</div>
  </div>
</template>

<style scoped>
.verdict { flex: 1; padding: 14px 16px 16px; position: relative; overflow: hidden; min-width: 0; }
.verdict::before { content: ""; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--c); }
.verdict { --c: var(--unknown); --cb: var(--unknown-bg); }
.verdict.none { --c: var(--ok); --cb: var(--ok-bg); }
.verdict.suspicious { --c: var(--warn); --cb: var(--warn-bg); }
.verdict.likely { --c: var(--danger); --cb: var(--danger-bg); }
.top { display: flex; justify-content: space-between; align-items: center; }
.label { display: inline-flex; gap: 6px; align-items: center; font-size: 13px; color: var(--muted); }
.count { font-size: 12px; color: var(--c); background: var(--cb); padding: 1px 8px; border-radius: 10px; }
.main { display: flex; align-items: center; gap: 10px; margin: 10px 0 6px; }
.sym { width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center; color: var(--c); background: var(--cb); }
.lv { font-size: 24px; font-weight: 650; color: var(--c); letter-spacing: 1px; }
.txt { font-size: 13px; color: var(--text-2); line-height: 1.55; }
</style>
