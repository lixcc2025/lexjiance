// 设置：settings.json（主题、云端地址、是否启用云端）。
// 云端令牌用系统加密（Windows DPAPI / macOS 钥匙串）单独存 cloud-token.bin，不写进 settings.json，也不发给页面。

import { safeStorage } from "electron"
import { existsSync, mkdirSync, readFileSync, unlinkSync, writeFileSync } from "fs"
import { dirname } from "path"
import type { Settings, SettingsPatch, Theme } from "../../shared/schema"
import { settingsFile, tokenFile } from "./paths"
import { log } from "./log"

interface Stored { theme: Theme; cloud: { enabled: boolean; url: string } }
const DEFAULTS: Stored = { theme: "system", cloud: { enabled: false, url: "" } }

let cache: Stored | null = null

function load(): Stored {
  if (cache) return cache
  try {
    const raw = JSON.parse(readFileSync(settingsFile(), "utf8"))
    cache = {
      theme: ["system", "light", "dark"].includes(raw.theme) ? raw.theme : DEFAULTS.theme,
      cloud: { enabled: !!raw.cloud?.enabled, url: typeof raw.cloud?.url === "string" ? raw.cloud.url : "" },
    }
  } catch {
    cache = structuredClone(DEFAULTS)
  }
  return cache
}

function persist(s: Stored) {
  mkdirSync(dirname(settingsFile()), { recursive: true })
  writeFileSync(settingsFile(), JSON.stringify(s, null, 2))
}

export function getCloudToken(): string {
  try {
    if (!existsSync(tokenFile())) return ""
    const buf = readFileSync(tokenFile())
    return safeStorage.isEncryptionAvailable() ? safeStorage.decryptString(buf) : buf.toString("utf8")
  } catch (e) {
    log.warn("读取云端令牌失败", e)
    return ""
  }
}

function setCloudToken(token: string | null) {
  if (!token) { try { unlinkSync(tokenFile()) } catch { /* 本来就没有 */ } return }
  mkdirSync(dirname(tokenFile()), { recursive: true })
  writeFileSync(tokenFile(), safeStorage.isEncryptionAvailable() ? safeStorage.encryptString(token) : Buffer.from(token, "utf8"))
}

export function getSettings(): Settings {
  const s = load()
  return { theme: s.theme, cloud: { ...s.cloud, hasToken: !!getCloudToken() } }
}

// 地址只接受 http(s)，去掉结尾的斜杠
export function normalizeUrl(u: string): string {
  const t = u.trim().replace(/\/+$/, "")
  if (!t) return ""
  if (!/^https?:\/\/[^\s/]+/i.test(t)) throw new Error("服务器地址要以 http:// 或 https:// 开头")
  return t
}

export function saveSettings(patch: SettingsPatch): Settings {
  const s = load()
  if (patch.theme && ["system", "light", "dark"].includes(patch.theme)) s.theme = patch.theme
  if (patch.cloud) {
    if (patch.cloud.url !== undefined) s.cloud.url = normalizeUrl(patch.cloud.url)
    if (patch.cloud.enabled !== undefined) s.cloud.enabled = !!patch.cloud.enabled
    if (patch.cloud.token !== undefined) setCloudToken(patch.cloud.token)
  }
  persist(s)
  return getSettings()
}
