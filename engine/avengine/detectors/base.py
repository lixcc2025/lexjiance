"""检测项的统一接口。

每个检测项是一个 Detector 子类：声明名字、适用的媒体类型，run() 返回疑点列表。
不适用（比如纯音频文件跑视频检测）或缺条件（模型没装）时抛 Skip，引擎记下原因、不算失败。
"""
from __future__ import annotations

from typing import Callable

from ..models import Finding
from ..probe import MediaInfo

Progress = Callable[[float, str], None]   # (0~1, 说明)


class Skip(Exception):
    """这个检测项这次不跑，参数是给人看的原因"""


class Detector:
    name: str = ""
    title: str = ""
    # 适用于哪种文件：video / audio / any
    needs: str = "any"
    # 是否依赖 AI 模型（模型没装时在界面上提示「未安装」，而不是「未发现」）
    uses_model: bool = False

    def applicable(self, media: MediaInfo) -> str:
        """返回空串表示适用，否则返回不适用的原因"""
        if self.needs == "video" and not media.video:
            return "没有视频画面"
        if self.needs == "audio" and not media.audio:
            return "没有音频"
        return ""

    def run(self, media: MediaInfo, progress: Progress) -> list[Finding]:
        raise NotImplementedError
