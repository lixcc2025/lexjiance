"""命令行入口。

  python -m avengine analyze <文件>            人看的文字结果
  python -m avengine analyze <文件> --json     最后输出一个 JSON
  python -m avengine analyze <文件> --jsonl    桌面端用：每行一个事件（progress / finding / detector / result / error）
  python -m avengine detectors                 列出检测项
"""
from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .detectors import ALL
from .pipeline import analyze
from .probe import ProbeError

SEV = {"info": "说明", "low": "轻微", "medium": "可疑", "high": "高度可疑"}


def _fmt_t(t):
    if t is None:
        return ""
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def _print_text(r) -> None:
    d = r.to_dict()
    print(f"文件：{d['file']}")
    m = d["media"]
    print(f"格式：{m['format']}  时长：{m['duration'] or 0:.2f} 秒")
    print(f"\n【AI 生成】{d['ai']['text']}")
    print(f"【剪辑痕迹】{d['edit']['text']}\n")
    for f in d["findings"]:
        pos = ""
        if f["start"] is not None:
            pos = f"  @ {_fmt_t(f['start'])}" + (f" – {_fmt_t(f['end'])}" if f["end"] is not None else "")
        print(f"- [{SEV[f['severity']]}] {f['title']}{pos}")
        if f["detail"]:
            print(f"    {f['detail']}")
    print("\n检测项：")
    for s in d["detectors"]:
        state = "出错：" + s["error"] if not s["ok"] else ("未运行：" + s["skipped"] if s["skipped"] else "完成")
        print(f"  {s['title']} — {state}（{s['seconds']} 秒）")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="avengine", description="音视频 AI 生成 / 剪辑痕迹检测引擎")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze", help="检测一个文件")
    a.add_argument("file")
    g = a.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true")
    g.add_argument("--jsonl", action="store_true")
    a.add_argument("--only", help="只跑这些检测项，逗号分隔")
    sub.add_parser("detectors", help="列出检测项")
    args = p.parse_args(argv)

    if args.cmd == "detectors":
        for cls in ALL:
            print(f"{cls.name:<14} {cls.title}{'（需要模型）' if cls.uses_model else ''}")
        return 0

    def emit_line(kind, payload):
        sys.stdout.write(json.dumps({"type": kind, **payload}, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    only = [x.strip() for x in args.only.split(",")] if args.only else None
    try:
        r = analyze(args.file, emit=emit_line if args.jsonl else None, only=only)
    except ProbeError as e:
        if args.jsonl or args.json:
            print(json.dumps({"type": "error", "message": str(e)}, ensure_ascii=False))
        else:
            print(f"读不了这个文件：{e}", file=sys.stderr)
        return 2
    if args.jsonl:
        emit_line("result", r.to_dict())
    elif args.json:
        print(json.dumps(r.to_dict(), ensure_ascii=False, indent=2))
    else:
        _print_text(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
