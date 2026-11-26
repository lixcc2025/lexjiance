"""每个请求一个临时目录（只有服务进程能读），无论成功失败都删掉：上传的音轨和截图不留在服务器上。"""
from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def request_dir(base: str = "") -> Iterator[str]:
    d = tempfile.mkdtemp(prefix="avs-", dir=base or None)   # mkdtemp 本身就是 0700
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)
