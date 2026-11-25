// 结束整棵进程树（问题清单 P1-2）：父进程（相当于 Python）和它调起的子进程（相当于 ffmpeg）都要没了
import { spawn } from "node:child_process"
import { describe, expect, it } from "vitest"
import { killTree } from "../electron/main/proc"

const alive = (pid: number) => { try { process.kill(pid, 0); return true } catch { return false } }
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

describe("killTree", () => {
  it("父子进程一起结束", async () => {
    // 父进程起一个长时间运行的子进程，并把子进程的 pid 打出来
    const script = `const c=require("child_process").spawn(process.execPath,["-e","setInterval(()=>{},1000)"],{stdio:"ignore"});console.log(c.pid);setInterval(()=>{},1000)`
    const parent = spawn(process.execPath, ["-e", script], { detached: process.platform !== "win32", stdio: ["ignore", "pipe", "ignore"] })
    const childPid: number = await new Promise((r) => parent.stdout!.once("data", (b) => r(Number(String(b).trim()))))
    expect(alive(parent.pid!)).toBe(true)
    expect(alive(childPid)).toBe(true)
    killTree(parent)
    for (let i = 0; i < 40 && (alive(parent.pid!) || alive(childPid)); i++) await sleep(100)
    expect(alive(childPid)).toBe(false)
    await new Promise((r) => (parent.exitCode !== null || parent.signalCode !== null ? r(null) : parent.once("exit", r)))
  }, 15000)

  it("已经退出的进程不报错", async () => {
    const p = spawn(process.execPath, ["-e", "0"])
    await new Promise((r) => p.once("exit", r))
    expect(() => killTree(p)).not.toThrow()
  })
})
