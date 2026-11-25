<script setup lang="ts">
// Windows 标题栏：左边软件名和当前文件名，右上角留给系统的最小化 / 最大化 / 关闭（窗口控件覆盖）
defineProps<{ file: string | null }>()
const base = (p: string) => p.split(/[\\/]/).pop()
</script>

<template>
  <div class="titlebar drag">
    <div class="logo"><svg viewBox="0 0 32 32" width="13" height="13"><path d="M3 16h4l3-8 4 16 4-12 3 7 2-3h6" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" /></svg></div>
    <span class="name">音视频检测</span>
    <template v-if="file"><span class="sep">—</span><span class="file">{{ base(file) }}</span></template>
  </div>
</template>

<style scoped>
.titlebar { height: 40px; flex: none; display: flex; align-items: center; gap: 8px; padding: 0 150px 0 14px; background: var(--surface); border-bottom: 1px solid var(--border); font-size: 12px; color: var(--text-2); }
.logo { width: 20px; height: 20px; border-radius: 6px; display: grid; place-items: center; background: linear-gradient(145deg, #3a6fe0 0%, #1d3a8a 100%); }
.name { font-weight: 600; color: var(--text); }
.sep { color: var(--faint); }
.file { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
