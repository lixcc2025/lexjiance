// 云端结果：服务器返回的内容不完全可信，清洗后再合并；云端没跑时写明原因
import { describe, expect, it } from "vitest"
import { CLOUD_DETECTORS, cloudSkipped, mergeCloud, sanitizeResponse } from "../shared/cloud-protocol"
import type { AnalyzeResult } from "../shared/schema"

const local: AnalyzeResult = {
  file: "/a.mp4",
  media: { format: "MP4", duration: 20, size: 1, video: null, audio: null },
  ai: { level: "unknown", text: "", score: null },
  edit: { level: "suspicious", text: "", score: null },
  findings: [{ detector: "structure", category: "edit", severity: "medium", title: "断档", detail: "", modality: "video", start: 5, end: 7, evidence: {} }],
  detectors: [{ name: "metadata", title: "文件元数据", desc: "", ok: true, skipped: "", error: "", seconds: 0.1 }],
}

describe("sanitizeResponse", () => {
  it("丢掉字段不对的，补默认值，时间限制在文件时长内", () => {
    const r = sanitizeResponse({
      findings: [
        { category: "ai", severity: "high", title: "合成语音", start: 3, end: 99, detector: "ai_voice" },
        { category: "ai", severity: "critical", title: "等级不认识" },
        { category: "hack", severity: "high", title: "类别不认识" },
        { severity: "high", category: "ai" },
        "垃圾",
      ],
      detectors: [{ name: "ai_voice", ok: true, seconds: 2.5 }, { title: "没名字" }],
    }, 20)
    expect(r.findings).toHaveLength(1)
    expect(r.findings[0]).toMatchObject({ detector: "ai_voice", start: 3, end: 20, modality: "file", evidence: {} })
    expect(r.detectors).toHaveLength(1)
    expect(r.detectors[0]).toMatchObject({ name: "ai_voice", title: "AI 合成语音", ok: true, seconds: 2.5 })
  })
  it("不是对象也不崩", () => {
    expect(sanitizeResponse(null, 10)).toEqual({ findings: [], detectors: [] })
    expect(sanitizeResponse("x", 10)).toEqual({ findings: [], detectors: [] })
  })
})

describe("mergeCloud", () => {
  it("云端没启用：AI 结论仍是无法判断，三个云端检测项都写明原因", () => {
    const r = mergeCloud(local, null, cloudSkipped("云端识别未启用"))
    expect(r.ai.level).toBe("unknown")
    expect(r.edit.level).toBe("suspicious")
    const cloud = r.detectors.filter((d) => CLOUD_DETECTORS.some((c) => c.name === d.name))
    expect(cloud.map((d) => d.skipped)).toEqual(["云端识别未启用", "云端识别未启用", "云端识别未启用"])
  })
  it("云端出错：记成出错，不影响本机结果", () => {
    const r = mergeCloud(local, null, cloudSkipped("连不上服务器", true))
    expect(r.detectors.find((d) => d.name === "ai_voice")).toMatchObject({ ok: false, error: "连不上服务器" })
    expect(r.findings).toHaveLength(1)
  })
  it("云端跑了没发现：AI 结论变成未发现", () => {
    const r = mergeCloud(local, { findings: [], detectors: [{ name: "ai_voice", title: "AI 合成语音", desc: "", ok: true, skipped: "", error: "", seconds: 1 }] })
    expect(r.ai.level).toBe("none")
    expect(r.detectors.find((d) => d.name === "ai_video")?.skipped).toBe("服务器未返回")
  })
  it("云端发现合成语音：合并疑点、重算结论、按严重程度排序", () => {
    const r = mergeCloud(local, {
      findings: [{ detector: "ai_voice", category: "ai", severity: "high", title: "合成语音", detail: "", modality: "audio", start: 1, end: 4, evidence: { 分数: 0.97 } }],
      detectors: [{ name: "ai_voice", title: "AI 合成语音", desc: "", ok: true, skipped: "", error: "", seconds: 3 }],
    })
    expect(r.ai.level).toBe("likely")
    expect(r.findings.map((x) => x.title)).toEqual(["合成语音", "断档"])
    expect(r.detectors.map((d) => d.name)).toEqual(["metadata", "ai_voice", "ai_video", "watermark"])
  })
})
