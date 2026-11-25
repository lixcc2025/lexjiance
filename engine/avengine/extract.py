"""给云端 AI 识别准备上传素材：不传原文件，只传识别要用的部分，上传快、交出去的内容也少。

- 声音：16kHz 单声道 FLAC（无损，语音识别模型的常用输入）
- 画面：每秒一帧，最多 MAX_FRAMES 张（长视频均匀抽），长边缩到 512，JPEG

  python -m avengine extract <文件> --out <目录>     打印清单 JSON
"""
from __future__ import annotations

import os
import subprocess
from typing import Any

from .media.probe import probe
from .media.tools import ffmpeg_bin, popen_kwargs

AUDIO_RATE = 16000
MAX_FRAMES = 120
FRAME_EDGE = 512


def _ff(args: list[str], timeout: float = 600) -> bool:
    r = subprocess.run([ffmpeg_bin(), "-v", "error", "-nostdin", "-y", *args], capture_output=True, timeout=timeout, **popen_kwargs())
    return r.returncode == 0


def extract(path: str, outdir: str, max_frames: int = MAX_FRAMES) -> dict[str, Any]:
    os.makedirs(outdir, exist_ok=True)
    media = probe(path)
    dur = media.duration or 0.0
    out: dict[str, Any] = {"duration": dur, "audio": None, "sample_rate": AUDIO_RATE, "frames": []}
    if media.audio:
        a = os.path.join(outdir, "audio.flac")
        if _ff(["-i", path, "-vn", "-ac", "1", "-ar", str(AUDIO_RATE), "-c:a", "flac", a]):
            out["audio"] = a
    if media.video and dur > 0:
        n = max(1, min(max_frames, int(dur)))
        scale = f"scale='if(gt(iw,ih),{FRAME_EDGE},-2)':'if(gt(iw,ih),-2,{FRAME_EDGE})'"
        for i in range(n):
            t = dur * (i + 0.5) / n
            f = os.path.join(outdir, f"f{i:04d}.jpg")
            if _ff(["-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", scale, "-q:v", "3", f], timeout=60):
                out["frames"].append({"t": round(t, 3), "file": f})
    return out
