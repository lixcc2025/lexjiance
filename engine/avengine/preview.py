"""时间轴要用的预览素材：视频缩略帧、声音波形、频谱图。都交给 ffmpeg 流式处理，长文件也不占多少内存。
和检测用同一条画面、同一条声音（问题清单 P0-3）。

  python -m avengine preview <文件> --out <目录>     打印一个 JSON：时长、波形数组、频谱图路径、缩略帧列表
"""
from __future__ import annotations

import os
from typing import Any, Optional

import numpy as np

from .media.decode import DecodeError, pcm_blocks
from .media.ffrun import FFError, map_args, run
from .media.outdir import prepare
from .media.probe import probe

WAVE_BINS = 1800        # 波形分多少段（界面再按宽度合并）
WAVE_RATE = 8000        # 算波形时先降到 8kHz 单声道
SPEC_SIZE = "1800x256"  # 频谱图：宽是时间，高是频率
SPEC_RATE = 16000       # 频谱只看到 8kHz（人声主要在这个范围），图更清楚
FRAMES = 24             # 缩略帧数量
OURS = r"spectrogram\.png|frame_\d{2}\.jpg|preview\.json"


def waveform(path: str, duration: float, stream_index: Optional[int] = None) -> list[float]:
    """每段的峰值（0~1，做了轻微压缩让小声也看得见）"""
    per = max(1, int(duration * WAVE_RATE) // WAVE_BINS)
    peaks: list[np.ndarray] = []
    carry = np.zeros(0, dtype=np.int16)
    for block in pcm_blocks(path, WAVE_RATE, stream_index):
        data = np.concatenate((carry, block)) if len(carry) else block
        n = len(data) // per
        if n:
            peaks.append(np.abs(data[: n * per].reshape(n, per).astype(np.int32)).max(axis=1))
        carry = data[n * per:]
    if len(carry):
        peaks.append(np.array([np.abs(carry.astype(np.int32)).max()]))
    if not peaks:
        return []
    p = np.concatenate(peaks).astype(np.float64)
    m = p.max()
    if not m:
        return []
    return [round(float(x), 3) for x in (p / m) ** 0.7]


def spectrogram(path: str, out: str, stream_index: Optional[int] = None) -> Optional[str]:
    src = f"[0:{stream_index}]" if stream_index is not None else "[0:a:0]"
    try:
        run(["-y", "-i", path, "-filter_complex",
             f"{src}aresample={SPEC_RATE},showspectrumpic=s={SPEC_SIZE}:legend=0:color=magma:scale=log:fscale=lin:mode=combined",
             "-frames:v", "1", out], timeout=600)
    except FFError:
        return None
    return out if os.path.isfile(out) else None


def frames(path: str, duration: float, outdir: str, stream_index: Optional[int] = None) -> list[dict[str, Any]]:
    got = []
    for i in range(FRAMES):
        t = duration * (i + 0.5) / FRAMES
        f = os.path.join(outdir, f"frame_{i:02d}.jpg")
        # -ss 放在 -i 前面：按关键帧快速跳，不从头解码
        try:
            run(["-y", "-ss", f"{t:.3f}", "-i", path, *map_args(stream_index), "-frames:v", "1", "-vf", "scale=240:-2", "-q:v", "5", f], timeout=30)
        except FFError:
            continue
        if os.path.isfile(f):
            got.append({"t": round(t, 3), "path": f})
    return got


def make_preview(path: str, outdir: str) -> dict[str, Any]:
    prepare(outdir, OURS)
    media = probe(path)
    dur = media.duration or 0.0
    a, v = media.target_audio, media.target_video
    res: dict[str, Any] = {"duration": dur, "waveform": [], "spectrogram": None, "frames": []}
    if a and dur > 0:
        try:
            res["waveform"] = waveform(path, dur, a.index)
        except DecodeError:
            res["waveform"] = []
        res["spectrogram"] = spectrogram(path, os.path.join(outdir, "spectrogram.png"), a.index)
    if v and dur > 0:
        res["frames"] = frames(path, dur, outdir, v.index)
    return res
