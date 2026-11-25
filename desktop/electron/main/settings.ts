// 设置：settings.json（主题、云端地址、是否启用云端、是否保留检测记录）。
// 云端令牌用系统加密（Windows DPAPI / macOS 钥匙串）单独存 cloud-token.bin，不写进 settings.json，也不发给页面。
// 问题清单 P2-4 / P2-5：公网 http 地址要明确确认；系统加密用不了就拒绝保存令牌（不静默明文落盘）；文件 0600、原子写入。

import { safeStorage } from "electron"
import { existsSync, mkdirSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "fs"
import { dirname } from "path"
import type { Settings, SettingsPatch, Theme } from "../../shared/schema"
import { settingsFile, tokenFile } from "./paths"
import { isInsecurePublic, normalizeUrl } from "./url-policy"
import { log } from "./log"

interface Stored { theme: Theme; cloud: { enabled: boolean; url: string; allowInsecure: boolean }; keepHistory: boolean }
const DEFAULTS: Stored = { theme: "system", cloud: { enabled: false, url: "", allowInsecure: false }, keepHistory: true }

let cache: Stored | null = null

function load(): Stored {
  if (cache) return cache
  try {
    const raw = JSON.parse(readFileSync(settingsFile(), "utf8"))
    cache = {
      theme: ["system", "light", "dark"].includes(raw.theme) ? raw.theme : DEFAULTS.theme,
      cloud: {
        enabled: !!raw.cloud?.enabled,
        url: typeof raw.cloud?.url === "string" ? raw.cloud.url : "",
        allowInsecure: !!raw.cloud?.allowInsecure,
      },
      keepHistory: raw.keepHistory !== false,
    }
  } catch {
    cache = structuredClone(DEFAULTS)
  }
  return cache
}

// 先写临时文件再改名：写到一半崩溃也不会把设置弄坏
function writeAtomic(file: string, data: string | Buffer) {
  mkdirSync(dirname(file), { recursive: true, mode: 0o700 })
  const tmp = `${file}.${process.pid}.tmp`
  writeFileSync(tmp, data, { mode: 0o600 })
  renameSync(tmp, file)
}

export function getCloudToken(): string {
  try {
    if (!existsSync(tokenFile())) return ""
    if (!safeStorage.isEncryptionAvailable()) {
      log.warn("系统加密不可用，不读取云端令牌")
      return ""
    }
    return safeStorage.decryptString(readFileSync(tokenFile()))
  } catch (e) {
    log.warn("读取云端令牌失败（可能是旧版明文或换了电脑），已忽略", e)
    return ""
  }
}

function setCloudToken(token: string | null) {
  if (!token) { try { unlinkSync(tokenFile()) } catch { /* 本来就没有 */ } return }
  if (!safeStorage.isEncryptionAvailable()) throw new Error("这台电脑的系统加密不可用，不能安全保存令牌")
  writeAtomic(tokenFile(), safeStorage.encryptString(token))
}

export function getSettings(): Settings {
  const s = load()
  return {
    theme: s.theme,
    cloud: { enabled: s.cloud.enabled, url: s.cloud.url, hasToken: !!getCloudToken(), insecure: isInsecurePublic(s.cloud.url), allowInsecure: s.cloud.allowInsecure },
    keepHistory: s.keepHistory,
  }
}

export function saveSettings(patch: SettingsPatch): Settings {
  const s = structuredClone(load())
  if (patch.theme && ["system", "light", "dark"].includes(patch.theme)) s.theme = patch.theme
  if (typeof patch.keepHistory === "boolean") s.keepHistory = patch.keepHistory
  if (patch.cloud) {
    if (patch.cloud.url !== undefined) {
      const u = normalizeUrl(patch.cloud.url)
      if (u !== s.cloud.url) s.cloud.allowInsecure = false // 换了地址要重新确认
      s.cloud.url = u
    }
    if (patch.cloud.allowInsecure !== undefined) s.cloud.allowInsecure = !!patch.cloud.allowInsecure
    if (patch.cloud.enabled !== undefined) s.cloud.enabled = !!patch.cloud.enabled
    if (isInsecurePublic(s.cloud.url) && s.cloud.enabled && !s.cloud.allowInsecure) {
      throw new Error("这是公网上的 http 明文地址，令牌和上传的音轨、截图可能被截获。请改用 https，或勾选「我了解风险，仍然使用」")
    }
    if (patch.cloud.token !== undefined) setCloudToken(patch.cloud.token)
  }
  writeAtomic(settingsFile(), JSON.stringify(s, null, 2))
  cache = s
  return getSettings()
}

// 发令牌和素材前再检查一次
export function cloudSendAllowed(): boolean {
  const s = load()
  return !isInsecurePublic(s.cloud.url) || s.cloud.allowInsecure
}
