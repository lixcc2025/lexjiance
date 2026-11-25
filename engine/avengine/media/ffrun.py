"""调 ffmpeg / ffprobe 的唯一入口（问题清单 P1-2）。

以前 decode、preview、extract、probe 各自拼命令，超时、-nostdin、stderr、选流有的有有的没有。现在统一在这里：
- 总是 -nostdin -v error；stderr 收下来，失败时把最后几行附在错误里（不再「静默失败」）
- run()：一次性命令，带超时，超时就杀掉
- stream()：流式读 stdout（解码 PCM、读包），带「多久没有新数据就杀掉」的看门狗和总时长上限；
  不管正常结束、出错还是调用方中途不读了，都会 kill + wait，不留孤儿进程
"""
from __future__ import annotations

import subprocess
import threading
import time
from contextlib import contextmanager
from typing import IO, Iterator, Optional

from .tools import ffmpeg_bin, ffprobe_bin, popen_kwargs

IDLE_TIMEOUT = 60.0       # 流式读取时，多少秒没有新数据就认为卡死
TOTAL_TIMEOUT = 4 * 3600  # 单个流式命令最长（4 小时，足够解几小时的录像）


class FFError(RuntimeError):
    """ffmpeg / ffprobe 失败；消息里带 stderr 的最后几行"""


def _tail(b: bytes, n: int = 600) -> str:
    return b.decode("utf-8", "replace").strip()[-n:]


def run(args: list[str], timeout: float = 300, probe: bool = False) -> bytes:
    """跑一次 ffmpeg（probe=True 时是 ffprobe），返回 stdout；失败或超时抛 FFError"""
    cmd = [ffprobe_bin(), "-v", "error", *args] if probe else [ffmpeg_bin(), "-v", "error", "-nostdin", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False, **popen_kwargs())
    except subprocess.TimeoutExpired as e:
        raise FFError(f"{'ffprobe' if probe else 'ffmpeg'} 超时（{timeout:.0f} 秒）") from e
    if r.returncode != 0:
        raise FFError(_tail(r.stderr) or f"{'ffprobe' if probe else 'ffmpeg'} 失败（退出码 {r.returncode}）")
    return r.stdout


class _Watched:
    """包一层 stdout：每次读到数据都记一下时间，看门狗据此判断是否卡死"""

    def __init__(self, f: IO[bytes]):
        self.f = f
        self.last = time.monotonic()

    def read(self, n: int = -1) -> bytes:
        b = self.f.read(n)
        self.last = time.monotonic()
        return b

    def readline(self) -> bytes:
        b = self.f.readline()
        self.last = time.monotonic()
        return b


@contextmanager
def stream(args: list[str], probe: bool = False, idle: float = IDLE_TIMEOUT, total: float = TOTAL_TIMEOUT) -> Iterator[_Watched]:
    """流式读 stdout。用法：
        with stream([...]) as out:
            while chunk := out.read(65536): ...
    退出 with 时检查退出码，非 0 抛 FFError（带 stderr）。"""
    cmd = [ffprobe_bin(), "-v", "error", *args] if probe else [ffmpeg_bin(), "-v", "error", "-nostdin", *args]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **popen_kwargs())
    assert proc.stdout and proc.stderr
    err = bytearray()
    killed: list[str] = []

    def drain_stderr() -> None:
        for line in iter(proc.stderr.readline, b""):
            err.extend(line)
            if len(err) > 16000:
                del err[:-8000]

    out = _Watched(proc.stdout)
    t0 = time.monotonic()

    def watchdog() -> None:
        while proc.poll() is None:
            now = time.monotonic()
            if now - out.last > idle:
                killed.append(f"{idle:.0f} 秒没有输出，可能卡住了")
            elif now - t0 > total:
                killed.append(f"超过 {total / 3600:.0f} 小时")
            if killed:
                proc.kill()
                return
            time.sleep(0.5)

    drainer = threading.Thread(target=drain_stderr, daemon=True)
    drainer.start()
    threading.Thread(target=watchdog, daemon=True).start()
    ok = False
    try:
        yield out
        ok = True
    finally:
        if not ok or killed:
            proc.kill()
        try:
            proc.stdout.close()
        except OSError:
            pass
        try:
            code = proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            code = proc.wait()
        drainer.join(timeout=5)
        try:
            proc.stderr.close()
        except OSError:
            pass
    name = "ffprobe" if probe else "ffmpeg"
    if killed:
        raise FFError(f"{name} 被终止：{killed[0]}")
    if code != 0:
        raise FFError(_tail(bytes(err)) or f"{name} 失败（退出码 {code}）")


def map_args(stream_index: Optional[int]) -> list[str]:
    """选定具体的流（问题清单 P0-3：不能让 ffmpeg 自己挑，否则和别的检测项分析的不是同一条）"""
    return ["-map", f"0:{stream_index}"] if stream_index is not None else []
