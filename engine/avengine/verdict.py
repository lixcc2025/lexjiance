"""两项结论的规则。桌面端合并云端 AI 识别结果后会按同样的规则重算（desktop/src/shared/verdict.ts），两边要一致。"""
from __future__ import annotations

from .models import AI, Finding, Verdict

RANK = {"info": 0, "low": 1, "medium": 2, "high": 3}


def verdict(findings: list[Finding], category: str, ai_models_ran: bool = False) -> Verdict:
    top = max((RANK[f.severity] for f in findings if f.category == category and f.severity != "info"), default=0)
    if category == AI:
        if top >= 3:
            return Verdict("likely", "很可能是 AI 生成或经过 AI 合成，见下方疑点")
        if top >= 1:
            return Verdict("suspicious", "有 AI 生成的迹象，建议进一步核实")
        if not ai_models_ran:
            return Verdict("unknown", "元数据里没有 AI 标识；AI 识别（云端模型）未运行，不能排除 AI 生成")
        return Verdict("none", "没有发现 AI 生成的迹象（不等于一定是真实录制）")
    if top >= 3:
        return Verdict("likely", "有明显的剪辑痕迹，见下方疑点位置")
    if top >= 1:
        return Verdict("suspicious", "有可疑的剪辑痕迹，建议对照疑点位置回放核实")
    return Verdict("none", "没有发现剪辑痕迹（重新编码导出的剪辑可能检测不到）")
