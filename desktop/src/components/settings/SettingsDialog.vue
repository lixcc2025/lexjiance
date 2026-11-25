<script setup lang="ts">
// 设置：外观、云端 AI 识别（地址、令牌、测试连接）、存储（缓存、日志）、关于
import { onMounted, ref } from "vue"
import Icon from "../common/Icon.vue"
import { fmtSize, type CloudHealth, type Theme } from "../../types"
import { useSettings } from "../../composables/useSettings"

const emit = defineEmits<{ (e: "close"): void }>()
const { settings, info, setTheme, saveCloud, testCloud } = useSettings()

const tab = ref<"look" | "cloud" | "storage" | "about">("look")
const url = ref(settings.value.cloud.url)
const token = ref("")
const enabled = ref(settings.value.cloud.enabled)
const saving = ref(false)
const msg = ref<{ ok: boolean; text: string } | null>(null)
const health = ref<CloudHealth | null>(null)
const testing = ref(false)
const cache = ref<number | null>(null)

const THEMES: { k: Theme; t: string }[] = [{ k: "system", t: "跟随系统" }, { k: "light", t: "浅色" }, { k: "dark", t: "深色" }]

async function save() {
  saving.value = true
  msg.value = null
  try {
    await saveCloud({ url: url.value, enabled: enabled.value, token: token.value ? token.value : undefined })
    token.value = ""
    msg.value = { ok: true, text: "已保存" }
  } catch (e: any) {
    msg.value = { ok: false, text: String(e?.message || e).replace(/^Error invoking remote method '[^']+': (Error: )?/, "") }
  } finally {
    saving.value = false
  }
}
async function clearToken() { await saveCloud({ token: null }); msg.value = { ok: true, text: "已清除访问令牌" } }
async function test() {
  testing.value = true
  health.value = null
  await save()
  health.value = await testCloud()
  testing.value = false
}
const openLogs = () => window.avd.openLogs()
async function refreshCache() { cache.value = await window.avd.cacheSize() }
async function clearCache() { await window.avd.clearCache(); await refreshCache() }

onMounted(refreshCache)
</script>

<template>
  <div class="overlay" @mousedown.self="emit('close')">
    <div class="dlg panel" role="dialog" aria-label="设置">
      <div class="head">
        <span class="title">设置</span>
        <button class="flat icon" title="关闭（Esc）" @click="emit('close')"><Icon name="x" :size="15" /></button>
      </div>
      <div class="body">
        <nav>
          <button class="flat" :class="{ on: tab === 'look' }" @click="tab = 'look'"><Icon name="layers" :size="14" />外观</button>
          <button class="flat" :class="{ on: tab === 'cloud' }" @click="tab = 'cloud'"><Icon name="cloud" :size="14" />云端 AI 识别</button>
          <button class="flat" :class="{ on: tab === 'storage' }" @click="tab = 'storage'; refreshCache()"><Icon name="folder" :size="14" />存储</button>
          <button class="flat" :class="{ on: tab === 'about' }" @click="tab = 'about'"><Icon name="info" :size="14" />关于</button>
        </nav>

        <section v-if="tab === 'look'">
          <h3>主题</h3>
          <div class="seg">
            <button v-for="m in THEMES" :key="m.k" class="flat" :class="{ on: settings.theme === m.k }" @click="setTheme(m.k)">{{ m.t }}</button>
          </div>
          <p class="hint">深色适合长时间看画面和波形；跟随系统会随 Windows / macOS 的深浅色设置自动切换。</p>
        </section>

        <section v-else-if="tab === 'cloud'">
          <h3>云端 AI 识别</h3>
          <p class="hint">AI 合成语音、AI 生成画面、隐形水印需要 AI 模型，在服务器上运行（可以是本单位内网的服务器）。
            启用后，检测时会把<b>提取的 16kHz 音轨和抽帧图片</b>发到下面的服务器，不上传原文件；识别完服务器应立即删除。</p>
          <label class="sw"><input v-model="enabled" type="checkbox" /><span>启用云端 AI 识别</span></label>
          <label class="field"><span>服务器地址</span><input v-model="url" class="selectable" placeholder="例如 https://ai.example.com 或 http://10.0.0.8:8080" spellcheck="false" /></label>
          <label class="field">
            <span>访问令牌</span>
            <input v-model="token" type="password" class="selectable" :placeholder="settings.cloud.hasToken ? '已保存（留空不修改）' : '服务器要求时填写'" />
          </label>
          <div class="row">
            <button class="primary" :disabled="saving" @click="save">保存</button>
            <button :disabled="testing || !url" @click="test"><Icon name="refresh" :size="13" />{{ testing ? "测试中…" : "测试连接" }}</button>
            <button v-if="settings.cloud.hasToken" class="flat" @click="clearToken">清除令牌</button>
            <span v-if="msg" class="msg" :class="{ bad: !msg.ok }">{{ msg.text }}</span>
          </div>
          <div v-if="health" class="health" :class="{ bad: !health.ok }">
            <Icon :name="health.ok ? 'check' : 'alert'" :size="14" />
            <span>{{ health.message }}<template v-if="health.version"> · 服务器版本 {{ health.version }}</template><template v-if="health.models?.length"> · 模型：{{ health.models.join("、") }}</template></span>
          </div>
        </section>

        <section v-else-if="tab === 'storage'">
          <h3>预览缓存</h3>
          <p class="hint">时间轴的缩略帧、波形、频谱图会缓存起来，同一个文件再打开时不用重算。缓存在系统临时目录，可以随时清理。</p>
          <div class="row"><span class="num big">{{ cache === null ? "…" : fmtSize(cache) }}</span><button @click="clearCache">清理缓存</button></div>
          <h3>日志</h3>
          <p class="hint">软件出问题时，把日志文件发给技术支持。日志里只有文件路径和出错信息，没有检测内容。</p>
          <div class="row"><button @click="openLogs"><Icon name="external" :size="13" />打开日志目录</button></div>
        </section>

        <section v-else>
          <h3>音视频检测</h3>
          <p class="hint">版本 <span class="num">{{ info.version }}</span> · {{ info.platform === "darwin" ? "macOS" : info.platform === "win32" ? "Windows" : info.platform }}</p>
          <p class="hint">本机检测：文件元数据（AI 生成标识、内容凭证、编辑软件、拍摄设备）、封装结构（时间戳断档、关键帧、音画时长）、声音剪辑痕迹（数字静音、底噪突变、频带突变）。</p>
          <p class="hint">检测结果是辅助判断的线索，不是鉴定结论；作为证据使用时应委托司法鉴定机构鉴定。</p>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; z-index: 50; display: grid; place-items: center; background: rgba(8, 10, 16, .5); backdrop-filter: blur(3px); animation: rise .2s ease both; }
