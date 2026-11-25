// 检测记录：只存在本机（页面的 localStorage），最多 30 条，不存检测内容，只存路径和两项结论
import { ref } from "vue"
import { baseName, type AnalyzeResult, type HistoryItem } from "../types"

const KEY = "avd.history"
const MAX = 30

function read(): HistoryItem[] {
  try { return JSON.parse(localStorage.getItem(KEY) || "[]") } catch { return [] }
}

const history = ref<HistoryItem[]>(read())

export function useHistory() {
  function add(r: AnalyzeResult) {
    const item: HistoryItem = { path: r.file, name: baseName(r.file), time: Date.now(), ai: r.ai.level, edit: r.edit.level, count: r.findings.filter((f) => f.severity !== "info").length }
    history.value = [item, ...history.value.filter((h) => h.path !== r.file)].slice(0, MAX)
    localStorage.setItem(KEY, JSON.stringify(history.value))
  }
  function clear() {
    history.value = []
    localStorage.removeItem(KEY)
  }
  return { history, add, clear }
}
