"""声音特征：流式算，长录音也不占多少内存。

- 每 20 毫秒一帧：响度（dBFS）
- 每 1 秒一窗：底噪（这一秒里最安静的那些帧的响度）、有声部分的频带上限（频谱在哪个频率以上基本没有能量）
- 数字静音：样本值连续为 0 的片段（真实录音总有底噪，不会出现完全为 0 的样本）
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..media.decode import DecodeError, pcm_blocks

RATE = 32000          # 分析用采样率：能看到 16kHz 以内的频带
FRAME = 640           # 20ms
NFFT = 1024
WIN_FRAMES = 50       # 1 秒 = 50 帧
SILENCE_DB = -90.0    # 低于这个算没有声音
ZERO_MIN = int(0.05 * RATE)   # 连续 0 至少 50 毫秒才算数字静音


@dataclass
class AudioFeatures:
    duration: float
    frame_db: np.ndarray                    # 每帧响度
    win_floor: np.ndarray                   # 每秒底噪（dBFS）
    win_cutoff: np.ndarray                  # 每秒有声部分的频带上限（Hz，没有足够有声帧时为 nan）
    zero_runs: list[tuple[float, float]] = field(default_factory=list)  # 数字静音片段（秒）

    @property
    def windows(self) -> int:
        return len(self.win_floor)


def _cutoff_hz(power: np.ndarray) -> float:
    """平均功率谱 → 频带上限：参考人声主频段（300~3000Hz）的电平，往高频找最后一个还在「参考电平 - 50dB」以上的频率"""
    freqs = np.fft.rfftfreq(NFFT, 1 / RATE)
    db = 10 * np.log10(power + 1e-20)
    # 按 250Hz 一段取平均，去掉单个频点的毛刺
    edges = np.arange(0, RATE / 2 + 250, 250)
    idx = np.digitize(freqs, edges) - 1
    bands = np.array([db[idx == i].mean() if np.any(idx == i) else -200 for i in range(len(edges) - 1)])
    ref = bands[(edges[:-1] >= 300) & (edges[:-1] < 3000)].mean()
    above = np.where(bands > ref - 50)[0]
    return float(edges[above[-1] + 1]) if len(above) else float("nan")


def extract(path: str, stream_index: int | None = None) -> AudioFeatures:
    frame_db: list[np.ndarray] = []
    win_floor: list[float] = []
    win_cutoff: list[float] = []
    zero_runs: list[tuple[float, float]] = []
    window = np.hanning(FRAME).astype(np.float32)

    carry = np.zeros(0, dtype=np.int16)        # 没凑满一帧的尾巴
    pending_frames: list[np.ndarray] = []      # 没凑满一秒的帧（样本）
    pending_db: list[float] = []
    run_start = None                           # 跨块延续的连续 0 起点（样本序号）
    total = 0

    def flush_window(frames: list[np.ndarray], dbs: list[float]) -> None:
        d = np.array(dbs)
        floor = float(np.percentile(d, 10))
        win_floor.append(floor)
        active = [f for f, x in zip(frames, dbs) if x > max(floor + 10, -60)]
        if len(active) >= 5:
            spec = np.abs(np.fft.rfft(np.stack(active).astype(np.float32) * window, NFFT)) ** 2
            win_cutoff.append(_cutoff_hz(spec.mean(axis=0)))
        else:
            win_cutoff.append(float("nan"))

    for block in pcm_blocks(path, RATE, stream_index):
        # 数字静音：找连续为 0 的片段。run_start 记着跨块延续的片段起点
        z = (block == 0).astype(np.int8)
        d = np.diff(np.concatenate((np.array([1 if run_start is not None else 0], dtype=np.int8), z)))
        for i in np.flatnonzero(d):
            if d[i] == 1:
                run_start = total + int(i)
            else:
                if run_start is not None and total + i - run_start >= ZERO_MIN:
                    zero_runs.append((run_start / RATE, (total + int(i)) / RATE))
                run_start = None
        data = np.concatenate((carry, block)) if len(carry) else block
        n = len(data) // FRAME
        frames = data[: n * FRAME].reshape(n, FRAME)
        carry = data[n * FRAME:].copy()
        rms = np.sqrt(np.mean(frames.astype(np.float64) ** 2, axis=1))
        dbs = 20 * np.log10(np.maximum(rms, 1e-3) / 32768.0)
        frame_db.append(dbs)
        for f, d in zip(frames, dbs):
            pending_frames.append(f)
            pending_db.append(float(d))
            if len(pending_frames) == WIN_FRAMES:
                flush_window(pending_frames, pending_db)
                pending_frames, pending_db = [], []
        total += len(block)
    if run_start is not None and total - run_start >= ZERO_MIN:
        zero_runs.append((run_start / RATE, total / RATE))
    if len(pending_frames) >= WIN_FRAMES // 2:
        flush_window(pending_frames, pending_db)

    if total == 0:
        # ffprobe 说有声音，ffmpeg 却一个样本也解不出来：是解码失败，不是「声音太短」
        raise DecodeError("声音解码失败：没有解出任何样本（文件可能损坏，或编码不受支持）")
    return AudioFeatures(
        duration=total / RATE,
        frame_db=np.concatenate(frame_db) if frame_db else np.zeros(0),
        win_floor=np.array(win_floor),
        win_cutoff=np.array(win_cutoff),
        zero_runs=zero_runs,
    )
