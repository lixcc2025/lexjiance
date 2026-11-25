"""检测项登记表（本机、不用模型的检测）。新加检测项：写一个 Detector 子类，加进 ALL。顺序就是执行和展示顺序。

AI 模型类的检测（合成语音、AI 画面、水印）在云端服务器上跑，由桌面端的 cloud 模块负责，不在这里。
"""
from .base import Detector, Skip
from .metadata import MetadataDetector
from .structure import StructureDetector
from .audio_splice import AudioSpliceDetector

ALL: list[type[Detector]] = [
    MetadataDetector,
    StructureDetector,
    AudioSpliceDetector,
]

__all__ = ["ALL", "Detector", "Skip"]
