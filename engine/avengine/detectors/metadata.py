"""文件元数据：AI 生成标识、AI 工具标签、内容凭证（C2PA）、编辑软件和拍摄设备信息。

依据：
- 《人工智能生成合成内容标识办法》（2025-09-01 施行）和配套国家标准 GB 45438-2025 要求 AI 生成的音视频
  在文件元数据里写「隐式标识」。合规的国内生成工具（即梦、可灵、海螺等）导出的文件应带这个标识。
  TODO：按标准原文核对字段名和 JSON 结构（现在按 "AIGC" 键 + Label / ContentProducer 等字段识别）
- C2PA 内容凭证：OpenAI、Google、Adobe 等会在生成内容里嵌入。这里只判断有没有，解析签名和内容
  后续接 c2pa-python（Apache-2.0）
- 元数据可以被删除或伪造：查到是强信号，查不到不能说明不是 AI 生成。
"""
from __future__ import annotations

import json
import re

from ..models import AI, EDIT, SOURCE, Finding
from ..media.probe import MediaInfo
from .base import Detector, Progress

# 元数据里出现这些字样，说明文件经过 / 来自这些 AI 工具（全部小写比较）
AI_TOOL_MARKERS = {
    "sora": "Sora", "openai": "OpenAI", "veo": "Google Veo", "runway": "Runway", "pika": "Pika",
    "luma": "Luma", "kling": "可灵 Kling", "可灵": "可灵 Kling", "jimeng": "即梦", "即梦": "即梦",
    "hailuo": "海螺 Hailuo", "海螺": "海螺 Hailuo", "minimax": "MiniMax", "vidu": "Vidu", "pixverse": "PixVerse",
    "elevenlabs": "ElevenLabs", "suno": "Suno", "udio": "Udio", "fish audio": "Fish Audio",
    "tongyi": "通义", "通义": "通义", "doubao": "豆包", "豆包": "豆包", "seedance": "Seedance",
    "stable diffusion": "Stable Diffusion", "comfyui": "ComfyUI", "aigc": "AIGC 标记",
}
# 只当单词匹配的（太短，容易误中别的词）
_WORD_ONLY = {"veo", "pika", "luma", "udio", "suno", "sora"}

# 编辑 / 转码软件
EDITOR_MARKERS = {
    "premiere": "Adobe Premiere", "after effects": "Adobe After Effects", "audition": "Adobe Audition",
    "final cut": "Final Cut Pro", "davinci": "DaVinci Resolve", "capcut": "剪映 CapCut", "jianying": "剪映",
    "剪映": "剪映", "快剪辑": "快剪辑", "camtasia": "Camtasia", "audacity": "Audacity", "handbrake": "HandBrake",
    "imovie": "iMovie", "lavf": "FFmpeg", "lavc": "FFmpeg", "ffmpeg": "FFmpeg",
}
# 拍摄 / 录音设备留下的字段
DEVICE_KEYS = ("com.apple.quicktime.make", "com.apple.quicktime.model", "make", "model",
               "com.android.manufacturer", "com.android.model", "com.apple.quicktime.software")

# 隐式标识里的字段（TODO：按 GB 45438-2025 原文核对字段名和含义）
AIGC_FIELDS = {
    "Label": "生成合成标签", "ContentProducer": "生成合成服务提供者", "ProduceID": "内容制作编号",
    "ContentPropagator": "传播服务提供者", "PropagateID": "内容传播编号",
    "ReservedCode1": "预留字段 1", "ReservedCode2": "预留字段 2",
}

SCAN_BYTES = 4 * 1024 * 1024   # 文件头尾各扫 4MB 找内嵌标识（MP4 的 moov 可能在尾部）


def _all_tags(media: MediaInfo) -> dict[str, str]:
    tags = {f"format:{k}": v for k, v in media.format_tags.items()}
    for s in media.streams:
        for k, v in s.tags.items():
            tags[f"stream{s.index}:{k}"] = v
    return tags


def _match(text: str, markers: dict[str, str]) -> list[str]:
    low = text.lower()
    hits = []
    for key, name in markers.items():
        if key in _WORD_ONLY:
            if re.search(rf"(?<![a-z]){re.escape(key)}(?![a-z])", low):
                hits.append(name)
        elif key in low:
            hits.append(name)
    return sorted(set(hits))


def _read_head_tail(path: str, size: int) -> bytes:
    with open(path, "rb") as f:
        head = f.read(SCAN_BYTES)
        if size <= SCAN_BYTES * 2:
            return head + f.read()
        f.seek(size - SCAN_BYTES)
        return head + f.read()


