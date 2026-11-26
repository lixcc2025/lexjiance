"""评测工具：小测试集（真实的安静、生成的响），假模型应该完全分得开；报告按生成工具分组。"""
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from avserver.__main__ import main  # noqa: E402
from tests.dummy_models import install  # noqa: E402


@unittest.skipIf(not shutil.which("ffmpeg"), "没有 ffmpeg")
class EvaluateTest(unittest.TestCase):
    def test_cli_evaluate(self):
        d = tempfile.mkdtemp()
        try:
            install(os.path.join(d, "models"), which=("ai_voice",))
            rng = np.random.default_rng(3)
            for i in range(6):
                os.makedirs(os.path.join(d, "ds", "real", "手机"), exist_ok=True)
                sf.write(os.path.join(d, "ds", "real", "手机", f"r{i}.wav"), rng.normal(0, 0.02, 16000 * 5).astype(np.float32), 16000)
            for g in ("工具A", "工具B"):
                os.makedirs(os.path.join(d, "ds", "fake", g), exist_ok=True)
                for i in range(3):
                    sf.write(os.path.join(d, "ds", "fake", g, f"f{i}.wav"), np.clip(rng.normal(0, 0.5, 16000 * 5), -1, 1).astype(np.float32), 16000)
            open(os.path.join(d, "ds", "real", "坏文件.wav"), "wb").write(b"broken")
            out = os.path.join(d, "报告.md")
            os.environ["AVS_MODELS_DIR"] = os.path.join(d, "models")
            try:
                self.assertEqual(main(["evaluate", os.path.join(d, "ds"), "--detector", "ai_voice", "--out", out]), 0)
            finally:
                del os.environ["AVS_MODELS_DIR"]
            r = json.load(open(os.path.splitext(out)[0] + ".json", encoding="utf-8"))
            self.assertEqual((r["真实"], r["AI 生成"], r["失败"]), (6, 6, 1))
            self.assertEqual(r["AUC"], 1.0)
            self.assertEqual(r["EER"], 0.0)
            self.assertEqual(set(r["按生成工具"]), {"工具A", "工具B"})
            self.assertTrue(os.path.isfile(out) and "按生成工具" in open(out, encoding="utf-8").read())
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
