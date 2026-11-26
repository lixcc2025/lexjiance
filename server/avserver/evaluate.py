"""评测：拿测试集算模型准不准，并给出阈值建议。上线前、换模型、加新生成工具时都要跑。

数据集目录：
  数据集/real/…             真实录音 / 录像（任意子目录）
  数据集/fake/<生成工具>/…   AI 生成的，按工具分目录（如 fake/豆包/、fake/海螺/、fake/GPT-SoVITS/）

  python -m avserver evaluate 数据集目录 --detector ai_voice [--out 报告.md]

每个文件的分数 = 所有窗口（帧）里的最高分（和线上一样先做中值平滑）。输出：
  AUC、等错误率（EER）及其阈值、误报率 1% / 5% 时的阈值和检出率、按生成工具分的检出率、按当前模型阈值的误报率
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Optional

import numpy as np

from .detectors.audio import _normalize, resample
from .detectors.segments import smooth, windows
from .detectors.video import preprocess
from .models.runtime import Model

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".amr", ".wma", ".mp4", ".mov", ".mkv", ".webm"}
VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".3gp", ".flv"}


# ---------- 指标（纯函数） ----------

def auc(pos: np.ndarray, neg: np.ndarray) -> float:
    """ROC 曲线下面积（按秩计算，同分算一半）"""
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    allv = np.concatenate([pos, neg])
    order = allv.argsort(kind="mergesort")
    ranks = np.empty(len(allv))
    ranks[order] = np.arange(1, len(allv) + 1)
    # 同分取平均秩
    for v in np.unique(allv):
        idx = allv == v
        if idx.sum() > 1:
            ranks[idx] = ranks[idx].mean()
    return float((ranks[: len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def roc_points(pos: np.ndarray, neg: np.ndarray) -> list[tuple[float, float, float]]:
    """[(阈值, 误报率 FPR, 检出率 TPR)]，阈值从高到低；分数 ≥ 阈值算「是 AI」"""
    th = np.unique(np.concatenate([pos, neg]))[::-1]
    return [(float(t), float((neg >= t).mean()), float((pos >= t).mean())) for t in th]


def eer(pos: np.ndarray, neg: np.ndarray) -> tuple[float, float]:
    """等错误率：取误报率和漏报率最接近的阈值，EER 记为两者的平均。返回 (EER, 阈值)"""
    best_gap, best = 2.0, (float("nan"), float("nan"))
    for t, fpr, tpr in roc_points(pos, neg):
        fnr = 1 - tpr
        if abs(fpr - fnr) < best_gap:
            best_gap, best = abs(fpr - fnr), ((fpr + fnr) / 2, t)
    return best


def threshold_at_fpr(pos: np.ndarray, neg: np.ndarray, target: float) -> tuple[float, float, float]:
    """误报率不超过 target 的最低阈值 → (阈值, 实际误报率, 检出率)"""
    ok = [(t, fpr, tpr) for t, fpr, tpr in roc_points(pos, neg) if fpr <= target]
    return min(ok, key=lambda x: x[0]) if ok else (1.0, 0.0, 0.0)


# ---------- 打分 ----------

def _ffmpeg_audio(path: str, rate: int) -> np.ndarray:
    r = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-vn", "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"],
                       capture_output=True, timeout=1800)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "replace")[-300:])
    return np.frombuffer(r.stdout, dtype="<f4")


def score_audio_file(model: Model, path: str) -> float:
    spec = model.spec
    rate = int(spec.input["sample_rate"])
    x = _ffmpeg_audio(path, rate)
    wins = windows(len(x), rate, float(spec.input["window"]), float(spec.input["hop"]))
    wlen = max(e - s for s, e in wins)
    batch = np.zeros((len(wins), wlen), dtype=np.float32)
    for i, (s, e) in enumerate(wins):
        batch[i, : e - s] = _normalize(x[s:e], spec.input.get("normalize", "none"))
    return float(smooth(model.scores(batch), 3).max())


def score_video_file(model: Model, path: str, max_frames: int = 120) -> float:
    from PIL import Image
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", path, "-vf", "fps=1", "-frames:v", str(max_frames), os.path.join(d, "f%04d.jpg")],
                       capture_output=True, timeout=1800, check=True)
        files = sorted(os.listdir(d))
        if not files:
            raise RuntimeError("抽不出帧")
        batch = np.stack([preprocess(Image.open(os.path.join(d, f)).convert("RGB"), model.spec.input) for f in files]).astype(np.float32)
    return float(smooth(model.scores(batch), 3).max())


@dataclass
class Item:
    path: str
    label: int          # 1 = AI 生成，0 = 真实
    group: str          # 生成工具名，真实的是 real
    score: Optional[float] = None
    error: str = ""


def collect(root: str, exts: set[str]) -> list[Item]:
    items: list[Item] = []
    for kind, label in (("real", 0), ("fake", 1)):
        base = os.path.join(root, kind)
        for dirpath, _, files in os.walk(base):
            for f in sorted(files):
                if os.path.splitext(f)[1].lower() in exts:
                    rel = os.path.relpath(dirpath, base)
                    group = "real" if label == 0 else (rel.split(os.sep)[0] if rel != "." else "未分类")
                    items.append(Item(os.path.join(dirpath, f), label, group))
    return items


def evaluate(model: Model, root: str, progress=print) -> dict:
    video = model.spec.detector == "ai_video"
    items = collect(root, VIDEO_EXT if video else AUDIO_EXT)
    if not items:
        raise RuntimeError(f"{root} 下面没找到 real/ 和 fake/ 里的音视频文件")
    for i, it in enumerate(items):
        try:
            it.score = score_video_file(model, it.path) if video else score_audio_file(model, it.path)
        except Exception as e:
            it.error = str(e)[:200]
        if (i + 1) % 20 == 0 or i + 1 == len(items):
            progress(f"  已打分 {i + 1}/{len(items)}")
    ok = [it for it in items if it.score is not None]
    pos = np.array([it.score for it in ok if it.label == 1])
    neg = np.array([it.score for it in ok if it.label == 0])
    spec = model.spec
    e, e_th = eer(pos, neg) if len(pos) and len(neg) else (float("nan"), float("nan"))
    groups = {}
    for g in sorted({it.group for it in ok if it.label == 1}):
        s = np.array([it.score for it in ok if it.group == g])
        groups[g] = {"数量": int(len(s)), "按当前阈值检出率": float((s >= spec.medium).mean()), "平均分": float(s.mean())}
    rep = {
        "模型": spec.label, "检测项": spec.detector, "真实": int(len(neg)), "AI 生成": int(len(pos)), "失败": len(items) - len(ok),
        "AUC": auc(pos, neg), "EER": e, "EER 阈值": e_th,
        "误报 1%": dict(zip(("阈值", "误报率", "检出率"), threshold_at_fpr(pos, neg, 0.01))) if len(neg) else None,
        "误报 5%": dict(zip(("阈值", "误报率", "检出率"), threshold_at_fpr(pos, neg, 0.05))) if len(neg) else None,
        "当前阈值": {"medium": spec.medium, "high": spec.high,
                 "误报率": float((neg >= spec.medium).mean()) if len(neg) else None,
                 "检出率": float((pos >= spec.medium).mean()) if len(pos) else None},
        "按生成工具": groups,
        "失败文件": [{"文件": os.path.relpath(it.path, root), "原因": it.error} for it in items if it.score is None][:50],
    }
    return rep


def to_markdown(r: dict) -> str:
    pct = lambda v: "—" if v is None or v != v else f"{v * 100:.1f}%"
    num = lambda v: "—" if v is None or v != v else f"{v:.3f}"
    lines = [f"# 评测报告：{r['模型']}（{r['检测项']}）", "",
             f"- 样本：真实 {r['真实']}，AI 生成 {r['AI 生成']}，失败 {r['失败']}",
             f"- AUC：{num(r['AUC'])}（1 是完美，0.5 等于瞎猜）",
             f"- 等错误率 EER：{pct(r['EER'])}（阈值 {num(r['EER 阈值'])}）"]
    for k in ("误报 1%", "误报 5%"):
        if r[k]:
            lines.append(f"- {k}：阈值 {num(r[k]['阈值'])}，实际误报 {pct(r[k]['误报率'])}，检出 {pct(r[k]['检出率'])}")
    c = r["当前阈值"]
    lines += [f"- 当前阈值 medium={c['medium']} / high={c['high']}：误报 {pct(c['误报率'])}，检出 {pct(c['检出率'])}", "",
              "## 按生成工具", "", "| 工具 | 数量 | 检出率（当前阈值） | 平均分 |", "|---|---|---|---|"]
    for g, v in r["按生成工具"].items():
        lines.append(f"| {g} | {v['数量']} | {pct(v['按当前阈值检出率'])} | {num(v['平均分'])} |")
    if r["失败文件"]:
        lines += ["", "## 打分失败的文件", ""] + [f"- {x['文件']}：{x['原因']}" for x in r["失败文件"]]
    lines += ["", "阈值建议：法律场景误报代价高，medium 取「误报 5%」的阈值，high 取「误报 1%」的阈值，写回 model.json 的 thresholds。", ""]
    return "\n".join(lines)


def save(r: dict, out: str) -> None:
    with open(out, "w", encoding="utf-8") as f:
        f.write(to_markdown(r))
    with open(os.path.splitext(out)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
