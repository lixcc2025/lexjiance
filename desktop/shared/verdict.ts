// 两项结论的规则：和引擎的 engine/avengine/verdict.py 一致（引擎给出本机结果，合并云端 AI 结果后在这里重算）

import type { Category, Finding, Verdict } from "./schema"

export const RANK = { info: 0, low: 1, medium: 2, high: 3 } as const

export function verdict(findings: Finding[], category: Category, aiModelsRan = false): Verdict {
  const top = Math.max(0, ...findings.filter((f) => f.category === category && f.severity !== "info").map((f) => RANK[f.severity]))
  if (category === "ai") {
    if (top >= 3) return { level: "likely", text: "很可能是 AI 生成或经过 AI 合成，见下方疑点", score: null }
    if (top >= 1) return { level: "suspicious", text: "有 AI 生成的迹象，建议进一步核实", score: null }
    if (!aiModelsRan) return { level: "unknown", text: "元数据里没有 AI 标识；AI 识别（云端模型）未运行，不能排除 AI 生成", score: null }
    return { level: "none", text: "没有发现 AI 生成的迹象（不等于一定是真实录制）", score: null }
  }
  if (top >= 3) return { level: "likely", text: "有明显的剪辑痕迹，见下方疑点位置", score: null }
  if (top >= 1) return { level: "suspicious", text: "有可疑的剪辑痕迹，建议对照疑点位置回放核实", score: null }
  return { level: "none", text: "没有发现剪辑痕迹（重新编码导出的剪辑可能检测不到）", score: null }
}

export function sortFindings(list: Finding[]): Finding[] {
  return [...list].sort((a, b) => RANK[b.severity] - RANK[a.severity] || (a.start ?? -1) - (b.start ?? -1))
}
