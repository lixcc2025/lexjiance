"""输出目录：只往里写自己认得的文件名，目录里有别的文件就拒绝，免得 -y 覆盖调用方的同名文件（问题清单次要问题）"""
from __future__ import annotations

import os
import re


class OutDirError(RuntimeError):
    pass


def prepare(outdir: str, ours: str) -> None:
    """ours：本命令会写的文件名（正则）。目录不存在就建；存在且有不认识的文件就报错"""
    os.makedirs(outdir, exist_ok=True)
    pat = re.compile(ours)
    foreign = [n for n in os.listdir(outdir) if not pat.fullmatch(n)]
    if foreign:
        raise OutDirError(f"输出目录里有其他文件，不往里写：{', '.join(foreign[:3])}")
