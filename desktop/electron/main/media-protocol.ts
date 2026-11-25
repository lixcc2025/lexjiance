// media:// 本地回放协议：页面用 media://file/<编码后的本机路径> 播放被检测的文件、显示预览素材，不放开 file://。
// - 注册成 standard + stream，Chromium 的媒体管线才会发分段（Range）请求；大视频、索引在末尾的 MP4 才能播、能拖
// - 白名单：见 access.ts（只放行可信来源打开的音视频文件和预览素材目录）

import { protocol } from "electron"
import { createReadStream, statSync } from "fs"
import { extname } from "path"
import { Readable } from "stream"
import { Access } from "./access"
import { previewRoot } from "./paths"
import { parseRange } from "./range"

const MIME: Record<string, string> = {
  ".mp4": "video/mp4", ".m4v": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm", ".mkv": "video/x-matroska",
  ".avi": "video/x-msvideo", ".3gp": "video/3gpp", ".ts": "video/mp2t", ".flv": "video/x-flv",
  ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4", ".aac": "audio/aac", ".flac": "audio/flac",
  ".ogg": "audio/ogg", ".opus": "audio/ogg", ".amr": "audio/amr", ".wma": "audio/x-ms-wma",
  ".png": "image/png", ".jpg": "image/jpeg",
}

// 必须在 app ready 之前调用
export function registerMediaScheme() {
  protocol.registerSchemesAsPrivileged([{ scheme: "media", privileges: { standard: true, secure: true, stream: true, supportFetchAPI: true, bypassCSP: true } }])
}

export const access = new Access(() => [previewRoot()])

function serve(req: Request): Response {
  let p: string
  try { p = decodeURIComponent(new URL(req.url).pathname.slice(1)) } catch { return new Response("bad request", { status: 400 }) }
  if (!access.isAllowed(p)) return new Response("forbidden", { status: 403 })
  let size: number
  try {
    const st = statSync(p)
    if (!st.isFile()) throw new Error()
    size = st.size
  } catch {
    return new Response("not found", { status: 404 })
  }
  const type = MIME[extname(p).toLowerCase()] || "application/octet-stream"
  const range = parseRange(req.headers.get("range"), size)
  if (range === "invalid") return new Response(null, { status: 416, headers: { "Content-Range": `bytes */${size}` } })
  if (!range) {
    const body = Readable.toWeb(createReadStream(p)) as unknown as ReadableStream
    return new Response(body, { status: 200, headers: { "Content-Type": type, "Content-Length": String(size), "Accept-Ranges": "bytes" } })
  }
  const body = Readable.toWeb(createReadStream(p, range)) as unknown as ReadableStream
  return new Response(body, {
    status: 206,
    headers: { "Content-Type": type, "Content-Length": String(range.end - range.start + 1), "Content-Range": `bytes ${range.start}-${range.end}/${size}`, "Accept-Ranges": "bytes" },
  })
}

// app ready 之后调用
export function handleMediaProtocol() {
  protocol.handle("media", serve)
}
