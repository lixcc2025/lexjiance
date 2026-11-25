"""声音剪辑痕迹测试：用 numpy 合成「说话」（调幅的谐波）+ 背景底噪，再人为制造拼接痕迹。
跑法：cd engine && python -m unittest -v tests.test_audio_splice（要 numpy、ffmpeg）
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from avengine.detectors.audio_splice import AudioSpliceDetector  # noqa: E402
from avengine.media.probe import probe  # noqa: E402
from avengine.pipeline import analyze  # noqa: E402

SR = 44100
rng = np.random.default_rng(7)


def speech(seconds: float) -> np.ndarray:
    """像说话的声音：200Hz 基频的谐波，按音节（约 4Hz）开合，中间有停顿"""
    t = np.arange(int(seconds * SR)) / SR
    f0 = 180 + 30 * np.sin(2 * np.pi * 0.7 * t)
    phase = 2 * np.pi * np.cumsum(f0) / SR
    voice = sum(np.sin(k * phase) / k for k in range(1, 12))
    syll = np.clip(np.sin(2 * np.pi * 3.7 * t), 0, None) ** 2
    pause = (np.sin(2 * np.pi * 0.23 * t) > -0.6).astype(float)
    return 0.25 * voice * syll * pause


def noise(seconds: float, dbfs: float) -> np.ndarray:
    return rng.normal(0, 1, int(seconds * SR)) * (10 ** (dbfs / 20))


def lowpass(x: np.ndarray, hz: float) -> np.ndarray:
    X = np.fft.rfft(x)
    X[np.fft.rfftfreq(len(x), 1 / SR) > hz] = 0
    return np.fft.irfft(X, len(x))


def save(path: str, x: np.ndarray) -> str:
    pcm = np.clip(x, -1, 1)
    pcm = np.round(pcm * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return path


@unittest.skipIf(not shutil.which("ffmpeg"), "没有 ffmpeg")
class AudioSpliceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="avengine-splice-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def detect(self, name, x):
        p = save(os.path.join(self.dir, name), x)
        return AudioSpliceDetector().run(probe(p), lambda *_: None)

    def issues(self, found):
        return [f for f in found if f.severity != "info"]

    def test_clean(self):
        x = speech(20) + noise(20, -55)
        self.assertEqual(self.issues(self.detect("clean.wav", x)), [])

    def test_clean_mp3(self):
        # 有损压缩本身不能被当成拼接
        src = save(os.path.join(self.dir, "clean_src.wav"), speech(20) + noise(20, -55))
        mp3 = os.path.join(self.dir, "clean.mp3")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-b:a", "64k", mp3], check=True)
        found = AudioSpliceDetector().run(probe(mp3), lambda *_: None)
        self.assertEqual(self.issues(found), [], [f.title for f in found])

    def test_noise_floor_jump(self):
        x = speech(20) + np.concatenate((noise(10, -62), noise(10, -46)))
        hits = [f for f in self.detect("floor.wav", x) if "底噪" in f.title]
        self.assertEqual(len(hits), 1, [f.title for f in hits])
        self.assertAlmostEqual(hits[0].start, 10, delta=1.01)
        self.assertEqual(hits[0].severity, "medium")
        self.assertIn("变大", hits[0].title)

    def test_digital_silence(self):
        x = speech(12) + noise(12, -55)
        x[int(6.0 * SR):int(6.4 * SR)] = 0
        hits = [f for f in self.detect("zeros.wav", x) if "数字静音" in f.title]
        self.assertEqual(len(hits), 1, [f.title for f in hits])
        self.assertAlmostEqual(hits[0].start, 6.0, delta=0.02)
        self.assertAlmostEqual(hits[0].end, 6.4, delta=0.02)

    def test_many_zero_runs_are_summarized(self):
        x = speech(30) + noise(30, -55)
        for k in range(12):
            a = 1 + k * 2.3
            x[int(a * SR):int((a + 0.2) * SR)] = 0
        hits = [f for f in self.detect("dtx.wav", x) if "数字静音" in f.title]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0].severity, "low")
        self.assertIn("12 段", hits[0].title)

    def test_edge_zeros_ignored(self):
        x = speech(10) + noise(10, -55)
        x[: int(0.2 * SR)] = 0
        x[-int(0.2 * SR):] = 0
        self.assertEqual([f for f in self.detect("edge.wav", x) if "数字静音" in f.title], [])

    def test_bandwidth_change(self):
        a = speech(10) + noise(10, -50)
        b = lowpass(speech(10) + noise(10, -50), 4000)
        hits = [f for f in self.detect("band.wav", np.concatenate((a, b))) if "频带" in f.title]
        self.assertEqual(len(hits), 1, [f.title for f in hits])
        self.assertAlmostEqual(hits[0].start, 10, delta=1.01)
        self.assertLess(hits[0].evidence["之后频带上限（Hz）"], 5000)
        self.assertGreater(hits[0].evidence["之前频带上限（Hz）"], 12000)

    def test_pipeline_verdict(self):
        x = speech(20) + np.concatenate((noise(10, -62), noise(10, -46)))
        p = save(os.path.join(self.dir, "pipe.wav"), x)
        r = analyze(p)
        self.assertEqual(r.edit.level, "suspicious")
        self.assertTrue(any(s.name == "audio_splice" and s.ok and not s.skipped for s in r.detectors))


if __name__ == "__main__":
    unittest.main()