.dlg { width: min(720px, calc(100vw - 48px)); height: min(480px, calc(100vh - 48px)); display: flex; flex-direction: column; overflow: hidden; }
.head { height: 48px; display: flex; align-items: center; justify-content: space-between; padding: 0 10px 0 18px; border-bottom: 1px solid var(--border); }
.title { font-size: 14px; font-weight: 650; }
.body { flex: 1; min-height: 0; display: flex; }
nav { width: 170px; flex: none; padding: 10px 8px; border-right: 1px solid var(--border); display: flex; flex-direction: column; gap: 2px; }
nav button { justify-content: flex-start; height: 32px; color: var(--text-2); }
nav button.on { background: var(--accent-bg); color: var(--accent-2); }
section { flex: 1; overflow: auto; padding: 14px 22px 20px; user-select: text; }
h3 { font-size: 13px; margin: 6px 0 8px; }
.hint { font-size: 12px; color: var(--muted); line-height: 1.7; margin: 0 0 12px; }
.hint b { color: var(--text-2); }
.seg { display: inline-flex; gap: 2px; padding: 2px; border-radius: 8px; background: var(--surface-3); margin-bottom: 10px; }
.seg button { height: 28px; color: var(--muted); }
.seg button.on { background: var(--surface); color: var(--text); box-shadow: 0 1px 2px rgba(0, 0, 0, .15); }
.sw { display: flex; align-items: center; gap: 8px; margin: 4px 0 12px; font-size: 13px; cursor: pointer; }
.field { display: flex; flex-direction: column; gap: 5px; margin-bottom: 12px; font-size: 12px; color: var(--text-2); }
.field input { height: 32px; border-radius: 8px; border: 1px solid var(--border-2); background: var(--surface-2); color: var(--text); padding: 0 10px; font: inherit; font-size: 13px; outline: none; }
.field input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-bg); }
.row { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.msg { font-size: 12px; color: var(--ok); }
.msg.bad { color: var(--danger); }
.health { display: flex; gap: 8px; align-items: center; padding: 9px 12px; border-radius: 8px; font-size: 12px; color: var(--ok); background: var(--ok-bg); }
.health.bad { color: var(--danger); background: var(--danger-bg); }
.big { font-size: 18px; min-width: 90px; }
</style>
