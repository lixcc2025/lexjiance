// 结论规则（要和引擎 engine/avengine/verdict.py 一致）
import { describe, expect, it } from "vitest"
import { sortFindings, verdict } from "../shared/verdict"
import type { Finding } from "../shared/schema"

const f = (category: Finding["category"], severity: Finding["severity"], start: number | null = null): Finding =>
  ({ detector: "t", category, severity, title: "x", detail: "", modality: "file", start, end: null, evidence: {} })

describe("verdict", () => {
  it("AI：高度可疑 / 有疑点 / 无法判断 / 未发现", () => {
    expect(verdict([f("ai", "high")], "ai").level).toBe("likely")
    expect(verdict([f("ai", "medium")], "ai").level).toBe("suspicious")
    expect(verdict([f("ai", "info")], "ai").level).toBe("unknown")       // 模型没跑，不能说没有
    expect(verdict([], "ai", true).level).toBe("none")
  })
  it("剪辑：只看剪辑类疑点，说明类不算", () => {
    expect(verdict([f("ai", "high"), f("edit", "info")], "edit").level).toBe("none")
    expect(verdict([f("edit", "low")], "edit").level).toBe("suspicious")
    expect(verdict([f("edit", "high")], "edit").level).toBe("likely")
  })
  it("排序：严重的在前，同级按时间", () => {
    const s = sortFindings([f("edit", "low", 5), f("edit", "high", 9), f("edit", "low", 1)])
    expect(s.map((x) => [x.severity, x.start])).toEqual([["high", 9], ["low", 1], ["low", 5]])
  })
})
