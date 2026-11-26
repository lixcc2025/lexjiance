"""一次识别：按检测项逐个跑，一个出错不影响其他；返回 {"detectors": [...], "findings": [...]}（docs/云端接口.md）。"""
from __future__ import annotations

import logging
import time
from typing import Optional

import numpy as np
from PIL import Image

from .detectors import audio as audio_det
from .detectors import video as video_det
from .detectors.base import Finding, Status, dump
from .models.registry import Registry

log = logging.getLogger("avserver")


def run(registry: Registry, audio: Optional[tuple[np.ndarray, int]], frames: list[tuple[float, Image.Image]], duration: float) -> dict:
    statuses: list[Status] = []
    findings: list[Finding] = []
    for name in registry.all_detectors():
        st = Status(name)
        model = registry.get(name)
        t0 = time.monotonic()
        needs_audio = name in ("ai_voice", "watermark")
        if model is None:
            st.skipped = "服务器上没有安装这个模型"
        elif needs_audio and audio is None:
            st.skipped = "没有声音"
        elif not needs_audio and not frames:
            st.skipped = "没有画面"
        else:
            try:
                got = audio_det.detect(name, model, *audio) if needs_audio else video_det.detect(model, frames, duration)
                findings.extend(got)
            except Exception as e:  # 一个检测项出错不影响其他
                log.exception("检测项 %s 出错", name)
                st.ok, st.error = False, f"识别出错：{type(e).__name__}"
        st.seconds = round(time.monotonic() - t0, 3)
        statuses.append(st)
    return {"detectors": [dump(s) for s in statuses], "findings": [dump(f) for f in findings]}
