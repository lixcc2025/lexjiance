"""问题清单第二批的回归测试：多音轨选流（P0-3）、ffmpeg 卡住会被终止（P1-2）、解码失败记为出错（P1-4）、
输出目录不覆盖别人的文件、未知检测项名字、C2PA 不靠字样误报。跑法：cd engine && python -m unittest -v tests.test_robustness
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from avengine.extract import extract  # noqa: E402
from avengine.media.ffrun import FFError, stream  # noqa: E402
from avengine.media.outdir import OutDirError  # noqa: E402
from avengine.media.probe import probe  # noqa: E402
from avengine.pipeline import UnknownDetector, analyze  # noqa: E402
from avengine.preview import make_preview  # noqa: E402

FF = shutil.which("ffmpeg")
ENGINE = os.path.join(os.path.dirname(__file__), "..")


def ff(*args):
    subprocess.run([FF, "-v", "error", "-y", *args], check=True)


@unittest.skipIf(not FF, "没有 ffmpeg")
class RobustnessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="avengine-robust-")
        d = cls.dir
        # 多音轨：第 1 条是 8k 单声道（非默认、底噪平稳），第 2 条是 44.1k 立体声（默认、第 10 秒底噪跳变）
        ff("-f", "lavfi", "-i", "testsrc=size=160x120:rate=25", "-t", "20", os.path.join(d, "v.mp4"))
        ff("-f", "lavfi", "-i", "anoisesrc=c=white:a=0.0015:r=8000", "-t", "20", os.path.join(d, "a1.wav"))
        ff("-f", "lavfi", "-i", "anoisesrc=c=white:a=0.0008:r=44100", "-t", "10", os.path.join(d, "a2a.wav"))
        ff("-f", "lavfi", "-i", "anoisesrc=c=white:a=0.006:r=44100", "-t", "10", os.path.join(d, "a2b.wav"))
        ff("-i", os.path.join(d, "a2a.wav"), "-i", os.path.join(d, "a2b.wav"), "-filter_complex", "[0][1]concat=n=2:v=0:a=1,aformat=channel_layouts=stereo",
           os.path.join(d, "a2.wav"))
        ff("-i", os.path.join(d, "v.mp4"), "-i", os.path.join(d, "a1.wav"), "-i", os.path.join(d, "a2.wav"),
           "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "copy", "-c:a", "aac",
           "-disposition:a:0", "0", "-disposition:a:1", "default", os.path.join(d, "multi.mkv"))
        # ffprobe 认得、ffmpeg 解不出：Opus 封装后面全换成乱码
        ff("-f", "lavfi", "-i", "sine=frequency=300:sample_rate=48000", "-t", "5", "-c:a", "libopus", os.path.join(d, "ok.mkv"))
        with open(os.path.join(d, "ok.mkv"), "rb") as f:
            data = bytearray(f.read())
        rnd = random.Random(1)
        for i in range(600, len(data)):
            data[i] = rnd.randrange(256)
        with open(os.path.join(d, "bad.mkv"), "wb") as f:
            f.write(data)
        # 注释里写了「c2pa」字样，但没有真正的内容凭证结构
        ff("-f", "lavfi", "-i", "sine=frequency=300:sample_rate=16000", "-t", "2", "-metadata", "comment=c2pa jumbf test", os.path.join(d, "c2pa_text.mp3"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def test_multitrack_uses_default_audio_everywhere(self):
        p = os.path.join(self.dir, "multi.mkv")
        m = probe(p)
        self.assertEqual([s.index for s in m.audio], [1, 2])
        self.assertEqual(m.target_audio.index, 2)                     # 默认那条，不是流序号最小的
        r = analyze(p)
        self.assertEqual(r.media["audio"]["stream"], 2)                # 界面展示的也是这条
        self.assertEqual(r.media["audio"]["tracks"], 2)
        self.assertEqual(r.media["audio"]["channels"], 2)
        floor = [f for f in r.findings if f.signal == "noise_floor"]   # 只有第 2 条有底噪跳变：说明声音分析用的是它
        self.assertEqual(len(floor), 1, [f.title for f in r.findings])
        self.assertAlmostEqual(floor[0].start, 10, delta=1.01)
        ex = extract(p, os.path.join(self.dir, "ex"), max_frames=2)
        self.assertEqual(ex["audio_stream"], 2)

    def test_decode_failure_is_error_not_too_short(self):
        r = analyze(os.path.join(self.dir, "bad.mkv"))
        st = {s.name: s for s in r.detectors}["audio_splice"]
        self.assertFalse(st.ok)
        self.assertEqual(st.skipped, "")
        self.assertIn("可能损坏", st.error)

    def test_watchdog_kills_stuck_ffmpeg(self):
        t0 = time.monotonic()
        with self.assertRaises(FFError) as ctx:
            with stream(["-f", "lavfi", "-i", "sine=frequency=300", "-t", "600", "-f", "s16le", "-"], idle=0.5) as out:
                out.read(1000)
                time.sleep(2)        # 调用方不读了，ffmpeg 写满管道卡住；看门狗应该把它杀掉
                while out.read(65536):
                    pass
        self.assertIn("被终止", str(ctx.exception))
        self.assertLess(time.monotonic() - t0, 30)

    def test_outdir_refuses_foreign_files(self):
        d = os.path.join(self.dir, "busy")
        os.makedirs(d, exist_ok=True)
        open(os.path.join(d, "合同.docx"), "w").close()
        with self.assertRaises(OutDirError):
            make_preview(os.path.join(self.dir, "c2pa_text.mp3"), d)
        with self.assertRaises(OutDirError):
            extract(os.path.join(self.dir, "c2pa_text.mp3"), d)
        self.assertTrue(os.path.isfile(os.path.join(d, "合同.docx")))

    def test_unknown_detector_name(self):
        with self.assertRaises(UnknownDetector):
            analyze(os.path.join(self.dir, "c2pa_text.mp3"), only=["metadata", "nope"])
        out = subprocess.run([sys.executable, "-m", "avengine", "analyze", os.path.join(self.dir, "c2pa_text.mp3"), "--only", "nope", "--json"],
                             cwd=ENGINE, capture_output=True)
        self.assertEqual(out.returncode, 2)
        self.assertIn("error", json.loads(out.stdout.decode("utf-8")))

    def test_c2pa_text_is_not_a_credential(self):
        r = analyze(os.path.join(self.dir, "c2pa_text.mp3"))
        self.assertEqual([f.title for f in r.findings if f.signal == "c2pa"], [])


if __name__ == "__main__":
    unittest.main()
