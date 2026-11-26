"""给云端 AI 识别准备上传素材：不传原文件，只传识别要用的部分，上传快、交出去的内容也少。
和检测用同一条画面、同一条声音（问题清单 P0-3）。

- 声音：16kHz 单声道 FLAC（无损，语音识别模型的常用输入）
- 画面：每秒一帧，最多 MAX_FRAMES 张（长视频均匀抽），长边缩到 512，JPEG

  python -m avengine extract <文件> --out <目录>     打印清单 JSON
"""
from __future__ import annotations

import os
from typing import Any

from .media.ffrun import FFError, map_args, run
from .media.outdir import prepare
from .media.probe import probe

AUDIO_RATE = 16000
MAX_FRAMES = 120
FRAME_EDGE = 512
ONE_PASS_SECONDS = 600   # 10 分钟以内的视频解码一遍抽完；更长的逐张跳着抽，免得整段解码
OURS = r"audio\.flac|f\d{4}\.jpg"


def _frames_one_pass(path: str, stream_index: int, dur: float, n: int, scale: str, outdir: str) -> list[dict[str, Any]]:
    """短视频：解码一遍、按固定间隔出 n 张（第 i 张在 (i + 0.5) × 时长 / n 秒）。比每张单独起一次 ffmpeg 快很多"""
    step = dur / n
    try:
        run(["-y", "-ss", f"{step / 2:.3f}", "-i", path, *map_args(stream_index), "-vf", f"fps=1/{step:.6f},{scale}",
             "-frames:v", str(n), "-q:v", "3", os.path.join(outdir, "f%04d.jpg")], timeout=1800)
    except FFError:
        return []
    got = []
    for i in range(n):
        # ffmpeg 的 %04d 从 1 开始编号；改成从 0 开始，和逐张抽的命名一致
        src, dst = os.path.join(outdir, f"f{i + 1:04d}.jpg"), os.path.join(outdir, f"f{i:04d}.jpg")
        if not os.path.isfile(src):
            break
        os.replace(src, dst)
        got.append({"t": round(step * (i + 0.5), 3), "file": dst})
    return got


def extract(path: str, outdir: str, max_frames: int = MAX_FRAMES) -> dict[str, Any]:
    prepare(outdir, OURS)
    media = probe(path)
    dur = media.duration or 0.0
    a, v = media.target_audio, media.target_video
    out: dict[str, Any] = {"duration": dur, "audio": None, "sample_rate": AUDIO_RATE, "frames": [],
                           "audio_stream": a.index if a else None, "video_stream": v.index if v else None}
    if a:
        f = os.path.join(outdir, "audio.flac")
        run(["-y", "-i", path, *map_args(a.index), "-vn", "-ac", "1", "-ar", str(AUDIO_RATE), "-c:a", "flac", f], timeout=1800)
        out["audio"] = f
    if v and dur > 0:
        n = max(1, min(max_frames, int(dur)))
        scale = f"scale='if(gt(iw,ih),{FRAME_EDGE},-2)':'if(gt(iw,ih),-2,{FRAME_EDGE})'"
        if dur <= ONE_PASS_SECONDS:
            out["frames"] = _frames_one_pass(path, v.index, dur, n, scale, outdir)
            if out["frames"]:
                return out
        for i in range(n):
            t = dur * (i + 0.5) / n
            f = os.path.join(outdir, f"f{i:04d}.jpg")
            try:
                run(["-y", "-ss", f"{t:.3f}", "-i", path, *map_args(v.index), "-frames:v", "1", "-vf", scale, "-q:v", "3", f], timeout=60)
            except FFError:
                continue
            if os.path.isfile(f):
                out["frames"].append({"t": round(t, 3), "file": f})
    return out
