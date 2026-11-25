"""找 ffmpeg / ffprobe。

顺序：环境变量 AVENGINE_FFMPEG / AVENGINE_FFPROBE（桌面端打包后指向自带的那份）→ 系统 PATH。
"""
from __future__ import annotations

import os
import shutil


class ToolMissing(RuntimeError):
    pass


def _find(env: str, name: str) -> str:
    p = os.environ.get(env)
    if p and os.path.isfile(p):
        return p
    p = shutil.which(name)
    if not p:
        raise ToolMissing(f"找不到 {name}")
    return p


def ffmpeg_bin() -> str:
    return _find("AVENGINE_FFMPEG", "ffmpeg")


def ffprobe_bin() -> str:
    return _find("AVENGINE_FFPROBE", "ffprobe")


# Windows 下子进程不弹黑框
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


def popen_kwargs() -> dict:
    return {"creationflags": CREATE_NO_WINDOW} if os.name == "nt" else {}
