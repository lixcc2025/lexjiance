// HTTP Range 请求头解析（纯函数，单元测试覆盖）。
// 返回 null：没有 Range 或格式不认识，按整文件返回；返回 "invalid"：范围越界，应回 416

export function parseRange(header: string | null, size: number): { start: number; end: number } | null | "invalid" {
  const m = /^bytes=(\d*)-(\d*)$/.exec((header || "").trim())
  if (!m || (m[1] === "" && m[2] === "")) return null
  let start: number, end: number
  if (m[1] === "") {
    // bytes=-500：最后 500 字节
    start = Math.max(0, size - Number(m[2]))
    end = size - 1
  } else {
    start = Number(m[1])
    end = m[2] === "" ? size - 1 : Math.min(Number(m[2]), size - 1)
  }
  if (start >= size || start > end) return "invalid"
  return { start, end }
}
