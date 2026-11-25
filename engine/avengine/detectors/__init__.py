"""检测项登记表。新加检测项：写一个 Detector 子类，加进 ALL。顺序就是执行和展示顺序。"""
from .base import Detector, Skip
from .metadata import MetadataDetector
from .structure import StructureDetector
from .planned import AiVoiceDetector, AiVideoDetector, AudioSpliceDetector, WatermarkDetector

ALL: list[type[Detector]] = [
    MetadataDetector,
    StructureDetector,
    AudioSpliceDetector,
    WatermarkDetector,
    AiVoiceDetector,
    AiVideoDetector,
]

__all__ = ["ALL", "Detector", "Skip"]
