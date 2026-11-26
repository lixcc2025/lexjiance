"""模型说明文件 models/<目录>/model.json：一个模型怎么喂数据、输出怎么读、阈值多少。换模型只换文件，不改代码。

{
  "name": "voice-xlsr-zh",            模型名（界面和结果里显示）
  "version": "2026.12",
  "detector": "ai_voice",             给哪个检测项用：ai_voice / ai_video / watermark
  "file": "model.onnx",
  "license": "MIT（权重自训）",         许可证说明（商用前必须确认）
  "input": {
    // 声音类（ai_voice、watermark）：输入形状 [批, 采样点]
    "sample_rate": 16000, "window": 4.0, "hop": 2.0, "normalize": "none" | "peak" | "zscore",
    // 画面类（ai_video）：输入形状 [批, 3, 高, 宽]（NCHW）或 [批, 高, 宽, 3]（NHWC）
    "size": [224, 224], "resize": "center_crop" | "stretch", "mean": [..3], "std": [..3], "layout": "NCHW", "scale": 255
  },
  "output": { "type": "logits2" | "logit" | "prob", "fake_index": 1 },
     logits2：两类 logit（真 / 假），取 fake_index 那一类做 softmax；logit：一个 logit，过 sigmoid；prob：直接是概率
  "thresholds": { "medium": 0.5, "high": 0.85 },   分数 ≥ medium 记「可疑」，≥ high 记「高度可疑」（用评测工具在测试集上定）
  "batch": 16
}
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

DETECTORS = ("ai_voice", "ai_video", "watermark")
AUDIO_DETECTORS = ("ai_voice", "watermark")


class SpecError(ValueError):
    pass


@dataclass
class ModelSpec:
    name: str
    version: str
    detector: str
    path: str
    license: str
    input: dict[str, Any]
    output_type: str
    fake_index: int
    medium: float
    high: float
    batch: int = 16
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"{self.name} {self.version}".strip()


def load_spec(dir_: str) -> ModelSpec:
    p = os.path.join(dir_, "model.json")
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise SpecError(f"{p} 读不了：{e}") from e
    det = d.get("detector")
    if det not in DETECTORS:
        raise SpecError(f"{p}：detector 要是 {', '.join(DETECTORS)} 之一")
    path = os.path.join(dir_, d.get("file", "model.onnx"))
    if not os.path.isfile(path):
        raise SpecError(f"{p}：模型文件 {path} 不存在")
    inp = d.get("input") or {}
    if det in AUDIO_DETECTORS:
        for k in ("sample_rate", "window", "hop"):
            if not isinstance(inp.get(k), (int, float)) or inp[k] <= 0:
                raise SpecError(f"{p}：声音模型要有正数的 input.{k}")
    else:
        size = inp.get("size")
        if not (isinstance(size, list) and len(size) == 2 and all(isinstance(x, int) and x > 0 for x in size)):
            raise SpecError(f"{p}：画面模型要有 input.size，如 [224, 224]")
        if inp.get("layout", "NCHW") not in ("NCHW", "NHWC"):
            raise SpecError(f"{p}：input.layout 只能是 NCHW 或 NHWC")
    out = d.get("output") or {}
    if out.get("type", "logits2") not in ("logits2", "logit", "prob"):
        raise SpecError(f"{p}：output.type 只能是 logits2 / logit / prob")
    th = d.get("thresholds") or {}
    medium, high = float(th.get("medium", 0.5)), float(th.get("high", 0.85))
    if not (0 < medium <= high <= 1):
        raise SpecError(f"{p}：阈值要满足 0 < medium ≤ high ≤ 1")
    return ModelSpec(
        name=str(d.get("name") or os.path.basename(dir_)), version=str(d.get("version", "")), detector=det, path=path,
        license=str(d.get("license", "")), input=inp, output_type=out.get("type", "logits2"), fake_index=int(out.get("fake_index", 1)),
        medium=medium, high=high, batch=max(1, int(d.get("batch", 16))), extra={k: v for k, v in d.items() if k not in ("input", "output")},
    )
