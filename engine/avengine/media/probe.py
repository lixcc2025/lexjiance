"""调 ffprobe 读文件结构。ffmpeg / ffprobe 打包时随软件带，开发时用系统的。"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import Any, Optional

from .tools import ToolMissing, ffprobe_bin, popen_kwargs


class ProbeError(RuntimeError):
    pass


def run_ffprobe(args: list[str], timeout: float = 120) -> dict[str, Any]:
    try:
        cmd = [ffprobe_bin(), "-v", "error", "-of", "json", *args]
    except ToolMissing as e:
        raise ProbeError(str(e)) from e
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False, **popen_kwargs())
    except subprocess.TimeoutExpired as e:
        raise ProbeError("ffprobe 超时") from e
    if out.returncode != 0:
        raise ProbeError(out.stderr.decode("utf-8", "replace").strip()[:500] or "ffprobe 失败")
    try:
        return json.loads(out.stdout.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError as e:
        raise ProbeError("ffprobe 输出解析失败") from e


def _f(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@dataclass
class Stream:
    index: int
    kind: str                     # video / audio / other
    codec: str
    raw: dict[str, Any]
    duration: Optional[float] = None

    @property
    def tags(self) -> dict[str, str]:
        return {str(k): str(v) for k, v in (self.raw.get("tags") or {}).items()}


@dataclass
class MediaInfo:
    path: str
    format_name: str
    duration: Optional[float]
    size: int
    format_tags: dict[str, str]
    streams: list[Stream] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def video(self) -> list[Stream]:
        return [s for s in self.streams if s.kind == "video" and not s.raw.get("disposition", {}).get("attached_pic")]

    @property
    def audio(self) -> list[Stream]:
        return [s for s in self.streams if s.kind == "audio"]

    def summary(self) -> dict[str, Any]:
        """给桌面端展示的基本信息"""
        v = self.video[0].raw if self.video else {}
        a = self.audio[0].raw if self.audio else {}
        return {
            # ffprobe 的封装名是一串（mov,mp4,m4a,...），给人看用扩展名
            "format": (os.path.splitext(self.path)[1].lstrip(".").upper() or self.format_name) if "," in self.format_name else self.format_name,
            "duration": self.duration,
            "size": self.size,
            "video": {
                "codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"),
                "fps": v.get("avg_frame_rate"),
            } if v else None,
            "audio": {
                "codec": a.get("codec_name"), "sample_rate": _f(a.get("sample_rate")), "channels": a.get("channels"),
            } if a else None,
        }


def probe(path: str) -> MediaInfo:
    if not os.path.isfile(path):
        raise ProbeError(f"文件不存在：{path}")
    d = run_ffprobe(["-show_format", "-show_streams", path])
    fmt = d.get("format") or {}
    streams = []
    for s in d.get("streams") or []:
        kind = s.get("codec_type") if s.get("codec_type") in ("video", "audio") else "other"
        streams.append(Stream(index=int(s.get("index", 0)), kind=kind, codec=str(s.get("codec_name", "")),
                              raw=s, duration=_f(s.get("duration"))))
    if not streams:
        raise ProbeError("文件里没有音频或视频")
    return MediaInfo(
        path=path,
        format_name=str(fmt.get("format_name", "")),
        duration=_f(fmt.get("duration")),
        size=int(fmt.get("size") or os.path.getsize(path)),
        format_tags={str(k): str(v) for k, v in (fmt.get("tags") or {}).items()},
        streams=streams,
        raw=d,
    )


def packets(path: str, stream_index: int) -> list[dict[str, Any]]:
    """一个流的所有包（时间戳、是否关键帧、大小）。不解码，长视频也快"""
    d = run_ffprobe(["-select_streams", str(stream_index), "-show_entries",
                     "packet=pts_time,dts_time,duration_time,flags,size", "-show_packets", path], timeout=300)
    return d.get("packets") or []
