"""服务配置：全部来自环境变量，部署时在 docker-compose.yml 或系统服务里设置。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass
class Config:
    models_dir: str = field(default_factory=lambda: os.environ.get("AVS_MODELS_DIR", "models"))
    tokens_file: str = field(default_factory=lambda: os.environ.get("AVS_TOKENS_FILE", "tokens.txt"))
    # 只在本机开发 / 测试时用：不校验令牌
    allow_no_auth: bool = field(default_factory=lambda: os.environ.get("AVS_ALLOW_NO_AUTH") == "1")
    work_dir: str = field(default_factory=lambda: os.environ.get("AVS_WORK_DIR", ""))
    max_upload_mb: int = field(default_factory=lambda: _int("AVS_MAX_UPLOAD_MB", 300))
    max_frames: int = field(default_factory=lambda: _int("AVS_MAX_FRAMES", 200))
    max_audio_seconds: int = field(default_factory=lambda: _int("AVS_MAX_AUDIO_SECONDS", 4 * 3600))
    max_concurrent: int = field(default_factory=lambda: _int("AVS_MAX_CONCURRENT", 2))   # 同时识别几个请求（显存 / CPU 有限）
    queue_wait: int = field(default_factory=lambda: _int("AVS_QUEUE_WAIT", 120))         # 排队最多等几秒，超了回 503
    device: str = field(default_factory=lambda: os.environ.get("AVS_DEVICE", "auto"))    # auto / cpu / cuda
    threads: int = field(default_factory=lambda: _int("AVS_THREADS", 0))                 # CPU 推理线程数，0 = 自动
