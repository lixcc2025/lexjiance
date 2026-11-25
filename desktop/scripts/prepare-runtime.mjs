#!/usr/bin/env node
// 准备随软件一起打包的运行时：Python + numpy + ffmpeg + 检测引擎，组装到 build/runtime/<平台>-<架构>/。
//
//   node scripts/prepare-runtime.mjs               当前系统（Windows 上就是 win32-x64）
//   node scripts/prepare-runtime.mjs win32-x64     指定目标（在别的系统上也能准备 Windows 的，只是不能自检）
//   加 --refresh 重新下载（默认用 build/cache 里已下载的）
//
// 版本和下载地址在 build/runtime.json。每个下载都校验 SHA256。
// 结构（打包时 electron-builder 原样放进 resources/）：
//   python/   Windows：嵌入版 Python（python311._pth 里加了 Lib\site-packages 和 ..\engine）；macOS：python-build-standalone
//   ffmpeg/   ffmpeg、ffprobe（Windows 是 LGPL 动态链接版，带几个 dll）
//   engine/   检测引擎 avengine（从 ../engine 复制，不含测试）
//   licenses/ 第三方组件的许可证

import { createHash } from "node:crypto"
import { chmodSync, copyFileSync, cpSync, createWriteStream, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from "node:fs"
import { basename, dirname, join, resolve } from "node:path"
import { Readable } from "node:stream"
import { pipeline } from "node:stream/promises"
import { execFileSync } from "node:child_process"
import { fileURLToPath } from "node:url"
import extractZip from "extract-zip"

const DESKTOP = resolve(dirname(fileURLToPath(import.meta.url)), "..")
const ENGINE_SRC = resolve(DESKTOP, "..", "engine", "avengine")
const CACHE = join(DESKTOP, "build", "cache")
const cfg = JSON.parse(readFileSync(join(DESKTOP, "build", "runtime.json"), "utf8"))
const args = process.argv.slice(2)
const REFRESH = args.includes("--refresh")
const HOST = `${process.platform}-${process.arch}`
const TARGET = args.find((a) => !a.startsWith("--")) || HOST
const OUT = join(DESKTOP, "build", "runtime", TARGET)
const IS_WIN = TARGET.startsWith("win32")

const step = (m) => console.log(`\n▶ ${m}`)
const info = (m) => console.log(`  ${m}`)
function fail(m) { console.error(`\n✖ ${m}`); process.exit(1) }

if (!cfg.python[TARGET]) fail(`不支持的目标：${TARGET}（可选：${Object.keys(cfg.python).join("、")}）`)

function sha256(file) {
  return createHash("sha256").update(readFileSync(file)).digest("hex")
}

async function download(url, name = basename(new URL(url).pathname)) {
  mkdirSync(CACHE, { recursive: true })
  const file = join(CACHE, decodeURIComponent(name))
  if (existsSync(file) && !REFRESH) { info(`已缓存 ${basename(file)}`); return file }
  info(`下载 ${url}`)
  const r = await fetch(url, { redirect: "follow" })
  if (!r.ok) fail(`下载失败（${r.status}）：${url}`)
  const tmp = file + ".part"
  await pipeline(Readable.fromWeb(r.body), createWriteStream(tmp))
  rmSync(file, { force: true })
  copyFileSync(tmp, file)
  rmSync(tmp)
  info(`完成 ${(statSync(file).size / 1048576).toFixed(1)} MB`)
  return file
}

async function sumFromList(sumsUrl, filename) {
  const r = await fetch(sumsUrl, { redirect: "follow" })
  if (!r.ok) fail(`取校验文件失败：${sumsUrl}`)
  const line = (await r.text()).split(/\r?\n/).find((l) => l.trim().endsWith(filename))
  if (!line) fail(`校验文件里没有 ${filename}`)
  return line.trim().split(/\s+/)[0].toLowerCase()
}

function verify(file, expected) {
  const got = sha256(file)
  if (got !== expected) { rmSync(file, { force: true }); fail(`${basename(file)} 校验不对（期望 ${expected}，实际 ${got}），已删除，请重试`) }
  info(`SHA256 校验通过 ${got.slice(0, 16)}…`)
  return got
}

const manifest = { target: TARGET, preparedAt: new Date().toISOString(), components: {} }

// ---------- Python ----------
async function preparePython() {
  step("Python")
  const p = cfg.python[TARGET]
  const file = await download(p.url)
  const expected = p.sha256 || (await sumFromList(p.sums, basename(file)))
  const hash = verify(file, expected)
  const dest = join(OUT, "python")
  if (file.endsWith(".zip")) {
    await extractZip(file, { dir: dest })
  } else {
    // python-build-standalone 的包解开就是 python/ 目录
    execFileSync("tar", ["-xzf", file, "-C", OUT])
  }
  if (p.pth) {
    // 嵌入版 Python 不看 PYTHONPATH，靠 ._pth 决定搜索路径：加上 site-packages（numpy）和引擎目录
    const zipName = readdirSync(dest).find((n) => /^python\d+\.zip$/.test(n))
    writeFileSync(join(dest, p.pth), [zipName, ".", p.sitePackages.replace(/\//g, "\\"), "..\\engine", "# import site", ""].join("\r\n"))
    info(`已写 ${p.pth}`)
  }
  manifest.components.python = { url: p.url, sha256: hash }
}

// ---------- numpy ----------
async function prepareNumpy() {
  step(`numpy ${cfg.numpy}`)
  const p = cfg.python[TARGET]
  const r = await fetch(`https://pypi.org/pypi/numpy/${cfg.numpy}/json`)
  if (!r.ok) fail("取 numpy 版本信息失败")
  const meta = await r.json()
  const wheel = meta.urls.find((u) => u.filename.includes(p.wheelTag) && u.filename.endsWith(".whl"))
  if (!wheel) fail(`numpy ${cfg.numpy} 没有 ${p.wheelTag} 的安装包`)
  const file = await download(wheel.url, wheel.filename)
  const hash = verify(file, wheel.digests.sha256)
  const site = join(OUT, "python", ...p.sitePackages.split("/"))
  await extractZip(file, { dir: site })
  for (const n of readdirSync(site)) if (n.endsWith(".whl")) rmSync(join(site, n)) // 包里带的空占位文件
  manifest.components.numpy = { wheel: wheel.filename, sha256: hash }
}

// ---------- ffmpeg ----------
async function prepareFfmpeg() {
  step("ffmpeg")
  const f = cfg.ffmpeg[TARGET]
  const dest = join(OUT, "ffmpeg")
  mkdirSync(dest, { recursive: true })
  mkdirSync(join(OUT, "licenses"), { recursive: true })
  if (f.url) {
    const file = await download(f.url)
    const hash = verify(file, await sumFromList(f.sums, basename(file)))
    const tmp = join(CACHE, "ffmpeg-extract")
    rmSync(tmp, { recursive: true, force: true })
    await extractZip(file, { dir: tmp })
    const top = join(tmp, readdirSync(tmp)[0])
    for (const n of readdirSync(join(top, "bin"))) {
      if (n.startsWith("ffplay")) continue // 播放器用不上
      copyFileSync(join(top, "bin", n), join(dest, n))
    }
    if (existsSync(join(top, "LICENSE.txt"))) copyFileSync(join(top, "LICENSE.txt"), join(OUT, "licenses", "ffmpeg-LICENSE.txt"))
    rmSync(tmp, { recursive: true, force: true })
    manifest.components.ffmpeg = { url: f.url, sha256: hash }
  } else {
    const dir = process.env[f.env]
    if (!dir) fail(`macOS 的 ffmpeg 要用环境变量 ${f.env} 指定目录（里面放 ffmpeg 和 ffprobe）`)
    for (const n of ["ffmpeg", "ffprobe"]) {
      const src = join(dir, n)
      if (!existsSync(src)) fail(`${src} 不存在`)
      copyFileSync(src, join(dest, n))
      chmodSync(join(dest, n), 0o755)
    }
    manifest.components.ffmpeg = { from: dir, sha256: sha256(join(dest, "ffmpeg")) }
  }
  info(`ffmpeg 目录：${readdirSync(dest).length} 个文件`)
}

// ---------- 引擎 ----------
function prepareEngine() {
  step("检测引擎")
  cpSync(ENGINE_SRC, join(OUT, "engine", "avengine"), { recursive: true, filter: (s) => !/__pycache__|\.pyc$/.test(s) })
  info(`已复制 ${ENGINE_SRC}`)
}

function writeLicenses() {
  const lines = [
    "本软件包含以下第三方组件，各自的许可证见同目录或组件目录：",
    `- Python（PSF License）：python/LICENSE.txt`,
    `- NumPy ${cfg.numpy}（BSD-3-Clause）：python/${cfg.python[TARGET].sitePackages}/numpy-${cfg.numpy}.dist-info/`,
    `- FFmpeg（LGPL 2.1 或更高版本）：licenses/ffmpeg-LICENSE.txt，源码 https://ffmpeg.org/download.html`,
    "",
  ]
  writeFileSync(join(OUT, "licenses", "README.txt"), lines.join(IS_WIN ? "\r\n" : "\n"))
}

// ---------- 自检（只能在同一平台上跑） ----------
function selfCheck() {
  step("自检")
  if (TARGET !== HOST) { info(`当前系统是 ${HOST}，跳过自检（到 ${TARGET} 上再跑一次这个脚本即可自检）`); return }
  const py = IS_WIN ? join(OUT, "python", "python.exe") : join(OUT, "python", "bin", "python3")
  const exe = IS_WIN ? ".exe" : ""
  const env = { ...process.env, PYTHONPATH: join(OUT, "engine"), PYTHONUTF8: "1", AVENGINE_FFMPEG: join(OUT, "ffmpeg", "ffmpeg" + exe), AVENGINE_FFPROBE: join(OUT, "ffmpeg", "ffprobe" + exe) }
  const run = (a) => execFileSync(py, a, { env, cwd: join(OUT, "engine"), encoding: "utf8" })
  info(run(["-c", "import sys, numpy; print('Python', sys.version.split()[0], 'numpy', numpy.__version__)"]).trim())
  const dets = JSON.parse(run(["-m", "avengine", "detectors", "--json"]))
  info(`引擎检测项：${dets.map((d) => d.name).join("、")}`)
  const wav = join(CACHE, "selfcheck.wav")
  execFileSync(env.AVENGINE_FFMPEG, ["-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=300:sample_rate=16000", "-t", "3", wav])
  const res = JSON.parse(run(["-m", "avengine", "analyze", wav, "--json"]))
  const ok = res.detectors.every((d) => d.ok)
  info(`试检测 3 秒正弦波：${res.detectors.map((d) => `${d.name}=${d.ok ? (d.skipped ? "跳过" : "完成") : "出错"}`).join("，")}`)
  rmSync(wav, { force: true })
  if (!ok) fail("自检没通过")
}

step(`准备运行时：${TARGET} → ${OUT}`)
rmSync(OUT, { recursive: true, force: true })
mkdirSync(OUT, { recursive: true })
await preparePython()
await prepareNumpy()
await prepareFfmpeg()
prepareEngine()
writeLicenses()
writeFileSync(join(OUT, "runtime-manifest.json"), JSON.stringify(manifest, null, 2))
selfCheck()
console.log(`\n✔ 运行时准备好了：${OUT}`)
