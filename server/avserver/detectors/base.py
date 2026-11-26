"""检测项的状态和结果，格式和桌面端约定一致（docs/云端接口.md）。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

TITLES = {"ai_voice": ("AI 合成语音", "声音克隆、语音合成"), "ai_video": ("AI 生成画面", "文生视频、换脸"), "watermark": ("隐形水印", "AudioSeal 等 AI 水印")}


@dataclass
class Status:
    name: str
    ok: bool = True
    skipped: str = ""
    error: str = ""
    seconds: float = 0.0
    title: str = ""
    desc: str = ""

    def __post_init__(self):
        self.title, self.desc = self.title or TITLES[self.name][0], self.desc or TITLES[self.name][1]


@dataclass
class Finding:
    detector: str
    category: str
    severity: str
    title: str
    detail: str = ""
    modality: str = "file"
    start: Optional[float] = None
    end: Optional[float] = None
    evidence: dict[str, Any] = field(default_factory=dict)
    signal: str = ""


def dump(x) -> dict:
    return asdict(x)
