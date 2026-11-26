"""画面类检测：AI 生成画面（ai_video）。逐帧打分，相邻高分帧合并成可疑时间段。"""
from __future__ import annotations

import numpy as np
from PIL import Image

from ..models.runtime import Model
from .base import Finding
from .segments import segments, smooth


def preprocess(im: Image.Image, spec_input: dict) -> np.ndarray:
    w, h = spec_input["size"][1], spec_input["size"][0]   # size 是 [高, 宽]
    if spec_input.get("resize", "center_crop") == "center_crop":
        s = max(w / im.width, h / im.height)
        im = im.resize((max(w, round(im.width * s)), max(h, round(im.height * s))), Image.BILINEAR)
        l, t = (im.width - w) // 2, (im.height - h) // 2
        im = im.crop((l, t, l + w, t + h))
    else:
        im = im.resize((w, h), Image.BILINEAR)
    a = np.asarray(im, dtype=np.float32) / float(spec_input.get("scale", 255))
    mean = np.array(spec_input.get("mean", [0, 0, 0]), dtype=np.float32)
    std = np.array(spec_input.get("std", [1, 1, 1]), dtype=np.float32)
    a = (a - mean) / std
    return a.transpose(2, 0, 1) if spec_input.get("layout", "NCHW") == "NCHW" else a


def detect(model: Model, frames: list[tuple[float, Image.Image]], duration: float) -> list[Finding]:
    if not frames:
        return []
    spec = model.spec
    frames = sorted(frames, key=lambda f: f[0])
    batch = np.stack([preprocess(im, spec.input) for _, im in frames]).astype(np.float32)
    sc = smooth(model.scores(batch), 3)
    ts = np.array([t for t, _ in frames])
    gap = float(np.median(np.diff(ts))) if len(ts) > 1 else max(duration, 1.0)
    out: list[Finding] = []
    for seg in segments(ts - gap / 2, ts + gap / 2, sc, spec.medium, duration):
        sev = "high" if seg.peak >= spec.high else "medium"
        out.append(Finding("ai_video", "ai", sev, f"这段画面疑似 AI 生成（分数 {seg.peak:.2f}）",
                           "AI 画面识别模型认为这些帧有生成或换脸的特征。分数是模型给出的可能性，不是鉴定结论；压缩、缩放、翻拍会影响准确度。",
                           "video", round(seg.start, 2), round(seg.end, 2),
                           {"最高分": round(seg.peak, 3), "平均分": round(seg.mean, 3), "帧数": seg.count, "模型": spec.label,
                            "阈值（可疑 / 高度可疑）": f"{spec.medium} / {spec.high}"}, signal="ai_video"))
    if not out:
        out.append(Finding("ai_video", "source", "info", f"画面没有发现 AI 生成迹象（最高分 {float(sc.max()):.2f}）",
                           "AI 画面识别模型没有发现生成特征。模型对没见过的新生成工具可能认不出，不等于一定是真实拍摄。", "video",
                           evidence={"最高分": round(float(sc.max()), 3), "帧数": len(frames), "模型": spec.label}, signal="ai_video"))
    return out
