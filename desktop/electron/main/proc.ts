// 结束整棵进程树（纯 Node，单元测试覆盖）。问题清单 P1-2：只杀 Python 的话，它调起的 ffmpeg 会变成孤儿。
//   Windows：taskkill /T /F；macOS / Linux：子进程要用 detached 启动（单独成组），这里 kill 整个进程组。

import { ChildProcess, spawnSync } from "child_process"

export function killTree(child: ChildProcess) {
  if (child.exitCode !== null || child.signalCode !== null || !child.pid) return
  try {
    if (process.platform === "win32") spawnSync("taskkill", ["/PID", String(child.pid), "/T", "/F"], { windowsHide: true })
    else process.kill(-child.pid, "SIGKILL")
  } catch {
    try { child.kill("SIGKILL") } catch { /* 已经没了 */ }
  }
}
