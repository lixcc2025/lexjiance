"""跑一个文件：读结构 → 逐个检测项 → 汇总结论。"""
from __future__ import annotations

import os
import time
from typing import Callable, Optional

from .detectors import ALL, Skip
from .models import AI, EDIT, DetectorStatus, Finding, Result
from .verdict import RANK, verdict
from .media.probe import probe

# 事件回调：kind 是 progress / finding / detector，payload 是 dict
Emit = Callable[[str, dict], None]

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

    findings.sort(key=lambda f: (-RANK[f.severity], f.start if f.start is not None else -1))
    # 本机引擎不跑 AI 模型；AI 识别在云端，桌面端合并结果后重算结论
    result = Result(file=path, media=media.summary(), ai=verdict(findings, AI), edit=verdict(findings, EDIT),
                    findings=findings, detectors=statuses)
    emit("progress", {"pct": 1.0, "stage": "完成"})
    return result
