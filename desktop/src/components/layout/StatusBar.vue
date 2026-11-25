<script setup lang="ts">
import Icon from "../common/Icon.vue"
</script>

<template>
  <footer class="status">
    <span><Icon name="info" :size="12" />检测结果是辅助判断的线索，不是鉴定结论；作为证据使用应委托司法鉴定机构</span>
    <span class="grow" />
    <span class="keys">空格 播放 · ←/→ 1 秒 · Shift+←/→ 5 秒</span>
  </footer>
</template>

<style scoped>
.status { height: 28px; flex: none; display: flex; align-items: center; gap: 8px; padding: 0 16px; font-size: 11px; color: var(--faint); border-top: 1px solid var(--border); background: var(--surface); }
.status span { display: inline-flex; align-items: center; gap: 5px; }
.grow { flex: 1; }
.keys { font-family: var(--mono); font-size: 10.5px; }
@media (max-height: 760px) { .status { height: 24px; } .keys { display: none; } }
</style>
