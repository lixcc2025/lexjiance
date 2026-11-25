// 云端地址（问题清单 P2-4）：公网 http 明文要确认；本机、内网允许 http
import { describe, expect, it } from "vitest"
import { isInsecurePublic, isPrivateHost, normalizeUrl } from "../electron/main/url-policy"

describe("url-policy", () => {
  it("规范化", () => {
    expect(normalizeUrl(" https://ai.example.com/ ")).toBe("https://ai.example.com")
    expect(normalizeUrl("")).toBe("")
    expect(() => normalizeUrl("ftp://x")).toThrow()
    expect(() => normalizeUrl("not a url")).toThrow()
    expect(() => normalizeUrl("https://user:pw@x.com")).toThrow()
  })
  it("内网地址", () => {
    for (const h of ["localhost", "127.0.0.1", "10.1.2.3", "172.16.0.1", "172.31.255.1", "192.168.1.5", "ai.local", "[::1]", "fd12:3456::1"]) expect(isPrivateHost(h), h).toBe(true)
    for (const h of ["172.32.0.1", "8.8.8.8", "example.com", "11.0.0.1"]) expect(isPrivateHost(h), h).toBe(false)
  })
  it("公网明文才算不安全", () => {
    expect(isInsecurePublic("http://ai.example.com")).toBe(true)
    expect(isInsecurePublic("http://8.8.8.8:8080")).toBe(true)
    expect(isInsecurePublic("https://ai.example.com")).toBe(false)
    expect(isInsecurePublic("http://10.0.0.8:8080")).toBe(false)
    expect(isInsecurePublic("http://127.0.0.1:8765")).toBe(false)
    expect(isInsecurePublic("")).toBe(false)
  })
})
