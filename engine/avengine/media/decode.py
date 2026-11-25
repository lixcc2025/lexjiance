"""用 ffmpeg 把声音解成 PCM，按块流式给出（numpy int16 数组），长录音也不占多少内存。"""
from __future__ import annotations

import subprocess
from typing import Iterator

import numpy as np

from .tools import ffmpeg_bin, popen_kwargs


def pcm_blocks(path: str, rate: int, block_seconds: float = 30.0) -> Iterator[np.ndarray]:
    """单声道、指定采样率的 int16 样本，每块约 block_seconds 秒（最后一块可能更短）"""
    proc = subprocess.Popen(
        [ffmpeg_bin(), "-v", "error", "-nostdin", "-i", path, "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **popen_kwargs(),
    )
    assert proc.stdout
    want = int(rate * block_seconds) * 2
    buf = b""
    try:
        while True:
            chunk = proc.stdout.read(want - len(buf))
            if not chunk:
                break
            buf += chunk
            if len(buf) >= want:
                yield np.frombuffer(buf, dtype="<i2")
                buf = b""
        if len(buf) >= 2:
            yield np.frombuffer(buf[: len(buf) // 2 * 2], dtype="<i2")
    finally:
        proc.stdout.close()
        proc.wait()
