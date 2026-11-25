"""还没实现的检测项。先占位，界面上显示「未启用」和原因，接口定好后逐个替换成真实现。

候选做法和开源项目见 docs/开源调研.md。
"""
from __future__ import annotations

from ..models import Finding
from ..probe import MediaInfo
from .base import Detector, Progress, Skip


class AiVoiceDetector(Detector):
    name = "ai_voice"
    title = "AI 合成语音（声音克隆、TTS）"
    needs = "audio"
    uses_model = True

    def run(self, media: MediaInfo, progress: Progress) -> list[Finding]:
        # 计划：自监督语音模型 + 分类头，按 4 秒一段打分，输出可疑时间段。ONNX Runtime 跑 CPU
        raise Skip("模型未安装")


class AiVideoDetector(Detector):
    name = "ai_video"
    title = "AI 生成画面（文生视频、换脸）"
    needs = "video"
    uses_model = True

    def run(self, media: MediaInfo, progress: Progress) -> list[Finding]:
        # 计划：抽帧（人脸区域 + 整帧）分别打分，换脸和整段生成两类模型
        raise Skip("模型未安装")


class AudioSpliceDetector(Detector):
    name = "audio_splice"
    title = "声音剪辑痕迹（底噪突变、电网频率断续、数字静音）"
    needs = "audio"

    def run(self, media: MediaInfo, progress: Progress) -> list[Finding]:
        # 计划：不用模型。分段算底噪、频谱，找突变点；提取 50Hz 电网频率看是否连续；找整段全零的数字静音
        raise Skip("下一步实现")


class WatermarkDetector(Detector):
    name = "watermark"
    title = "隐形水印（AudioSeal 等）"
    uses_model = True

    def run(self, media: MediaInfo, progress: Progress) -> list[Finding]:
        raise Skip("下一步实现")
