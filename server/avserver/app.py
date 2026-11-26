"""HTTP 服务（FastAPI）。接口：GET /v1/health、POST /v1/detect，见 docs/云端接口.md。

安全和隐私：
- 令牌校验（文件里只存哈希）；只在本机测试时可用 AVS_ALLOW_NO_AUTH=1 关掉
- 上传大小上限：边收边数，超了立刻 413（不只看 Content-Length，防谎报）
- 同时识别的请求数有上限，排队超时回 503
- 上传内容只在内存和请求临时目录里，处理完立刻删除；日志只记请求编号、大小、耗时、令牌名，不记内容和文件名
"""
from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from . import __version__, auth
from .config import Config
from .inputs import InputError, load_audio, load_image, parse_meta
from .models.registry import Registry
from .pipeline import run
from .workdir import request_dir

log = logging.getLogger("avserver")


class TooLarge(Exception):
    pass


class BodyLimit:
    """上传大小上限（纯 ASGI 中间件）：先看声明的长度，再对收到的每一块计数，防止不带长度或谎报长度的大上传"""

    def __init__(self, app, limit: int):
        self.app, self.limit = app, limit

    async def _reject(self, send, msg: str):
        body = json.dumps({"error": msg}, ensure_ascii=False).encode()
        await send({"type": "http.response.start", "status": 413, "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        msg = f"上传内容超过 {self.limit // 1048576}MB"
        for k, v in scope.get("headers", []):
            if k == b"content-length":
                try:
                    if int(v) > self.limit:
                        return await self._reject(send, msg)
                except ValueError:
                    return await self._reject(send, "Content-Length 不对")
        received, started = 0, False

        async def counted():
            nonlocal received
            m = await receive()
            if m["type"] == "http.request":
                received += len(m.get("body", b""))
                if received > self.limit:
                    raise TooLarge()
            return m

        async def tracked(m):
            nonlocal started
            if m["type"] == "http.response.start":
                started = True
            await send(m)

        try:
            await self.app(scope, counted, tracked)
        except TooLarge:
            if not started:
                await self._reject(send, msg)


def create_app(cfg: Optional[Config] = None, registry: Optional[Registry] = None) -> FastAPI:
    cfg = cfg or Config()
    reg = registry or Registry(cfg.models_dir, cfg.device, cfg.threads)
    sem = asyncio.Semaphore(max(1, cfg.max_concurrent))
    limit = cfg.max_upload_mb * 1024 * 1024
    app = FastAPI(title="avserver", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)

    def err(code: int, msg: str) -> JSONResponse:
        return JSONResponse({"error": msg}, status_code=code)

    def authorize(request: Request) -> Optional[str]:
        if cfg.allow_no_auth:
            return "（未校验）"
        return auth.check(cfg.tokens_file, request.headers.get("authorization"))

    @app.get("/v1/health")
    async def health(request: Request):
        if not authorize(request):
            return err(401, "访问令牌不对")
        return {"ok": True, "version": f"avserver {__version__}", "models": reg.describe(), "model_errors": len(reg.errors)}

    @app.post("/v1/detect")
    async def detect(request: Request):
        rid = secrets.token_hex(4)
        who = authorize(request)
        if not who:
            return err(401, "访问令牌不对")
        t0 = time.monotonic()
        try:
            form = await request.form(max_files=cfg.max_frames + 2, max_fields=10)
        except TooLarge:
            raise
        except Exception:
            return err(400, "上传内容格式不对（要 multipart/form-data）")
        try:
            meta_raw = form.get("meta")
            if not isinstance(meta_raw, str):
                return err(400, "缺少 meta")
            meta = parse_meta(meta_raw, cfg.max_frames)
            audio_part = form.get("audio")
            frame_parts = [f for f in form.getlist("frames") if isinstance(f, UploadFile)]
            names = {name: t for t, name in meta.frames}
            try:
                await asyncio.wait_for(sem.acquire(), timeout=cfg.queue_wait)
            except asyncio.TimeoutError:
                return err(503, "服务器忙，请稍后再试")
            try:
                with request_dir(cfg.work_dir):
                    audio = load_audio(await audio_part.read(), cfg.max_audio_seconds) if isinstance(audio_part, UploadFile) else None
                    frames = []
                    for i, fp in enumerate(frame_parts):
                        t = names.get(fp.filename or "", meta.frames[i][0] if i < len(meta.frames) else float(i))
                        frames.append((t, load_image(await fp.read())))
                    result = await run_in_threadpool(run, reg, audio, frames, meta.duration)
            finally:
                sem.release()
        except InputError as e:
            return err(400, str(e))
        finally:
            await form.close()
        log.info("识别 %s 令牌=%s 音轨=%s 帧=%d 疑点=%d 用时=%.1fs", rid, who, "有" if audio is not None else "无", len(frames),
                 sum(1 for f in result["findings"] if f["severity"] != "info"), time.monotonic() - t0)
        return result

    @app.exception_handler(Exception)
    async def unexpected(request: Request, e: Exception):
        log.exception("未处理的错误")
        return err(500, "服务器内部错误")

    app.add_middleware(BodyLimit, limit=limit)
    app.state.registry = reg
    return app
