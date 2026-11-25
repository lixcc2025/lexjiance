"""用 ffmpeg 把声音解成 PCM，按块流式给出（numpy int16 数组），长录音也不占多少内存。

- 明确选流（-map），和其他检测项分析同一条声音（问题清单 P0-3）
- 解码失败（损坏、不支持的编码）抛 DecodeError，带 ffmpeg 的报错，不再被当成「声音太短」（问题清单 P1-4）
"""
from __future__ import annotations

from typing import Iterator, Optional

import numpy as np

from .ffrun import FFError, map_args, stream


class DecodeError(RuntimeError):
    pass


def pcm_blocks(path: str, rate: int, stream_index: Optional[int] = None, block_seconds: float = 30.0) -> Iterator[np.ndarray]:
    """单声道、指定采样率的 int16 样本，每块约 block_seconds 秒（最后一块可能更短）"""
    want = int(rate * block_seconds) * 2
    try:
        with stream(["-i", path, *map_args(stream_index), "-vn", "-ac", "1", "-ar", str(rate), "-f", "s16le", "-"]) as out:
            buf = b""
            while True:
                chunk = out.read(want - len(buf))
                if not chunk:
                    break
                buf += chunk
                if len(buf) >= want:
                    yield np.frombuffer(buf, dtype="<i2")
                    buf = b""
            if len(buf) >= 2:
                yield np.frombuffer(buf[: len(buf) // 2 * 2], dtype="<i2")
    except FFError as e:
        raise DecodeError(f"声音解码失败：{e}") from e
