"""跑 ONNX 模型（ONNX Runtime）。有 NVIDIA 显卡且装了 onnxruntime-gpu 时用 CUDA，否则用 CPU。"""
from __future__ import annotations

import threading

import numpy as np
import onnxruntime as ort

from .spec import ModelSpec


def providers(device: str) -> list[str]:
    avail = ort.get_available_providers()
    if device in ("auto", "cuda") and "CUDAExecutionProvider" in avail:
        return ["CUDAExecutionProvider", "CPUExecutionProvider"]
    if device == "cuda":
        raise RuntimeError("要求用 CUDA，但 ONNX Runtime 没有 CUDA 支持（装 onnxruntime-gpu，并确认驱动）")
    return ["CPUExecutionProvider"]


class Model:
    def __init__(self, spec: ModelSpec, device: str = "auto", threads: int = 0):
        self.spec = spec
        opts = ort.SessionOptions()
        if threads > 0:
            opts.intra_op_num_threads = threads
        opts.log_severity_level = 3
        self.session = ort.InferenceSession(spec.path, sess_options=opts, providers=providers(device))
        self.input_name = self.session.get_inputs()[0].name
        self.device = self.session.get_providers()[0]
        self._lock = threading.Lock()   # 同一个会话串行用，避免显存翻倍

    def scores(self, batch: np.ndarray) -> np.ndarray:
        """一批输入 → 每个样本「是 AI 生成 / 有水印」的概率（0~1）"""
        out: list[np.ndarray] = []
        n = self.spec.batch
        for i in range(0, len(batch), n):
            with self._lock:
                y = self.session.run(None, {self.input_name: batch[i:i + n]})[0]
            out.append(to_prob(np.asarray(y, dtype=np.float64), self.spec.output_type, self.spec.fake_index))
        return np.concatenate(out) if out else np.zeros(0)


def to_prob(y: np.ndarray, kind: str, fake_index: int) -> np.ndarray:
    y = y.reshape(len(y), -1)
    if kind == "logits2":
        z = y - y.max(axis=1, keepdims=True)
        e = np.exp(z)
        return e[:, fake_index] / e.sum(axis=1)
    if kind == "logit":
        return 1 / (1 + np.exp(-y[:, 0]))
    return np.clip(y[:, 0], 0, 1)
