"""检测结果的数据结构。引擎输出、桌面端展示都按这里的字段来。"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional

# 疑点类别
AI = "ai"            # AI 生成迹象
EDIT = "edit"        # 剪辑 / 篡改痕迹
SOURCE = "source"    # 来源信息（拍摄设备、编辑软件、转码等），本身不算疑点，帮助判断

# 严重程度：info 只是说明；low / medium / high 是疑点
SEVERITIES = ("info", "low", "medium", "high")


@dataclass
class Finding:
    detector: str                      # 哪个检测项发现的
    category: str                      # AI / EDIT / SOURCE
    severity: str                      # info / low / medium / high
    title: str                         # 一句话：发现了什么
    detail: str = ""                   # 为什么可疑、依据是什么
    modality: str = "file"             # file / video / audio
    start: Optional[float] = None      # 疑点位置（秒），没有位置的为空
    end: Optional[float] = None
    evidence: dict[str, Any] = field(default_factory=dict)  # 原始数据，方便复核
    signal: str = ""                   # 证据类型（如 ts_gap、noise_floor），结论用它判断不同证据是否互相印证

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DetectorStatus:
    name: str
    title: str
    ok: bool
    desc: str = ""
    skipped: str = ""      # 没跑的原因（比如没有视频流、模型没装）
    error: str = ""
    seconds: float = 0.0


@dataclass
class Verdict:
    level: str             # none / suspicious / likely / unknown
    text: str              # 给律师看的一句话
    score: Optional[float] = None


@dataclass
class Result:
    file: str
    media: dict[str, Any]
    ai: Verdict
    edit: Verdict
    findings: list[Finding]
    detectors: list[DetectorStatus]

    def to_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "media": self.media,
            "ai": asdict(self.ai),
            "edit": asdict(self.edit),
            "findings": [f.to_dict() for f in self.findings],
            "detectors": [asdict(d) for d in self.detectors],
        }
