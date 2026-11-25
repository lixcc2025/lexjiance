// 两项结论的规则：和引擎 engine/avengine/verdict.py 逐字一致，用同一套标准用例 tests-shared/verdict-cases.json 校验。
// 引擎给出本机结果；合并云端 AI 结果后在这里重算。
//
// 剪辑痕迹（问题清单 P0-4）：单一类型的弱信号不能直接说「明显剪辑」——
//   有 high → 高度可疑；同一位置（前后 WINDOW 秒内）两类以上证据互相印证 → 高度可疑；其余有疑点的 → 有疑点

import type { Category, Finding, Verdict } from "./schema"

export const RANK: Record<string, number> = { info: 0, low: 1, medium: 2, high: 3 }
export const WINDOW = 2.0

// 证据类型的中文名；顺序就是结论文字里列出的顺序
export const SIGNAL_NAMES: Record<string, string> = {
  ts_gap: "时间戳断档", keyframe: "关键帧异常", av_length: "音画时长不一致",
  digital_silence: "数字静音", digital_silence_many: "大量数字静音", noise_floor: "底噪突变", bandwidth: "频带突变",
  editor: "剪辑软件痕迹", aigc_label: "AI 隐式标识", ai_tool: "元数据里的 AI 工具名", ai_tool_human: "人工字段提到 AI 工具",
  c2pa: "内容凭证",
}

const signalOf = (f: Finding) => f.signal || f.detector
const rank = (s: string) => RANK[s] ?? 0

// Python 的 sorted() 对字符串按码点比较；这里同样用码点比较，不用 localeCompare
const cmp = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0)

function names(signals: Set<string>): string {
  const known = Object.keys(SIGNAL_NAMES).filter((k) => signals.has(k)).map((k) => SIGNAL_NAMES[k])
  const other = [...signals].filter((s) => !(s in SIGNAL_NAMES)).sort(cmp).map((s) => s || "其他")
  return [...known, ...other].join("、")
}

export function corroborated(hits: Finding[]): Set<string> {
  const timed = hits
    .filter((f) => f.start !== null)
    .sort((a, b) => (a.start! - b.start!) || ((a.end ?? a.start!) - (b.end ?? b.start!)) || cmp(signalOf(a), signalOf(b)))
  let best = new Set<string>()
  for (const a of timed) {
    const a0 = a.start!, a1 = a.end ?? a.start!
    const group = new Set([signalOf(a)])
    for (const b of timed) {
      const b0 = b.start!, b1 = b.end ?? b.start!
      if (a0 - WINDOW <= b1 && b0 <= a1 + WINDOW) group.add(signalOf(b))
    }
    if (group.size > best.size) best = group
  }
  return best.size >= 2 ? best : new Set()
}

export function verdict(findings: Finding[], category: Category, aiModelsRan = false): Verdict {
  const hits = findings.filter((f) => f.category === category && rank(f.severity) > 0)
  const top = Math.max(0, ...hits.map((f) => rank(f.severity)))
  const v = (level: Verdict["level"], text: string): Verdict => ({ level, text, score: null })
  if (category === "ai") {
    if (top >= 3) return v("likely", "很可能是 AI 生成或经过 AI 合成，见下方疑点")
    if (top >= 1) return v("suspicious", "有 AI 生成的迹象，建议进一步核实")
    if (!aiModelsRan) return v("unknown", "元数据里没有 AI 标识；AI 识别（云端模型）未运行，不能排除 AI 生成")
    return v("none", "没有发现 AI 生成的迹象（不等于一定是真实录制）")
  }
  if (!hits.length) return v("none", "没有发现剪辑痕迹（重新编码导出的剪辑可能检测不到）")
  if (top >= 3) return v("likely", "有明显的剪辑痕迹，见下方疑点位置")
  const corr = corroborated(hits)
  if (corr.size) return v("likely", `同一位置有 ${corr.size} 类证据互相印证（${names(corr)}），剪辑痕迹明显，见下方疑点位置`)
  const kinds = new Set(hits.map(signalOf))
  const why = kinds.size === 1 ? "单一类型的痕迹也可能是录制设备造成" : "这几类痕迹不在同一位置，单独看都可能是录制设备造成"
  return v("suspicious", `有可疑的剪辑痕迹（${names(kinds)}），${why}，建议对照疑点位置回放核实`)
}

export function sortFindings(list: Finding[]): Finding[] {
  return [...list].sort((a, b) => rank(b.severity) - rank(a.severity) || (a.start ?? -1) - (b.start ?? -1))
}
