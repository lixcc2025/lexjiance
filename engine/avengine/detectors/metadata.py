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
    "stable diffusion": "Stable Diffusion", "comfyui": "ComfyUI",
}
# 「AIGC」不在这里按字样匹配：只认国标隐式标识（键名精确匹配或内嵌结构，见 _find_aigc_label）

# 人工填写的字段：谁都能随手写，提到工具名不等于用了这个工具 → 最多「轻微」，并展示原文
HUMAN_KEYS = {
    "title", "comment", "description", "synopsis", "artist", "album", "album_artist", "author", "composer",
    "copyright", "genre", "keywords", "lyrics", "subtitle", "grouping", "show", "network", "performer",
    "publisher", "purl", "episode_id", "language",
}
# 否定语境：「与可灵无关」「not aigc」之类
NEGATION = re.compile(r"(不是|并非|无关|没有|不含|未使用|未经|并未|非\S{0,3}(生成|合成)|\bnot\b|\bno\b|isn'?t|without|never)", re.I)

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


def _field(key: str) -> str:
    """「stream1:handler_name」→「handler_name」；苹果的「com.apple.quicktime.title」→「title」"""
    f = key.split(":", 1)[-1].lower()
    return f.rsplit(".", 1)[-1] if f.startswith("com.apple.quicktime.") else f


def is_human_field(key: str) -> bool:
    f = _field(key)
    return f in HUMAN_KEYS or f.startswith("comment") or f.startswith("description") or f.startswith("title")


def _match(text: str, markers: dict[str, str]) -> list[str]:
    """英文名：短名（≤4 个字母，如 veo、luma）两边都要是单词边界，「luma」不会命中「illuminate」；
    长名只要求开头是边界，「KlingAI」「JimengAI」这种连写也能命中。中文名按字样匹配"""
    low = text.lower()
    hits = []
    for key, name in markers.items():
        if key.isascii():
            tail = "(?![a-z0-9])" if len(key) <= 4 else ""
            if re.search(rf"(?<![a-z0-9]){re.escape(key)}{tail}", low):
                hits.append(name)
        elif key in low:
            hits.append(name)
    return sorted(set(hits))


def _hits(tags: dict[str, str], markers: dict[str, str]) -> tuple[dict[str, str], dict[str, str], list[str], list[str]]:
    """按「谁写的」分开：机器写入的字段命中、人工字段命中（排除否定语境）；返回 (机器字段, 人工字段, 机器工具名, 人工工具名)"""
    machine, human, mn, hn = {}, {}, set(), set()
    for k, v in tags.items():
        names = _match(v, markers)
        if not names:
            continue
        if is_human_field(k):
            if NEGATION.search(v):
                continue
            human[k] = v
            hn.update(names)
        else:
            machine[k] = v
            mn.update(names)
    return machine, human, sorted(mn), sorted(hn)


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

        # 2. 标签里的 AI 工具名：机器写入的字段（编码器、软件、处理器名等）才算强信号
        m_fields, h_fields, m_tools, h_tools = _hits(tags, AI_TOOL_MARKERS)
        tools = m_tools or h_tools
        if m_fields:
            out.append(Finding(self.name, AI, "high", "元数据里出现 AI 生成工具：" + "、".join(m_tools),
                               "这些名字写在编码器、软件、处理器名这类由程序自动写入的字段里，生成工具导出文件时通常会留下。"
                               "元数据可以被修改，结合其他检测结果判断。",
                               evidence={f"字段 {k}": v[:300] for k, v in m_fields.items()}))
        if h_fields:
            out.append(Finding(self.name, AI, "low", "标题、注释等人工填写的字段里提到：" + "、".join(h_tools),
                               "这些字段谁都可以随手填写，提到工具名不等于用了这个工具。下面是原文，请结合内容自己判断。",
                               evidence={f"字段 {k}": v[:300] for k, v in h_fields.items()}))

        # 3. C2PA 内容凭证（只判断有无）
        if b"c2pa" in blob or b"jumbf" in blob:
            out.append(Finding(self.name, SOURCE, "medium", "文件带有 C2PA 内容凭证",
                               "内容凭证记录了文件的来源和编辑历史，AI 生成工具（OpenAI、Google、Adobe 等）会写入。"
                               "需要解析凭证内容才能确定来源（后续版本支持）。",
                               evidence={}))

        progress(0.7, "检查设备和软件信息")
        # 4. 编辑 / 转码软件
        # 只看机器写入的字段：标题里写「用剪映剪的」不算软件痕迹
        e_fields, _, editors, _ = _hits(tags, EDITOR_MARKERS)
        if editors:
            ffmpeg_only = set(editors) == {"FFmpeg"}
            out.append(Finding(self.name, EDIT if not ffmpeg_only else SOURCE, "low" if not ffmpeg_only else "info",
                               "文件经过软件处理：" + "、".join(editors),
                               "出现剪辑软件说明文件被导出过。注意：微信、QQ 等聊天软件和很多平台传输时会用 FFmpeg 重新编码，"
                               "这本身不是篡改，但会抹掉部分原始痕迹。" if not ffmpeg_only else
                               "文件由 FFmpeg 封装或转码过，聊天软件、平台、转换工具都会这样做，本身不算疑点。",
                               evidence={f"字段 {k}": v[:300] for k, v in e_fields.items()}))

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
