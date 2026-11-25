"""时间轴要用的预览素材：视频缩略帧、声音波形、频谱图。都交给 ffmpeg 流式处理，长文件也不占多少内存。

  python -m avengine preview <文件> --out <目录>     打印一个 JSON：时长、波形数组、频谱图路径、缩略帧列表
"""
from __future__ import annotations

import array
import os
import subprocess
from typing import Any, Optional

from .media.probe import probe
from .media.tools import ffmpeg_bin, popen_kwargs

WAVE_BINS = 1800        # 波形分多少段（界面再按宽度合并）
WAVE_RATE = 8000        # 算波形时先降到 8kHz 单声道
SPEC_SIZE = "1800x256"  # 频谱图：宽是时间，高是频率
SPEC_RATE = 16000       # 频谱只看到 8kHz（人声主要在这个范围），图更清楚
FRAMES = 24             # 缩略帧数量


def _run(args: list[str], timeout: float = 300) -> subprocess.CompletedProcess:
    return subprocess.run([ffmpeg_bin(), "-v", "error", "-nostdin", "-y", *args], capture_output=True, timeout=timeout, **popen_kwargs())


def waveform(path: str, duration: float) -> list[float]:
    """每段的峰值（0~1，做了轻微压缩让小声也看得见）"""
    total = max(1, int(duration * WAVE_RATE))
    per = max(1, total // WAVE_BINS)
    proc = subprocess.Popen([ffmpeg_bin(), "-v", "error", "-nostdin", "-i", path, "-vn", "-ac", "1", "-ar", str(WAVE_RATE),
                             "-f", "s16le", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **popen_kwargs())
    peaks: list[int] = []
    buf = array.array("h")
    assert proc.stdout
    while True:
        chunk = proc.stdout.read(1 << 18)
        if not chunk:
            break
        if len(chunk) % 2:
            chunk = chunk[:-1]
        buf.frombytes(chunk)
        # 凑够整段就算：切片取最大最小值在 C 里做，比逐个样本快几十倍
        whole = (len(buf) // per) * per
        for i in range(0, whole, per):
            seg = buf[i:i + per]
            peaks.append(max(max(seg), -min(seg)))
        del buf[:whole]
    if len(buf):
        peaks.append(max(max(buf), -min(buf)))
    proc.wait()
    m = max(peaks) if peaks else 0
    if not m:
        return []
    return [round((p / m) ** 0.7, 3) for p in peaks]


def spectrogram(path: str, out: str) -> Optional[str]:
    r = _run(["-i", path, "-vn", "-lavfi", f"aresample={SPEC_RATE},showspectrumpic=s={SPEC_SIZE}:legend=0:color=magma:scale=log:fscale=lin:mode=combined",
              "-frames:v", "1", out])
    return out if r.returncode == 0 and os.path.isfile(out) else None


def frames(path: str, duration: float, outdir: str) -> list[dict[str, Any]]:
    got = []
    for i in range(FRAMES):
        t = duration * (i + 0.5) / FRAMES
        f = os.path.join(outdir, f"frame_{i:02d}.jpg")
        # -ss 放在 -i 前面：按关键帧快速跳，不从头解码
        r = _run(["-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", "scale=240:-2", "-q:v", "5", f], timeout=30)
        if r.returncode == 0 and os.path.isfile(f):
            got.append({"t": round(t, 3), "path": f})
    return got


def make_preview(path: str, outdir: str) -> dict[str, Any]:
    os.makedirs(outdir, exist_ok=True)
    media = probe(path)
    dur = media.duration or 0.0
    res: dict[str, Any] = {"duration": dur, "waveform": [], "spectrogram": None, "frames": []}
    if media.audio and dur > 0:
        res["waveform"] = waveform(path, dur)
        res["spectrogram"] = spectrogram(path, os.path.join(outdir, "spectrogram.png"))
    if media.video and dur > 0:
        res["frames"] = frames(path, dur, outdir)
    return res
