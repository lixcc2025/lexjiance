"""声音类检测：AI 合成语音（ai_voice）、隐形水印（watermark）。按窗口滑动打分，连续高分的窗口合并成可疑时间段。"""
from __future__ import annotations

import numpy as np

from ..models.runtime import Model
from .base import Finding
from .segments import segments, smooth, windows

TEXT = {
    "ai_voice": ("这一段声音疑似 AI 合成", "AI 语音识别模型认为这段声音有合成或克隆的特征。分数是模型给出的可能性，不是鉴定结论；翻录、压缩、噪声会影响准确度。",
                 "声音没有发现 AI 合成迹象", "AI 语音识别模型没有发现合成特征。模型对没见过的新合成工具可能认不出，不等于一定是真人录音。"),
    "watermark": ("这一段声音检测到 AI 水印", "检测到 AI 语音生成工具嵌入的隐形水印，说明这段声音由带水印的生成工具产生。",
                  "没有检测到 AI 水印", "只能检测加了这类水印的生成工具；没有水印不说明不是 AI 生成。"),
}


def _normalize(x: np.ndarray, how: str) -> np.ndarray:
    if how == "peak":
        m = np.abs(x).max()
        return x / m if m > 0 else x
    if how == "zscore":
        s = x.std()
        return (x - x.mean()) / s if s > 0 else x - x.mean()
    return x


def resample(x: np.ndarray, sr: int, target: int) -> np.ndarray:
    """简单线性插值重采样（客户端按约定发 16k，这里只是兜底）"""
    if sr == target or len(x) == 0:
        return x
    n = int(round(len(x) * target / sr))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def detect(detector: str, model: Model, audio: np.ndarray, sr: int) -> list[Finding]:
    spec = model.spec
    rate = int(spec.input["sample_rate"])
    x = resample(audio, sr, rate)
    duration = len(x) / rate
    if duration < 0.5:
        return []
    wins = windows(len(x), rate, float(spec.input["window"]), float(spec.input["hop"]))
    wlen = max(e - s for s, e in wins)
    batch = np.zeros((len(wins), wlen), dtype=np.float32)
    for i, (s, e) in enumerate(wins):
        batch[i, : e - s] = _normalize(x[s:e], spec.input.get("normalize", "none"))
    raw = model.scores(batch)
    sc = smooth(raw, 3)
    starts = np.array([s / rate for s, _ in wins])
    ends = np.array([e / rate for _, e in wins])
    title, detail, none_title, none_detail = TEXT[detector]
    out: list[Finding] = []
    for seg in segments(starts, ends, sc, spec.medium, duration):
        sev = "high" if seg.peak >= spec.high else "medium"
        out.append(Finding(detector, "ai", sev, f"{title}（分数 {seg.peak:.2f}）", detail, "audio", round(seg.start, 2), round(seg.end, 2),
                           {"最高分": round(seg.peak, 3), "平均分": round(seg.mean, 3), "窗口数": seg.count, "模型": spec.label,
                            "阈值（可疑 / 高度可疑）": f"{spec.medium} / {spec.high}"}, signal=detector))
    if not out:
        out.append(Finding(detector, "source", "info", f"{none_title}（最高分 {float(sc.max()):.2f}）", none_detail, "audio",
                           evidence={"最高分": round(float(sc.max()), 3), "窗口数": len(wins), "模型": spec.label}, signal=detector))
    return out
