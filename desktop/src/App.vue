<script setup lang="ts">
// 外壳：标题栏（Windows）+ 侧栏 + 首页 / 工作台 + 设置窗口 + 拖放遮罩。状态在 composables 里
import { computed, onBeforeUnmount, onMounted, ref } from "vue"
import Icon from "./components/common/Icon.vue"
import TitleBar from "./components/layout/TitleBar.vue"
import Sidebar from "./components/layout/Sidebar.vue"
import HomeHero from "./components/home/HomeHero.vue"
import Workspace from "./components/workspace/Workspace.vue"
import SettingsDialog from "./components/settings/SettingsDialog.vue"
import { useAnalysis } from "./composables/useAnalysis"
import { useHistory } from "./composables/useHistory"
import { useSettings } from "./composables/useSettings"

const a = useAnalysis()
const { history, clear } = useHistory()
const { settings, mac, load, setTheme } = useSettings()
const dragging = ref(false)
const showSettings = ref(false)
const ws = ref<InstanceType<typeof Workspace> | null>(null)
const cloudState = computed(() => (!settings.value.cloud.enabled ? "off" : settings.value.cloud.url ? "on" : "nourl"))

async function choose() {
  const p = await window.avd.pickFile()
  if (p) a.start(p)
}
function onDrop(e: DragEvent) {
  dragging.value = false
  const f = e.dataTransfer?.files?.[0]
  if (f) a.start(window.avd.pathOf(f))
}

function onKey(e: KeyboardEvent) {
  const tag = (e.target as HTMLElement)?.tagName
  if (tag === "INPUT" || tag === "TEXTAREA") return
  const mod = e.metaKey || e.ctrlKey
  if (mod && e.key.toLowerCase() === "o") { e.preventDefault(); choose(); return }
  if (mod && e.key === ",") { e.preventDefault(); showSettings.value = true; return }
  if (e.key === "Escape") { if (showSettings.value) showSettings.value = false; else ws.value?.deselect(); return }
  if (!a.file.value || showSettings.value) return
  if (e.key === " ") { e.preventDefault(); ws.value?.toggle() }
  else if (e.key === "ArrowLeft") ws.value?.step(e.shiftKey ? -5 : -1)
  else if (e.key === "ArrowRight") ws.value?.step(e.shiftKey ? 5 : 1)
}

onMounted(async () => {
  await load()
  window.avd.onMenu((c) => { if (c === "open") choose(); else if (c === "settings") showSettings.value = true })
  window.addEventListener("keydown", onKey)
  await a.init()
})
onBeforeUnmount(() => window.removeEventListener("keydown", onKey))
</script>

<template>
  <div class="shell" :class="{ mac, win: !mac }" @dragover.prevent="dragging = true" @dragleave.self.prevent="dragging = false" @drop.prevent="onDrop">
    <TitleBar v-if="!mac" :file="a.file.value" />
    <div class="body">
      <Sidebar :history="history" :active="a.file.value" :engine-ready="a.detectors.value.length > 0" :mac="mac" :theme="settings.theme" :cloud="cloudState"
        @new="choose" @open="a.openExisting" @home="a.close()" @clear="clear" @theme="(t) => setTheme(t as any)" @settings="showSettings = true" />
      <section class="main">
        <HomeHero v-if="!a.file.value" :dragging="dragging" :mac="mac" @pick="choose" />
        <Workspace v-else ref="ws" :key="a.file.value" :mac="mac" />
      </section>
    </div>
    <SettingsDialog v-if="showSettings" @close="showSettings = false" />
    <div v-if="dragging" class="mask"><div class="mask-box"><Icon name="upload" :size="26" />松开即可开始检测</div></div>
  </div>
</template>

<style scoped>
.shell { height: 100%; display: flex; flex-direction: column; position: relative; }
.body { flex: 1; min-height: 0; display: flex; }
.main { flex: 1; min-width: 0; display: flex; flex-direction: column; background: var(--bg); }
.mask { position: absolute; inset: 0; z-index: 10; display: grid; place-items: center; pointer-events: none; background: rgba(10, 14, 24, .45); backdrop-filter: blur(4px); }
.mask-box { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 28px 44px; border-radius: 18px; color: var(--accent-2); font-size: 14px;
  background: var(--surface); border: 1.5px dashed var(--accent); box-shadow: 0 0 0 6px var(--accent-bg), 0 20px 60px rgba(0, 0, 0, .4); }
</style>
