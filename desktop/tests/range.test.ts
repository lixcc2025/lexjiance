// 回放协议的分段读取（Range）
import { describe, expect, it } from "vitest"
import { parseRange } from "../electron/main/range"

describe("parseRange", () => {
  it("没有或不认识：整文件", () => {
    expect(parseRange(null, 100)).toBeNull()
    expect(parseRange("bytes=-", 100)).toBeNull()
    expect(parseRange("items=0-1", 100)).toBeNull()
  })
  it("常见写法", () => {
    expect(parseRange("bytes=0-", 100)).toEqual({ start: 0, end: 99 })
    expect(parseRange("bytes=10-19", 100)).toEqual({ start: 10, end: 19 })
    expect(parseRange("bytes=90-500", 100)).toEqual({ start: 90, end: 99 })
    expect(parseRange("bytes=-30", 100)).toEqual({ start: 70, end: 99 })   // 最后 30 字节（读 MP4 末尾的索引）
  })
  it("越界：416", () => {
    expect(parseRange("bytes=100-", 100)).toBe("invalid")
    expect(parseRange("bytes=50-40", 100)).toBe("invalid")
  })
})
