"""跑一个文件：读结构 → 逐个检测项 → 汇总结论。"""
from __future__ import annotations

import os
import time
from typing import Callable, Optional

from .detectors import ALL, Skip
from .models import AI, EDIT, DetectorStatus, Finding, Result, Verdict
from .probe import probe

# 事件回调：kind 是 progress / finding / detector，payload 是 dict
Emit = Callable[[str, dict], None]

_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3}


def _verdict(findings: list[Finding], category: str, statuses: list[DetectorStatus], model_names: set[str]) -> Verdict:
    hits = [f for f in findings if f.category == category and f.severity != "info"]
    top = max((_RANK[f.severity] for f in hits), default=0)
    if category == AI:
        models_ran = any(s.ok and not s.skipped for s in statuses if s.name in model_names)
        if top >= 3:
            return Verdict("likely", "很可能是 AI 生成或经过 AI 合成，见下方疑点")
        if top >= 1:
            return Verdict("suspicious", "有 AI 生成的迹象，建议进一步核实")
        if not models_ran:
            return Verdict("unknown", "元数据里没有 AI 标识；AI 识别模型未启用，不能排除 AI 生成")
        return Verdict("none", "没有发现 AI 生成的迹象（不等于一定是真实录制）")
    if top >= 3:
        return Verdict("likely", "有明显的剪辑痕迹，见下方疑点位置")
    if top >= 1:
        return Verdict("suspicious", "有可疑的剪辑痕迹，建议对照疑点位置回放核实")
    return Verdict("none", "没有发现剪辑痕迹（重新编码导出的剪辑可能检测不到）")


def analyze(path: str, emit: Optional[Emit] = None, only: Optional[list[str]] = None) -> Result:
    emit = emit or (lambda kind, payload: None)
    path = os.path.abspath(path)
    emit("progress", {"pct": 0.0, "stage": "读取文件结构"})
    media = probe(path)

    detectors = [cls() for cls in ALL if not only or cls.name in only]
    findings: list[Finding] = []
    statuses: list[DetectorStatus] = []
    n = len(detectors)
    for i, d in enumerate(detectors):
        base, span = 0.05 + 0.9 * i / n, 0.9 / n

        def progress(frac: float, stage: str, _base=base, _span=span, _d=d) -> None:
            emit("progress", {"pct": round(_base + _span * max(0.0, min(1.0, frac)), 3), "stage": f"{_d.title}：{stage}"})

        st = DetectorStatus(name=d.name, title=d.title, desc=d.desc, ok=True)
        t0 = time.monotonic()
        reason = d.applicable(media)
        if reason:
            st.skipped = reason
        else:
            progress(0.0, "开始")
            try:
                got = d.run(media, progress)
                for f in got:
                    findings.append(f)
                    emit("finding", f.to_dict())
            except Skip as e:
                st.skipped = str(e)
            except Exception as e:  # 一个检测项出错不影响其他项
                st.ok = False
                st.error = f"{type(e).__name__}: {e}"[:300]
        st.seconds = round(time.monotonic() - t0, 3)
        statuses.append(st)
        emit("detector", st.__dict__)

    model_names = {cls.name for cls in ALL if cls.uses_model}
    findings.sort(key=lambda f: (-_RANK[f.severity], f.start if f.start is not None else -1))
    result = Result(file=path, media=media.summary(), ai=_verdict(findings, AI, statuses, model_names),
                    edit=_verdict(findings, EDIT, statuses, model_names), findings=findings, detectors=statuses)
    emit("progress", {"pct": 1.0, "stage": "完成"})
    return result
