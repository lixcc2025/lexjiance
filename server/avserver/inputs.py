"""解析上传内容：meta（JSON）、audio（16kHz 单声道 FLAC）、frames（JPEG）。格式不对抛 InputError（回 400）。"""
from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import soundfile as sf
from PIL import Image

Image.MAX_IMAGE_PIXELS = 4096 * 4096   # 防解压炸弹：客户端发的是长边 512 的图


class InputError(ValueError):
    pass


@dataclass
class Meta:
    duration: float
    sample_rate: int
    has_audio: bool
    frames: list[tuple[float, str]] = field(default_factory=list)   # (时间, 文件名)
    client: dict = field(default_factory=dict)


def parse_meta(raw: str, max_frames: int) -> Meta:
    try:
        d = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as e:
        raise InputError("meta 不是合法的 JSON") from e
    if not isinstance(d, dict) or d.get("api") != "v1":
        raise InputError("meta 格式不对或 api 版本不是 v1")
    try:
        dur = float(d.get("duration") or 0)
        sr = int(d.get("sample_rate") or 16000)
    except (TypeError, ValueError) as e:
        raise InputError("duration / sample_rate 不是数字") from e
    if not (0 <= dur < 24 * 3600):
        raise InputError("duration 不合理")
    frames = []
    for f in (d.get("frames") or [])[: max_frames + 1]:
        try:
            frames.append((float(f["t"]), str(f["name"])))
        except (KeyError, TypeError, ValueError) as e:
            raise InputError("frames 里有格式不对的项") from e
    if len(frames) > max_frames:
        raise InputError(f"抽帧最多 {max_frames} 张")
    client = d.get("client") if isinstance(d.get("client"), dict) else {}
    return Meta(duration=dur, sample_rate=sr, has_audio=bool(d.get("has_audio")), frames=frames, client=client)


def load_audio(data: bytes, max_seconds: int) -> tuple[np.ndarray, int]:
    """→ (float32 单声道, 采样率)"""
    try:
        x, sr = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
    except Exception as e:  # soundfile 对坏文件抛各种异常
        raise InputError("音轨读不了（要 FLAC / WAV）") from e
    if len(x) > max_seconds * sr:
        raise InputError("音轨太长")
    return x.mean(axis=1), int(sr)


def load_image(data: bytes) -> Image.Image:
    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception as e:
        raise InputError("有抽帧图片读不了") from e
    return im.convert("RGB")
