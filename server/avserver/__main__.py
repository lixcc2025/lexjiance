"""命令行：
  python -m avserver serve [--host 0.0.0.0] [--port 8000]       启动服务
  python -m avserver token add 名字 / list / remove 名字           管理访问令牌
  python -m avserver models                                      列出已加载的模型、检查说明文件
  python -m avserver evaluate 数据集目录 --detector ai_voice [--out 报告.md]
"""
from __future__ import annotations

import argparse
import logging
import sys

from . import __version__, auth
from .config import Config


def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    p = argparse.ArgumentParser(prog="avserver", description="音视频 AI 识别服务")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sv = sub.add_parser("serve")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8000)
    tk = sub.add_parser("token")
    tk.add_argument("action", choices=["add", "list", "remove"])
    tk.add_argument("name", nargs="?")
    sub.add_parser("models")
    ev = sub.add_parser("evaluate")
    ev.add_argument("dataset")
    ev.add_argument("--detector", required=True, choices=["ai_voice", "ai_video", "watermark"])
    ev.add_argument("--out", default="评测报告.md")
    a = p.parse_args(argv)
    cfg = Config()

    if a.cmd == "serve":
        import uvicorn
        from .app import create_app
        uvicorn.run(create_app(cfg), host=a.host, port=a.port, proxy_headers=True, server_header=False, log_level="info")
        return 0
    if a.cmd == "token":
        if a.action == "list":
            for name in auth.load(cfg.tokens_file).values():
                print(name)
            return 0
        if not a.name:
            print("要给令牌起个名字，比如单位名", file=sys.stderr)
            return 2
        if a.action == "add":
            print(f"新令牌（只显示这一次，发给「{a.name}」填进软件设置）：\n{auth.add(cfg.tokens_file, a.name)}")
        else:
            print("已删除" if auth.remove(cfg.tokens_file, a.name) else "没有这个名字")
        return 0
    from .models.registry import Registry
    reg = Registry(cfg.models_dir, cfg.device, cfg.threads)
    if a.cmd == "models":
        for line in reg.describe() or ["（没有加载任何模型）"]:
            print(line)
        for e in reg.errors:
            print("错误：" + e)
        return 1 if reg.errors else 0
    from .evaluate import evaluate, save, to_markdown
    model = reg.get(a.detector)
    if not model:
        print(f"没有给 {a.detector} 加载模型", file=sys.stderr)
        return 2
    r = evaluate(model, a.dataset)
    save(r, a.out)
    print(to_markdown(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
