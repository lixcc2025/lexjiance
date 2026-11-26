# 模型目录

每个子目录放一个模型：`model.json`（说明）+ `model.onnx`（模型文件）。服务启动时扫描，每个检测项（ai_voice、ai_video、watermark）用一个；
同一检测项有多个时按目录名取第一个。说明文件的字段见 `avserver/models/spec.py` 开头的注释，`_examples/` 里有三个检测项的模板。

```
models/
├── voice-xlsr-zh/        AI 合成语音
│   ├── model.json
│   └── model.onnx
├── video-clip-probe/     AI 生成画面
└── audioseal/            隐形水印
```

检查：`python -m avserver models`（列出加载了哪些模型，说明文件写错会报出来）。
上线前用评测工具定阈值：`python -m avserver evaluate 测试集目录 --detector ai_voice`，见 docs/模型方案.md。

**模型文件不要提交到 git**（.gitignore 已排除 `*.onnx`）；许可证必须允许商用，写在 model.json 的 license 里。
