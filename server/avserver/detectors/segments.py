"""逐窗 / 逐帧的分数 → 可疑时间段（纯函数，单元测试覆盖）。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Segment:
    start: float
    end: float
    peak: float     # 段内最高分
    mean: float     # 段内平均分
    count: int      # 段内窗口 / 帧数


def smooth(scores: np.ndarray, k: int = 3) -> np.ndarray:
    """滑动中值，去掉单个窗口 / 单帧的毛刺（k 为奇数）"""
    if len(scores) < k or k < 2:
        return scores.copy()
    pad = k // 2
    x = np.pad(scores, pad, mode="edge")
    return np.array([np.median(x[i:i + k]) for i in range(len(scores))])


def segments(starts: np.ndarray, ends: np.ndarray, scores: np.ndarray, threshold: float, duration: float) -> list[Segment]:
    """分数 ≥ threshold 的相邻窗口合并成一段；段的时间限制在 0 ~ duration"""
    out: list[Segment] = []
    i, n = 0, len(scores)
    while i < n:
        if scores[i] < threshold:
            i += 1
            continue
        j = i
        while j + 1 < n and scores[j + 1] >= threshold:
            j += 1
        s = scores[i:j + 1]
        lim = duration if duration > 0 else float(ends[j])
        out.append(Segment(max(0.0, float(starts[i])), min(lim, float(ends[j])), float(s.max()), float(s.mean()), j - i + 1))
        i = j + 1
    return out


def windows(n_samples: int, rate: int, window: float, hop: float) -> list[tuple[int, int]]:
    """切窗：[(起点样本, 终点样本)]。最后不满一窗的部分如果超过半窗，补一窗对齐到结尾"""
    w, h = int(round(window * rate)), max(1, int(round(hop * rate)))
    if n_samples <= w:
        return [(0, n_samples)]
    out = [(s, s + w) for s in range(0, n_samples - w + 1, h)]
    if n_samples - out[-1][1] > w // 2:
        out.append((n_samples - w, n_samples))
    return out
