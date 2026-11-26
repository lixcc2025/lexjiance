"""服务端测试：用假模型（tests/dummy_models.py）把整条流程测通。跑法：cd server && python -m unittest -v"""
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient  # noqa: E402

from avserver import auth  # noqa: E402
from avserver.app import create_app  # noqa: E402
from avserver.config import Config  # noqa: E402
from avserver.detectors.segments import segments, smooth, windows  # noqa: E402
from avserver.evaluate import auc, eer, threshold_at_fpr  # noqa: E402
from avserver.inputs import InputError, parse_meta  # noqa: E402
from avserver.models.spec import SpecError, load_spec  # noqa: E402
from tests.dummy_models import install  # noqa: E402

SR = 16000


def flac(x: np.ndarray) -> bytes:
    b = io.BytesIO()
    sf.write(b, x.astype(np.float32), SR, format="FLAC")
    return b.getvalue()


def jpeg(level: int) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (64, 48), (level, level, level)).save(b, "JPEG")
    return b.getvalue()


def meta(duration: float, frames=(), has_audio=True) -> str:
    return json.dumps({"api": "v1", "client": {"name": "test"}, "duration": duration, "sample_rate": SR, "has_audio": has_audio,
                       "frames": [{"t": t, "name": n} for t, n in frames]})


class PureTest(unittest.TestCase):
    def test_windows(self):
        self.assertEqual(windows(10, 1, 4, 2), [(0, 4), (2, 6), (4, 8), (6, 10)])
        self.assertEqual(windows(3, 1, 4, 2), [(0, 3)])                      # 不满一窗
        self.assertEqual(windows(9, 1, 4, 4), [(0, 4), (4, 8)])               # 剩 1 个样本（不到半窗）不补
        self.assertEqual(windows(11, 1, 4, 4), [(0, 4), (4, 8), (7, 11)])     # 剩 3 个（超过半窗）补一窗对齐到结尾

    def test_segments_and_smooth(self):
        sc = np.array([0.1, 0.2, 0.9, 0.95, 0.1, 0.8, 0.1])
        st, en = np.arange(7) * 2.0, np.arange(7) * 2.0 + 4
        segs = segments(st, en, sc, 0.5, 13.0)
        self.assertEqual([(s.start, s.end, round(s.peak, 2), s.count) for s in segs], [(4.0, 10.0, 0.95, 2), (10.0, 13.0, 0.8, 1)])
        self.assertEqual(list(smooth(np.array([0, 0, 1, 0, 0.0]))), [0, 0, 0, 0, 0])   # 单点毛刺被抹掉

    def test_metrics(self):
        pos, neg = np.array([0.9, 0.8, 0.7]), np.array([0.1, 0.2, 0.3])
        self.assertEqual(auc(pos, neg), 1.0)
        self.assertEqual(auc(np.array([0.5]), np.array([0.5])), 0.5)        # 同分算一半
        e, _ = eer(pos, neg)
        self.assertEqual(e, 0.0)
        e2, _ = eer(np.array([0.9, 0.4]), np.array([0.5, 0.1]))            # 一对交错：EER 50%
        self.assertAlmostEqual(e2, 0.5)
        pos2, neg2 = np.array([0.9, 0.6, 0.4]), np.array([0.1, 0.5, 0.2, 0.3])
        self.assertEqual(threshold_at_fpr(pos2, neg2, 0.25), (0.4, 0.25, 1.0))   # 允许 1/4 误报：阈值可以降到 0.4，全检出
        self.assertEqual(threshold_at_fpr(pos2, neg2, 0.0), (0.6, 0.0, 2 / 3))   # 不许误报：阈值 0.6，检出 2/3

    def test_meta_validation(self):
        with self.assertRaises(InputError):
            parse_meta("not json", 10)
        with self.assertRaises(InputError):
            parse_meta(json.dumps({"api": "v2"}), 10)
        with self.assertRaises(InputError):
            parse_meta(meta(10, [(i, f"f{i}.jpg") for i in range(11)]), 10)
        m = parse_meta(meta(5.0, [(0.5, "f0000.jpg")]), 10)
        self.assertEqual((m.duration, m.frames), (5.0, [(0.5, "f0000.jpg")]))

    def test_spec_validation(self):
        d = tempfile.mkdtemp()
        try:
            os.makedirs(os.path.join(d, "m"))
            with open(os.path.join(d, "m", "model.json"), "w") as f:
                json.dump({"detector": "ai_voice", "input": {"sample_rate": 16000, "window": 4, "hop": 2}}, f)
            with self.assertRaises(SpecError):                               # 没有模型文件
                load_spec(os.path.join(d, "m"))
            open(os.path.join(d, "m", "model.onnx"), "wb").close()
            with open(os.path.join(d, "m", "model.json"), "w") as f:
                json.dump({"detector": "ai_voice", "input": {"sample_rate": 16000, "window": 4, "hop": 2}, "thresholds": {"medium": 0.9, "high": 0.5}}, f)
            with self.assertRaises(SpecError):                               # 阈值反了
                load_spec(os.path.join(d, "m"))
        finally:
            shutil.rmtree(d)


class ApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="avs-test-")
        cls.models = os.path.join(cls.dir, "models")
        install(cls.models)
        cls.tokens = os.path.join(cls.dir, "tokens.txt")
        cls.token = auth.add(cls.tokens, "测试律所")
        cls.work = os.path.join(cls.dir, "work")
        os.makedirs(cls.work)
        cfg = Config(models_dir=cls.models, tokens_file=cls.tokens, work_dir=cls.work, max_upload_mb=5, max_frames=50)
        cls.client = TestClient(create_app(cfg))
        cls.h = {"Authorization": f"Bearer {cls.token}"}

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def post(self, files, headers=None):
        return self.client.post("/v1/detect", files=files, headers=headers if headers is not None else self.h)

    def test_health_requires_token(self):
        self.assertEqual(self.client.get("/v1/health").status_code, 401)
        self.assertEqual(self.client.get("/v1/health", headers={"Authorization": "Bearer wrong-token"}).status_code, 401)
        r = self.client.get("/v1/health", headers=self.h)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()["models"]), 3)
        self.assertEqual(auth.load(self.tokens).get(self.token), None)       # 文件里没有明文令牌

    def test_detect_locates_synthetic_segment_and_frames(self):
        # 20 秒：8~14 秒「响」（假模型认为是合成）；6 帧里第 3、4 帧亮（假模型认为是生成）
        rng = np.random.default_rng(1)
        x = rng.normal(0, 0.03, SR * 20)
        x[8 * SR:14 * SR] = rng.normal(0, 0.5, SR * 6)
        frames = [(1.5 + i * 3, f"f{i:04d}.jpg") for i in range(6)]
        files = [("meta", (None, meta(20.0, frames))), ("audio", ("audio.flac", flac(np.clip(x, -1, 1)), "audio/flac"))]
        files += [("frames", (n, jpeg(230 if i in (2, 3) else 40), "image/jpeg")) for i, (_, n) in enumerate(frames)]
        r = self.post(files)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        st = {d["name"]: d for d in body["detectors"]}
        self.assertTrue(all(st[n]["ok"] and not st[n]["skipped"] for n in ("ai_voice", "ai_video", "watermark")), st)
        voice = [f for f in body["findings"] if f["detector"] == "ai_voice" and f["severity"] != "info"]
        self.assertEqual(len(voice), 1, body["findings"])
        self.assertAlmostEqual(voice[0]["start"], 8, delta=1.5)
        self.assertAlmostEqual(voice[0]["end"], 14, delta=1.5)
        self.assertEqual((voice[0]["category"], voice[0]["severity"], voice[0]["signal"]), ("ai", "high", "ai_voice"))
        video = [f for f in body["findings"] if f["detector"] == "ai_video" and f["severity"] != "info"]
        self.assertEqual(len(video), 1, body["findings"])
        self.assertAlmostEqual(video[0]["start"], 6.0, delta=0.01)          # 第 3 帧 7.5 秒，前后各半个间隔
        self.assertAlmostEqual(video[0]["end"], 12.0, delta=0.01)
        self.assertEqual(os.listdir(self.work), [])                          # 请求临时目录已删

    def test_clean_input_gives_info_only(self):
        x = np.random.default_rng(2).normal(0, 0.02, SR * 10)
        r = self.post([("meta", (None, meta(10.0))), ("audio", ("audio.flac", flac(x), "audio/flac"))])
        body = r.json()
        self.assertTrue(all(f["severity"] == "info" for f in body["findings"]), body["findings"])
        self.assertEqual({d["name"]: d["skipped"] for d in body["detectors"]}["ai_video"], "没有画面")

    def test_bad_requests(self):
        self.assertEqual(self.post([("meta", (None, "{}"))]).status_code, 400)
        self.assertEqual(self.post([("meta", (None, meta(5)))], headers={}).status_code, 401)
        r = self.post([("meta", (None, meta(5))), ("audio", ("audio.flac", b"not audio", "audio/flac"))])
        self.assertEqual(r.status_code, 400)
        self.assertIn("音轨", r.json()["error"])
        r = self.post([("meta", (None, meta(5))), ("frames", ("f0000.jpg", b"xx", "image/jpeg"))])
        self.assertEqual(r.status_code, 400)
        self.assertEqual(os.listdir(self.work), [])

    def test_upload_limit(self):
        big = b"0" * (6 * 1024 * 1024)
        r = self.post([("meta", (None, meta(5))), ("audio", ("audio.flac", big, "audio/flac"))])
        self.assertEqual(r.status_code, 413)

        def gen():                                                            # 不带 Content-Length 的分块上传
            yield b"--x\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"a.flac\"\r\n\r\n"
            for _ in range(8):
                yield b"0" * (1024 * 1024)
        r = self.client.post("/v1/detect", content=gen(), headers={**self.h, "Content-Type": "multipart/form-data; boundary=x"})
        self.assertEqual(r.status_code, 413)

    def test_no_models(self):
        empty = os.path.join(self.dir, "empty")
        os.makedirs(empty, exist_ok=True)
        c = TestClient(create_app(Config(models_dir=empty, tokens_file=self.tokens, work_dir=self.work)))
        x = np.zeros(SR * 3)
        r = c.post("/v1/detect", files=[("meta", (None, meta(3))), ("audio", ("audio.flac", flac(x), "audio/flac"))], headers=self.h)
        self.assertEqual({d["name"]: d["skipped"] for d in r.json()["detectors"]}["ai_voice"], "服务器上没有安装这个模型")


if __name__ == "__main__":
    unittest.main()
