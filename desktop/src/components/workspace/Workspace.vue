<script setup lang="ts">
// 工作台：文件信息条 + 播放器 + 多轨时间轴 + 结论区 + 疑点检查器
import { computed, ref } from "vue"
import FileBar from "./FileBar.vue"
import Viewer from "./Viewer.vue"
import Timeline from "./Timeline.vue"
import VerdictPanel from "./VerdictPanel.vue"
import FindingsPanel from "./FindingsPanel.vue"
import StatusBar from "../layout/StatusBar.vue"
import { baseName, mediaUrl } from "../../types"
import { useAnalysis } from "../../composables/useAnalysis"

defineProps<{ mac: boolean }>()
const a = useAnalysis()
const viewer = ref<InstanceType<typeof Viewer> | null>(null)
const active = ref(-1)
const now = ref(0)
const mediaDur = ref(0)
const duration = computed(() => a.result.value?.media.duration || a.preview.value?.duration || mediaDur.value || 0)

function seek(t: number) { viewer.value?.seek(t) }
// 选中疑点：跳到疑点前 1 秒（看 / 听接缝前后）
function select(i: number) {
  active.value = i
  const f = a.findings.value[i]
  if (f && f.start !== null) seek(Math.max(0, f.start - 1))
}
function play(i: number) {
  active.value = i
  const f = a.findings.value[i]
  if (f && f.start !== null) viewer.value?.seek(Math.max(0, f.start - 1), true)
}
function reveal() { if (a.file.value) window.avd.showInFolder(a.file.value) }

// 给快捷键用
defineExpose({
  toggle: () => viewer.value?.toggle(),
  step: (d: number) => seek(now.value + d),
  deselect: () => (active.value = -1),
})
</script>

<template>
  <div class="ws">
    <FileBar :file="a.file.value!" :result="a.result.value" :is-video="a.isVideo.value" :can-retry="!!(a.result.value || a.error.value)" :mac="mac"
      @retry="a.start(a.file.value!)" @reveal="reveal" />
    <div class="work">
      <div class="stage-col">
        <div class="viewer-wrap">
          <Viewer ref="viewer" :key="a.file.value!" :url="mediaUrl(a.file.value!)" :is-video="a.isVideo.value" :name="baseName(a.file.value!)"
            :art="a.preview.value?.spectrogram ? mediaUrl(a.preview.value.spectrogram) : null" @time="(t) => (now = t)" @duration="(d) => (mediaDur = d)" />
        </div>
        <Timeline :duration="duration" :preview="a.preview.value" :findings="a.findings.value" :active="active" :now="now" :scanning="a.running.value" :is-video="a.isVideo.value"
          @seek="seek" @select="select" />
      </div>
      <div class="side-col">
        <VerdictPanel :result="a.result.value" :error="a.error.value" :pct="a.pct.value" :stage="a.stage.value" :detectors="a.detectors.value" :status="a.status.value"
          :current="a.current.value" :live="a.live.value" @cancel="a.cancel()" @retry="a.start(a.file.value!)" />
        <FindingsPanel :findings="a.findings.value" :active="active" :running="a.running.value" @select="select" @seek="play" />
      </div>
    </div>
    <StatusBar />
  </div>
</template>

<style scoped>
.ws { flex: 1; min-height: 0; display: flex; flex-direction: column; }
.work { flex: 1; min-height: 0; display: flex; gap: 12px; padding: 12px; }
.stage-col { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 12px; }
.viewer-wrap { flex: 1; min-height: 200px; }
.side-col { width: 384px; flex: none; display: flex; flex-direction: column; gap: 12px; min-height: 0; }
@media (max-width: 1320px) { .side-col { width: 340px; } }
@media (max-width: 1120px) { .side-col { width: 300px; } }
@media (max-height: 760px) {
  .work { gap: 10px; padding: 10px; }
  .stage-col, .side-col { gap: 10px; }
  .viewer-wrap { min-height: 130px; }
}
</style>
