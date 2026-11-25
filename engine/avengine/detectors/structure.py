"""封装结构：时间戳断档、关键帧位置异常、音画时长不一致。不解码画面，只读包信息，长视频也快。

剪辑后重新导出的文件，时间戳通常是连续的，这一项抓不到；它抓的是「直接拼接、截断、
没有重新编码」留下的结构痕迹，以及原始录制文件里不该出现的断档。
"""
from __future__ import annotations

import statistics
from typing import Optional

from ..models import EDIT, SOURCE, Finding
from ..media.probe import MediaInfo, Packet, packets
from .base import Detector, Progress

GAP_FACTOR = 3.0         # 两包间隔超过正常间隔的几倍算断档
MIN_GAP_SEC = 0.25       # 再小的断档不报（可能是正常抖动）
MAX_REPORT = 20          # 同类疑点最多列几处
MANY_GAPS = 5            # 断档超过这么多处：更像可变帧率 / 屏幕录制 / 边录边停，逐条降为「轻微」


def _gaps(pk: list[Packet]) -> tuple[list[tuple[float, float]], float]:
    """按 pts 排序后找跳变。返回 [(断档开始, 断档结束)]、正常间隔"""
    ts = sorted(p.pts for p in pk if p.pts is not None)
    if len(ts) < 10:
        return [], 0.0
    diffs = [b - a for a, b in zip(ts, ts[1:]) if b > a]
    if not diffs:
        return [], 0.0
    normal = statistics.median(diffs)
    limit = max(normal * GAP_FACTOR, MIN_GAP_SEC)
    return [(a, b) for a, b in zip(ts, ts[1:]) if b - a > limit], normal


def _end_time(pk: list[Packet]) -> Optional[float]:
    """用包算出流的时长（MKV、MPEG-TS 常常没有每条流的 duration）"""
    ends = [p.pts + (p.duration or 0) for p in pk if p.pts is not None]
    starts = [p.pts for p in pk if p.pts is not None]
    return max(ends) - min(starts) if ends else None


def _keyframe_irregular(pk: list[Packet]) -> tuple[list[float], Optional[float]]:
    """关键帧间隔大多固定（手机、监控常见）时，找出不在节奏上的关键帧。返回 (异常位置, 常规间隔)"""
    kf = sorted(p.pts for p in pk if p.key and p.pts is not None)
    if len(kf) < 6:
        return [], None
    iv = [round(b - a, 2) for a, b in zip(kf, kf[1:])]
    common = statistics.mode(iv)
    share = sum(1 for x in iv if abs(x - common) <= 0.05) / len(iv)
    if share < 0.7 or common <= 0:   # 七成以上间隔一致才算「固定节奏」（原来 0.8，多插一个关键帧就刚好卡线）
        return [], None   # 本来就不规律（可变 GOP），不判断
    odd = [kf[i + 1] for i, x in enumerate(iv) if x < common - 0.05 and i + 1 < len(kf) - 1]
    return odd, common


class StructureDetector(Detector):
    name = "structure"
    title = "封装结构"
    desc = "时间戳断档、关键帧位置、音画时长"

    def run(self, media: MediaInfo, progress: Progress) -> list[Finding]:
        out: list[Finding] = []
        # 和其他检测项分析同一条画面、同一条声音（多音轨时尤其要紧）
        streams = [s for s in (media.target_video, media.target_audio) if s]
        lengths: dict[str, Optional[float]] = {}
        for i, s in enumerate(streams):
            progress(0.1 + 0.7 * i / max(1, len(streams)), f"读取{('视频' if s.kind == 'video' else '音频')}包")
            pk = packets(media.path, s.index)
            label = "画面" if s.kind == "video" else "声音"
            lengths[s.kind] = s.duration or _end_time(pk)
            gaps, normal = _gaps(pk)
            many = len(gaps) > MANY_GAPS
            for a, b in gaps[:MAX_REPORT]:
                out.append(Finding(self.name, EDIT, "low" if many else "medium", f"{label}时间戳在这里跳了 {b - a:.2f} 秒",
                                   f"正常每 {normal * 1000:.0f} 毫秒一个数据包，这里中间空了 {b - a:.2f} 秒。原始录制一般是连续的，"
                                   "跳变常见于删掉一段后直接拼接，也可能是录制设备掉帧、暂停录制。",
                                   modality=s.kind, start=round(a, 3), end=round(b, 3), signal="ts_gap",
                                   evidence={"断档前最后一包（秒）": round(a, 3), "断档后第一包（秒）": round(b, 3), "正常间隔（秒）": round(normal, 4)}))
            if many:
                out.append(Finding(self.name, SOURCE, "info", f"{label}有 {len(gaps)} 处时间戳跳变",
                                   "断档很多、分布零散，更像可变帧率、屏幕录制或边录边停，所以每处只记为「轻微」。"
                                   "如果某一处和其他类型的痕迹（底噪突变、关键帧异常等）在同一位置出现，仍然值得重点看。",
                                   modality=s.kind, evidence={"断档数": len(gaps)}))
            if len(gaps) > MAX_REPORT:
                out.append(Finding(self.name, SOURCE, "info", f"{label}还有 {len(gaps) - MAX_REPORT} 处时间戳跳变未列出", modality=s.kind))
            if s.kind == "video":
                odd, common = _keyframe_irregular(pk)
                for t in odd[:MAX_REPORT]:
                    out.append(Finding(self.name, EDIT, "low", "这里多出一个不在节奏上的关键帧",
                                       f"这个视频的关键帧基本每 {common:.2f} 秒一个，这里提前出现了一个。"
                                       "剪辑拼接、重新录制的接缝处常有这种情况，也可能是画面突变时编码器自动插入。",
                                       modality="video", start=round(t, 3), signal="keyframe", evidence={"常规关键帧间隔（秒）": common, "这个关键帧（秒）": round(t, 3)}))

        progress(0.9, "比较音画时长")
        dv, da = lengths.get("video"), lengths.get("audio")
        if dv and da and abs(dv - da) > 1.0:
            out.append(Finding(self.name, EDIT, "low", f"画面和声音长度差了 {abs(dv - da):.1f} 秒",
                               "原始录制的音画长度基本一致。差得多可能是后期替换或拼接过声音，也可能是录制设备的问题。", signal="av_length",
                               evidence={"画面时长（秒）": round(dv, 3), "声音时长（秒）": round(da, 3)}))
        if not out:
            out.append(Finding(self.name, SOURCE, "info", "封装结构没有发现断档",
                               "只说明没有直接拼接的结构痕迹。重新编码导出的剪辑一般看不出来，要靠其他检测项。"))
        return out
