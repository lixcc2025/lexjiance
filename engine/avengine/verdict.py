"""两项结论的规则。桌面端合并云端 AI 识别结果后会按同样的规则重算（desktop/shared/verdict.ts），两边逐字一致，
用同一套标准用例 tests-shared/verdict-cases.json 校验（问题清单 P0-4、P3-4）。

剪辑痕迹（问题清单 P0-4）：单一类型的弱信号（比如屏幕录制的一串时间戳断档、手机自动增益造成的一次底噪突变）不能直接说「明显剪辑」：
- 有 high → 高度可疑
- 同一位置（前后 WINDOW 秒内）有两类以上不同的证据互相印证 → 高度可疑，说明是哪几类
- 其余有疑点的 → 有疑点，说明依据了哪几类、单一类型也可能是设备造成
"""
from __future__ import annotations

from .models import AI, Finding, Verdict

RANK = {"info": 0, "low": 1, "medium": 2, "high": 3}
WINDOW = 2.0

# 证据类型的中文名；顺序就是结论文字里列出的顺序
SIGNAL_NAMES = {
    "ts_gap": "时间戳断档", "keyframe": "关键帧异常", "av_length": "音画时长不一致",
    "digital_silence": "数字静音", "digital_silence_many": "大量数字静音", "noise_floor": "底噪突变", "bandwidth": "频带突变",
    "editor": "剪辑软件痕迹", "aigc_label": "AI 隐式标识", "ai_tool": "元数据里的 AI 工具名", "ai_tool_human": "人工字段提到 AI 工具",
    "c2pa": "内容凭证",
}


def _names(signals: set[str]) -> str:
    known = [k for k in SIGNAL_NAMES if k in signals]
    other = sorted(s for s in signals if s not in SIGNAL_NAMES)
    return "、".join([SIGNAL_NAMES[k] for k in known] + [s or "其他" for s in other])


def _signal(f: Finding) -> str:
    return f.signal or f"{f.detector}"


def corroborated(hits: list[Finding]) -> set[str]:
    """同一位置互相印证的证据类型（取类型最多的那一处）；不到两类返回空集"""
    timed = sorted((f for f in hits if f.start is not None), key=lambda f: (f.start, f.end if f.end is not None else f.start, _signal(f)))
    best: set[str] = set()
    for a in timed:
        a0, a1 = a.start, a.end if a.end is not None else a.start
        group = {_signal(a)}
        for b in timed:
            b0, b1 = b.start, b.end if b.end is not None else b.start
            if a0 - WINDOW <= b1 and b0 <= a1 + WINDOW:
                group.add(_signal(b))
        if len(group) > len(best):
            best = group
    return best if len(best) >= 2 else set()


def verdict(findings: list[Finding], category: str, ai_models_ran: bool = False) -> Verdict:
    hits = [f for f in findings if f.category == category and RANK.get(f.severity, 0) > 0]
    top = max((RANK[f.severity] for f in hits), default=0)
    if category == AI:
        if top >= 3:
            return Verdict("likely", "很可能是 AI 生成或经过 AI 合成，见下方疑点")
        if top >= 1:
            return Verdict("suspicious", "有 AI 生成的迹象，建议进一步核实")
        if not ai_models_ran:
            return Verdict("unknown", "元数据里没有 AI 标识；AI 识别（云端模型）未运行，不能排除 AI 生成")
        return Verdict("none", "没有发现 AI 生成的迹象（不等于一定是真实录制）")
    if not hits:
        return Verdict("none", "没有发现剪辑痕迹（重新编码导出的剪辑可能检测不到）")
    if top >= 3:
        return Verdict("likely", "有明显的剪辑痕迹，见下方疑点位置")
    corr = corroborated(hits)
    if corr:
        return Verdict("likely", f"同一位置有 {len(corr)} 类证据互相印证（{_names(corr)}），剪辑痕迹明显，见下方疑点位置")
    kinds = {_signal(f) for f in hits}
    why = "单一类型的痕迹也可能是录制设备造成" if len(kinds) == 1 else "这几类痕迹不在同一位置，单独看都可能是录制设备造成"
    return Verdict("suspicious", f"有可疑的剪辑痕迹（{_names(kinds)}），{why}，建议对照疑点位置回放核实")
