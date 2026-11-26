# lexjiance（音视频检测）

代码里的目录和程序名暂时还叫 avdetect，定名后统一改。

检测视频、音频是否 AI 生成、有没有剪辑痕迹的桌面软件，面向律师、法院、检察院。主要是 Windows，也支持 macOS。

- 本机检测（离线、不用模型）：文件元数据（国标 AI 隐式标识、AI 工具名、内容凭证、编辑软件）、封装结构（时间戳断档、关键帧、音画时长）、声音剪辑痕迹（数字静音、底噪突变、频带突变）
- 云端 AI 识别（可选，服务器上跑模型）：合成语音、AI 画面、水印；只上传提取的音轨和抽帧。服务端代码在 `server/`

| 文档 | 内容 |
|---|---|
| `docs/架构.md` | 目录和模块、检测项、数据流、开发方法 |
| `docs/打包.md` | Windows / macOS 打包 |
| `docs/云端接口.md` | 桌面端和识别服务之间的接口 |
| `docs/服务器部署.md` | 识别服务部署（Docker、HTTPS、内网离线） |
| `docs/模型方案.md` | 每个检测项用什么模型、怎么接入、怎么评测定阈值 |
| `docs/开源调研.md` | GitHub 开源项目和许可证 |
| `docs/进度.md` | 进度和下一步 |

快速开始：

```bash
cd engine && python3 -m venv .venv && .venv/bin/pip install numpy && .venv/bin/python -m unittest
cd ../desktop && npm install && npm run check && npm run dev
# Windows 安装包（在 Windows 上）：npm run dist:win
```
