// 云端地址的安全判断（纯函数，单元测试覆盖）。问题清单 P2-4：
// 明文 http 发往公网会泄露访问令牌和证据素材。本机、内网地址（127.x、10.x、172.16-31.x、192.168.x、*.local、::1、fc00::/7）允许 http。

export function normalizeUrl(u: string): string {
  const t = u.trim().replace(/\/+$/, "")
  if (!t) return ""
  let url: URL
  try { url = new URL(t) } catch { throw new Error("服务器地址格式不对") }
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new Error("服务器地址要以 http:// 或 https:// 开头")
  if (url.username || url.password) throw new Error("地址里不要带用户名密码，令牌单独填")
  return t
}

export function isPrivateHost(host: string): boolean {
  const h = host.replace(/^\[|\]$/g, "").toLowerCase()
  if (h === "localhost" || h.endsWith(".local") || h === "::1") return true
  if (/^f[cd][0-9a-f]{2}:/.test(h)) return true // IPv6 唯一本地地址
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(h)
  if (!m) return false
  const [a, b] = [Number(m[1]), Number(m[2])]
  return a === 127 || a === 10 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)
}

// 公网上的明文 http：要用户明确确认才能用
export function isInsecurePublic(u: string): boolean {
  if (!u) return false
  try {
    const url = new URL(u)
    return url.protocol === "http:" && !isPrivateHost(url.hostname)
  } catch {
    return false
  }
}
