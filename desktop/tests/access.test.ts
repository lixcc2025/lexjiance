// 回放白名单（问题清单 P2-1、P2-6）：任意路径加不进来、符号链接绕不过去、预览目录前缀判断不被「同名前缀」骗过
import { mkdirSync, mkdtempSync, rmSync, symlinkSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { join } from "node:path"
import { afterAll, describe, expect, it } from "vitest"
import { Access, isMediaFile } from "../electron/main/access"

const d = mkdtempSync(join(tmpdir(), "avd-access-"))
const preview = join(d, "preview")
mkdirSync(preview)
const video = join(d, "证据 录像.mp4")
const secret = join(d, "secret.ini")
const sneaky = join(d, "preview-evil")            // 和预览目录同名前缀
writeFileSync(video, "x")
writeFileSync(secret, "password=1")
mkdirSync(sneaky)
writeFileSync(join(sneaky, "a.png"), "x")
writeFileSync(join(preview, "frame_00.jpg"), "x")
// 预览目录里指向外面的符号链接（Windows 上没有权限建符号链接时跳过这一项）
let linked = true
try { symlinkSync(secret, join(preview, "link.jpg")) } catch { linked = false }
afterAll(() => rmSync(d, { recursive: true, force: true }))

describe("Access", () => {
  const acc = new Access(() => [preview])

  it("只接受存在的音视频文件", () => {
    expect(isMediaFile(video)).toBe(true)
    expect(acc.allowMedia(secret)).toBe(false)                         // 不是音视频
    expect(acc.allowMedia(join(d, "不存在.mp4"))).toBe(false)
    expect(acc.allowMedia("relative/x.mp4")).toBe(false)               // 相对路径
    expect(acc.allowMedia(d)).toBe(false)                              // 目录
    expect(acc.allowMedia(123)).toBe(false)
  })

  it("没加进来的读不到；加进来的能读", () => {
    expect(acc.isAllowed(video)).toBe(false)
    expect(acc.allowMedia(video)).toBe(true)
    expect(acc.isAllowed(video)).toBe(true)
    expect(acc.isAllowed(secret)).toBe(false)
  })

  it("预览目录：里面的能读，同名前缀的兄弟目录、指向外面的符号链接不能读", () => {
    expect(acc.isAllowed(join(preview, "frame_00.jpg"))).toBe(true)
    expect(acc.isAllowed(join(sneaky, "a.png"))).toBe(false)
    if (linked) expect(acc.isAllowed(join(preview, "link.jpg"))).toBe(false)
    expect(acc.isAllowed(join(preview, "..", "secret.ini"))).toBe(false)
  })

  it.runIf(process.platform === "win32" || process.platform === "darwin")("Windows / macOS 不分大小写", () => {
    expect(acc.isAllowed(video.toUpperCase())).toBe(true)
  })
})
