"""调 ffprobe 读文件结构，并确定「分析哪一条画面、哪一条声音」。

多音轨文件（解说轨、多语言轨）：所有检测项、预览、上传素材都用同一条目标流（问题清单 P0-3）。
选法：标了 default 的优先，其次是流序号最小的；画面排除封面图（attached_pic）。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, NamedTuple, Optional

from .ffrun import FFError, run, stream
from .tools import ToolMissing


class ProbeError(RuntimeError):
    pass


def run_ffprobe(args: list[str], timeout: float = 120) -> dict[str, Any]:
    try:
        out = run(["-of", "json", *args], timeout=timeout, probe=True)
    except (FFError, ToolMissing) as e:
        raise ProbeError(str(e)) from e
    try:
        return json.loads(out.decode("utf-8", "replace") or "{}")
    except json.JSONDecodeError as e:
        raise ProbeError("ffprobe 输出解析失败") from e


def _f(v: Any) -> Optional[float]:
    try:
        x = float(v)
        return x if x == x else None   # 去掉 nan
    except (TypeError, ValueError):
        return None


def _i(v: Any) -> Optional[int]:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None   # ffprobe 会给 "N/A"


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

    @property
    def is_default(self) -> bool:
        return bool((self.raw.get("disposition") or {}).get("default"))


def _pick(streams: list[Stream]) -> Optional[Stream]:
    if not streams:
        return None
    return next((s for s in streams if s.is_default), streams[0])


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
        return [s for s in self.streams if s.kind == "video" and not (s.raw.get("disposition") or {}).get("attached_pic")]

    @property
    def audio(self) -> list[Stream]:
        return [s for s in self.streams if s.kind == "audio"]

    @property
    def target_video(self) -> Optional[Stream]:
        return _pick(self.video)

    @property
    def target_audio(self) -> Optional[Stream]:
        return _pick(self.audio)

    def summary(self) -> dict[str, Any]:
        """给桌面端展示的基本信息（和检测用的是同一条流）"""
        v = self.target_video.raw if self.target_video else {}
        a = self.target_audio.raw if self.target_audio else {}
        return {
            # ffprobe 的封装名是一串（mov,mp4,m4a,...），给人看用扩展名
            "format": (os.path.splitext(self.path)[1].lstrip(".").upper() or self.format_name) if "," in self.format_name else self.format_name,
            "duration": self.duration,
            "size": self.size,
            "video": {
                "codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"),
                "fps": v.get("avg_frame_rate"), "stream": v.get("index"),
            } if v else None,
            "audio": {
                "codec": a.get("codec_name"), "sample_rate": _f(a.get("sample_rate")), "channels": a.get("channels"),
                "stream": a.get("index"), "tracks": len(self.audio),
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
        streams.append(Stream(index=_i(s.get("index")) or 0, kind=kind, codec=str(s.get("codec_name", "")),
                              raw=s, duration=_f(s.get("duration"))))
    if not any(s.kind in ("video", "audio") for s in streams):
        raise ProbeError("文件里没有音频或视频")
    return MediaInfo(
        path=path,
        format_name=str(fmt.get("format_name", "")),
        duration=_f(fmt.get("duration")),
        size=_i(fmt.get("size")) or os.path.getsize(path),
        format_tags={str(k): str(v) for k, v in (fmt.get("tags") or {}).items()},
        streams=streams,
        raw=d,
    )


class Packet(NamedTuple):
    pts: Optional[float]
    duration: Optional[float]
    key: bool


def packets(path: str, stream_index: int) -> list[Packet]:
    """一个流的所有包（时间戳、时长、是否关键帧）。不解码；逐行流式读，几小时的录像也不会一次占几百 MB"""
    out: list[Packet] = []
    try:
        with stream(["-select_streams", str(stream_index), "-show_entries", "packet=pts_time,duration_time,flags",
                     "-of", "compact=p=0", "-show_packets", path], probe=True) as f:
            for raw in iter(f.readline, b""):
                kv = dict(x.split("=", 1) for x in raw.decode("utf-8", "replace").strip().split("|") if "=" in x)
                out.append(Packet(_f(kv.get("pts_time")), _f(kv.get("duration_time")), "K" in kv.get("flags", "")))
    except (FFError, ToolMissing) as e:
        raise ProbeError(str(e)) from e
    return out

