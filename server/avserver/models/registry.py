"""扫描模型目录：每个子目录一个模型（model.json + model.onnx）。每个检测项用一个模型；同一检测项有多个时按目录名排序取第一个。
说明文件写错的模型跳过并记日志，不影响别的模型。"""
from __future__ import annotations

import logging
import os
from typing import Optional

from .runtime import Model
from .spec import DETECTORS, SpecError, load_spec

log = logging.getLogger("avserver")


class Registry:
    def __init__(self, models_dir: str, device: str = "auto", threads: int = 0):
        self.models: dict[str, Model] = {}
        self.errors: list[str] = []
        if not os.path.isdir(models_dir):
            log.warning("模型目录不存在：%s（所有 AI 检测项都会显示「模型未安装」）", models_dir)
            return
        for name in sorted(os.listdir(models_dir)):
            d = os.path.join(models_dir, name)
            if not os.path.isfile(os.path.join(d, "model.json")):
                continue
            try:
                spec = load_spec(d)
                if spec.detector in self.models:
                    log.warning("检测项 %s 已有模型，跳过 %s", spec.detector, name)
                    continue
                m = Model(spec, device, threads)
                self.models[spec.detector] = m
                log.info("加载模型 %s → %s（%s）", spec.label, spec.detector, m.device)
            except (SpecError, Exception) as e:  # 坏模型不影响别的
                self.errors.append(f"{name}: {e}")
                log.error("模型 %s 加载失败：%s", name, e)

    def get(self, detector: str) -> Optional[Model]:
        return self.models.get(detector)

    def describe(self) -> list[str]:
        return [f"{d}: {m.spec.label}（{m.device.replace('ExecutionProvider', '')}）" for d, m in sorted(self.models.items())]

    @staticmethod
    def all_detectors() -> tuple[str, ...]:
        return DETECTORS