def _find_aigc_label(tags: dict[str, str], blob: bytes) -> tuple[str, str] | None:
    """隐式标识：先看 ffprobe 读到的标签，再在原始字节里找 "AIGC" 后面跟的 JSON"""
    for k, v in tags.items():
        if k.split(":", 1)[-1].lower() == "aigc":
            return k, v
    m = re.search(rb"AIGC.{0,16}?(\{[^{}]{0,2000}\})", blob, re.S)
    if m:
        try:
            body = m.group(1).decode("utf-8")
            json.loads(body)
            return "文件内嵌", body
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
    return None


class MetadataDetector(Detector):
    name = "metadata"
    title = "文件元数据"
    desc = "AI 生成标识、内容凭证、编辑软件、拍摄设备"

    def run(self, media: MediaInfo, progress: Progress) -> list[Finding]:
        out: list[Finding] = []
        tags = _all_tags(media)
        tag_text = "\n".join(f"{k}={v}" for k, v in tags.items())
        progress(0.3, "读取元数据")
        blob = _read_head_tail(media.path, media.size)

        # 1. 国标隐式标识
        label = _find_aigc_label(tags, blob)
        if label:
            where, value = label
            ev: dict = {"位置": where}
            try:
                fields = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                fields = None
            if isinstance(fields, dict):
                for k, v in fields.items():
                    if v in ("", None):
                        continue
                    ev[AIGC_FIELDS.get(k, k)] = v
            else:
                ev["内容"] = value[:500]
            out.append(Finding(self.name, AI, "high", "文件带有 AI 生成内容的隐式标识",
                               "按《人工智能生成合成内容标识办法》，AI 生成的音视频要在元数据里写入隐式标识。"
                               "这个文件里有这类标识，说明它很可能由 AI 生成或经过 AI 合成。",
                               evidence=ev))

        # 2. 标签里的 AI 工具名
        tools = _match(tag_text, AI_TOOL_MARKERS)
        if label:
            tools = [t for t in tools if t != "AIGC 标记"]
        if tools:
            out.append(Finding(self.name, AI, "medium" if tools == ["AIGC 标记"] else "high",
                               "元数据里出现 AI 生成工具：" + "、".join(tools),
                               "生成工具通常会在导出文件的编码器、软件、注释等字段留下名字。",
                               evidence={k: v for k, v in tags.items() if _match(f"{k}={v}", AI_TOOL_MARKERS)}))

        # 3. C2PA 内容凭证（只判断有无）
        if b"c2pa" in blob or b"jumbf" in blob:
            out.append(Finding(self.name, SOURCE, "medium", "文件带有 C2PA 内容凭证",
                               "内容凭证记录了文件的来源和编辑历史，AI 生成工具（OpenAI、Google、Adobe 等）会写入。"
                               "需要解析凭证内容才能确定来源（后续版本支持）。",
                               evidence={}))

        progress(0.7, "检查设备和软件信息")
        # 4. 编辑 / 转码软件
        editors = _match(tag_text, EDITOR_MARKERS)
        if editors:
            ffmpeg_only = set(editors) == {"FFmpeg"}
            out.append(Finding(self.name, EDIT if not ffmpeg_only else SOURCE, "low" if not ffmpeg_only else "info",
                               "文件经过软件处理：" + "、".join(editors),
                               "出现剪辑软件说明文件被导出过。注意：微信、QQ 等聊天软件和很多平台传输时会用 FFmpeg 重新编码，"
                               "这本身不是篡改，但会抹掉部分原始痕迹。" if not ffmpeg_only else
                               "文件由 FFmpeg 封装或转码过，聊天软件、平台、转换工具都会这样做，本身不算疑点。",
                               evidence={k: v for k, v in tags.items() if _match(f"{k}={v}", EDITOR_MARKERS)}))

        # 5. 拍摄设备
        dev = {k: v for k, v in tags.items() if k.split(":", 1)[-1].lower() in DEVICE_KEYS}
        if dev:
            out.append(Finding(self.name, SOURCE, "info", "有拍摄 / 录音设备信息",
                               "元数据里记录了设备型号，原始拍摄文件通常会有。设备信息也可以被伪造，只作参考。",
                               evidence=dev))
        elif media.video and not editors and not label and not tools:
            out.append(Finding(self.name, SOURCE, "info", "没有拍摄设备信息",
                               "手机、相机直接拍的文件一般会记录设备型号。没有设备信息常见于转发、转码过的文件，不能单独作为疑点。"))

        ct = {k: v for k, v in tags.items() if k.split(":", 1)[-1].lower() in ("creation_time", "com.apple.quicktime.creationdate", "date")}
        if ct:
            out.append(Finding(self.name, SOURCE, "info", "文件记录的创建时间", "可与案情中的录制时间对照。", evidence=ct))
        return out
