"""声音剪辑痕迹（不用模型）。

1. 数字静音：真实录音总有底噪，样本不会连续为 0。录音中间出现一段「绝对安静」，常见于删掉一段后补静音、
   或把别处的声音拼进来。注意：微信、电话等通话软件的静音压缩也会产生，所以大量出现时只作提示。
2. 底噪突变：同一次录音的背景噪声大致稳定。前后几秒底噪差了好几个分贝且各自稳定，说明前后可能不是同一段录音。
3. 频带突变：不同设备、不同编码的录音，高频截止的位置不一样（比如 16kHz 和 4kHz）。中途变了，说明可能拼接了别的来源。

只看声音本身；剪辑后整体重新加噪、重新编码的，这些方法可能查不出。
"""
from __future__ import annotations

import numpy as np

from ..dsp.features import SILENCE_DB, AudioFeatures, extract
from ..models import EDIT, SOURCE, Finding
from ..media.probe import MediaInfo
from .base import Detector, Progress, Skip

SIDE = 4                 # 突变点前后各取几秒比较
FLOOR_STEP_DB = 6.0      # 底噪差多少分贝算突变
FLOOR_STABLE_DB = 2.5    # 每一边底噪的波动要小于这个，才算「各自稳定」
CUTOFF_STEP_HZ = 1500.0  # 频带上限差多少算突变
CUTOFF_STABLE_HZ = 600.0
ZERO_EDGE = 0.3          # 开头结尾这么近的静音不算（录音软件常在两头补 0）
ZERO_MANY = 8            # 超过这么多段，按「通话软件静音压缩」处理


def _steps(series: np.ndarray, step: float, stable: float, valid) -> list[tuple[int, float, float]]:
    """找突变点：返回 [(秒序号, 前面中位数, 后面中位数)]，相邻的只留变化最大的那个"""
    out: list[tuple[int, float, float]] = []
    n = len(series)
    for t in range(SIDE, n - SIDE + 1):
        a, b = series[t - SIDE:t], series[t:t + SIDE]
        if not (valid(a) and valid(b)):
            continue
        if np.nanstd(a) > stable or np.nanstd(b) > stable:
            continue
        ma, mb = float(np.nanmedian(a)), float(np.nanmedian(b))
        if abs(mb - ma) >= step:
            if out and t - out[-1][0] <= SIDE:
                if abs(mb - ma) > abs(out[-1][2] - out[-1][1]):
                    out[-1] = (t, ma, mb)
            else:
                out.append((t, ma, mb))
    return out


class AudioSpliceDetector(Detector):
    name = "audio_splice"
    title = "声音剪辑痕迹"
    desc = "数字静音、底噪突变、频带突变"
    needs = "audio"

    def run(self, media: MediaInfo, progress: Progress) -> list[Finding]:
        progress(0.05, "解码声音")
        f: AudioFeatures = extract(media.path)
        if f.duration < 1:
            raise Skip("声音太短")
        progress(0.7, "分析底噪和频带")
        out: list[Finding] = []
        out += self._zeros(f)
        out += self._floor(f)
        out += self._cutoff(f)
        if not out:
            out.append(Finding(self.name, SOURCE, "info", "声音里没有发现拼接痕迹",
                               "没有数字静音、底噪突变或频带突变。整体重新加噪、重新编码的剪辑可能查不出来。", modality="audio"))
        return out

    def _zeros(self, f: AudioFeatures) -> list[Finding]:
        runs = [(a, b) for a, b in f.zero_runs if a > ZERO_EDGE and b < f.duration - ZERO_EDGE]
        if not runs:
            return []
        if len(runs) > ZERO_MANY:
            total = sum(b - a for a, b in runs)
            return [Finding(self.name, EDIT, "low", f"有 {len(runs)} 段数字静音（共 {total:.1f} 秒）",
                            "样本值完全为 0 的片段很多，更像是通话软件（微信、电话等）的静音压缩，单独不能说明被剪辑。"
                            "如果录音声称是手机直接录的，就值得注意。",
                            modality="audio", evidence={"前几段（秒）": ", ".join(f"{a:.2f}–{b:.2f}" for a, b in runs[:6])})]
        return [Finding(self.name, EDIT, "medium", f"这里有 {b - a:.2f} 秒「绝对安静」的数字静音",
                        "真实录音总有背景底噪，样本不会连续为 0。录音中间出现一段完全为 0 的静音，常见于删掉一段后补静音或拼接；"
                        "通话软件的静音压缩也可能产生。",
                        modality="audio", start=round(a, 3), end=round(b, 3), evidence={"长度（秒）": round(b - a, 3)})
                for a, b in runs]

    def _floor(self, f: AudioFeatures) -> list[Finding]:
        valid = lambda x: np.all(x > SILENCE_DB)
        out = []
        for t, a, b in _steps(f.win_floor, FLOOR_STEP_DB, FLOOR_STABLE_DB, valid):
            d = b - a
            out.append(Finding(self.name, EDIT, "medium" if abs(d) >= 9 else "low",
                               f"背景底噪在这里{'变大' if d > 0 else '变小'}了 {abs(d):.1f} 分贝",
                               f"前 {SIDE} 秒底噪约 {a:.0f} dBFS，后 {SIDE} 秒约 {b:.0f} dBFS，两边各自很稳定，中间突然跳变。"
                               "同一次录音的背景噪声一般是连续的，跳变常见于两段录音拼接；也可能是录音环境突然变化（开关空调、换房间）。",
                               modality="audio", start=float(t), end=float(t),
                               evidence={"之前底噪（dBFS）": round(a, 1), "之后底噪（dBFS）": round(b, 1)}))
        return out

    def _cutoff(self, f: AudioFeatures) -> list[Finding]:
        valid = lambda x: np.count_nonzero(~np.isnan(x)) >= SIDE - 1
        out = []
        for t, a, b in _steps(f.win_cutoff, CUTOFF_STEP_HZ, CUTOFF_STABLE_HZ, valid):
            out.append(Finding(self.name, EDIT, "medium", f"声音的频带在这里从 {a / 1000:.1f}kHz 变成 {b / 1000:.1f}kHz",
                               "不同设备、不同编码的录音，高频截止的位置不一样。同一段录音中途变了，说明前后可能来自不同的录音或经过不同的处理，"
                               "常见于拼接了别的来源的声音。",
                               modality="audio", start=float(t), end=float(t),
                               evidence={"之前频带上限（Hz）": round(a), "之后频带上限（Hz）": round(b)}))
        return out
