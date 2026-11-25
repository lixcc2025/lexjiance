// 设置和平台信息（全局一份）：主题、云端识别配置、是 macOS 还是 Windows
import { computed, ref } from "vue"
import type { AppInfo, CloudHealth, Settings, Theme } from "../types"

const settings = ref<Settings>({ theme: "system", cloud: { enabled: false, url: "", hasToken: false, insecure: false, allowInsecure: false }, keepHistory: true })
const info = ref<AppInfo>({ platform: "", version: "", titlebar: 0 })
let loaded: Promise<void> | null = null

export function useSettings() {
  const mac = computed(() => info.value.platform === "darwin")

  function load() {
    loaded ||= Promise.all([window.avd.getSettings(), window.avd.appInfo()]).then(([s, i]) => {
      settings.value = s
      info.value = i
      document.body.classList.toggle("mac", i.platform === "darwin")
      document.body.classList.toggle("win", i.platform !== "darwin")
    })
    return loaded
  }

  async function setTheme(theme: Theme) {
    settings.value = await window.avd.saveSettings({ theme })
  }

  // token：传 undefined 不改，传 "" 或 null 清除
  async function saveCloud(cloud: { enabled?: boolean; url?: string; token?: string | null; allowInsecure?: boolean }) {
    settings.value = await window.avd.saveSettings({ cloud: { ...cloud, token: cloud.token === "" ? null : cloud.token } })
  }

  async function setKeepHistory(keep: boolean) {
    settings.value = await window.avd.saveSettings({ keepHistory: keep })
  }

  const testCloud = (): Promise<CloudHealth> => window.avd.testCloud()

  return { settings, info, mac, load, setTheme, saveCloud, setKeepHistory, testCloud }
}
