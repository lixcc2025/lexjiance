#!/usr/bin/env python3
"""模拟云端 AI 识别服务器（只用标准库），给桌面端联调和测试用。接口见 docs/云端接口.md。

  python3 tools/mock_cloud.py [端口，默认 8765] [--token 令牌]

收到的音轨会按时长返回一条假的「合成语音」疑点（第 1/3 到 1/2 处），抽帧返回一条「AI 画面」说明；
不保存任何上传内容。真服务器按同样的请求和返回格式实现即可。
"""
from __future__ import annotations

import json
import sys
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TOKEN = ""


def parse_multipart(content_type: str, body: bytes) -> dict[str, list[tuple[str | None, bytes]]]:
    msg = BytesParser(policy=default).parsebytes(b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body)
    out: dict[str, list[tuple[str | None, bytes]]] = {}
    for part in msg.iter_parts():
        name = part.get_param("name", header="content-disposition")
        out.setdefault(name, []).append((part.get_filename(), part.get_payload(decode=True) or b""))
    return out


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, obj) -> None:
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _authed(self) -> bool:
        if TOKEN and self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._json(401, {"error": "unauthorized"})
            return False
        return True

    def do_GET(self):
        if self.path != "/v1/health":
            return self._json(404, {"error": "not found"})
        if self._authed():
            self._json(200, {"ok": True, "version": "mock-1", "models": ["mock-voice", "mock-video"]})

    def do_POST(self):
        if self.path != "/v1/detect":
            return self._json(404, {"error": "not found"})
        if not self._authed():
            return
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        parts = parse_multipart(self.headers.get("Content-Type", ""), body)
        meta = json.loads(parts.get("meta", [(None, b"{}")])[0][1] or b"{}")
        dur = float(meta.get("duration") or 0)
        has_audio = bool(parts.get("audio"))
        frames = parts.get("frames", [])
        detectors, findings = [], []
        if has_audio:
            detectors.append({"name": "ai_voice", "ok": True, "seconds": 0.4})
            findings.append({"detector": "ai_voice", "category": "ai", "severity": "high", "modality": "audio",
                             "title": "这一段声音疑似 AI 合成（模拟服务器）", "detail": "模拟服务器返回的示例结果，不代表真实判断。",
                             "start": round(dur / 3, 2), "end": round(dur / 2, 2),
                             "evidence": {"合成概率": 0.97, "模型": "mock-voice", "收到音轨（字节）": len(parts["audio"][0][1])}})
        else:
            detectors.append({"name": "ai_voice", "ok": True, "skipped": "没有声音"})
        if frames:
            detectors.append({"name": "ai_video", "ok": True, "seconds": 0.3})
            findings.append({"detector": "ai_video", "category": "source", "severity": "info", "modality": "video",
                             "title": f"画面未发现 AI 生成迹象（模拟服务器，收到 {len(frames)} 帧）", "detail": "示例结果。", "evidence": {}})
        else:
            detectors.append({"name": "ai_video", "ok": True, "skipped": "没有画面"})
        detectors.append({"name": "watermark", "ok": True, "skipped": "模拟服务器不支持"})
        self._json(200, {"detectors": detectors, "findings": findings})

    def log_message(self, fmt, *args):
        sys.stderr.write("[mock-cloud] " + fmt % args + "\n")


def main() -> None:
    global TOKEN
    args = sys.argv[1:]
    if "--token" in args:
        i = args.index("--token")
        TOKEN = args[i + 1]
        del args[i:i + 2]
    port = int(args[0]) if args else 8765
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"mock cloud on http://127.0.0.1:{port}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
