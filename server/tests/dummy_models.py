"""测试用的「假模型」：用 onnx 现场搭几个几 KB 的计算图，不是真的 AI 模型，只为把整条流程测通。
- 语音：窗口平均响度越大，「合成」分数越高（logits2）
- 画面：平均亮度越高，「生成」分数越高（prob）
- 水印：和语音一样，但输出单个 logit
"""
from __future__ import annotations

import json
import os

import onnx
from onnx import TensorProto, helper


def _save(graph, path: str) -> None:
    m = helper.make_model(graph, opset_imports=[helper.make_opsetid("", 13)])
    m.ir_version = 8
    onnx.checker.check_model(m)
    onnx.save(m, path)


def _const(name: str, v: float):
    return helper.make_node("Constant", [], [name], value=helper.make_tensor(name + "_t", TensorProto.FLOAT, [1], [v]))


def audio_graph(path: str, out_kind: str) -> None:
    x = helper.make_tensor_value_info("audio", TensorProto.FLOAT, ["N", "T"])
    nodes = [helper.make_node("Abs", ["audio"], ["a"]),
             helper.make_node("ReduceMean", ["a"], ["m"], axes=[1], keepdims=1),
             _const("c", 0.1), _const("k", 40.0),
             helper.make_node("Sub", ["m", "c"], ["d"]), helper.make_node("Mul", ["d", "k"], ["fake"])]
    if out_kind == "logits2":
        # 「真」的 logit 固定为 0，和「假」的 logit 拼成 [N, 2]
        nodes += [_const("zero", 0.0), helper.make_node("Mul", ["fake", "zero"], ["real"]),
                  helper.make_node("Concat", ["real", "fake"], ["out"], axis=1)]
        y = helper.make_tensor_value_info("out", TensorProto.FLOAT, ["N", 2])
    else:
        nodes += [helper.make_node("Identity", ["fake"], ["out"])]
        y = helper.make_tensor_value_info("out", TensorProto.FLOAT, ["N", 1])
    _save(helper.make_graph(nodes, "audio_dummy", [x], [y]), path)


def frame_graph(path: str) -> None:
    x = helper.make_tensor_value_info("image", TensorProto.FLOAT, ["N", 3, 32, 32])
    nodes = [helper.make_node("ReduceMean", ["image"], ["m"], axes=[1, 2, 3], keepdims=0),
             helper.make_node("Unsqueeze", ["m", "ax"], ["m2"]),
             _const("c", 0.5), _const("k", 20.0),
             helper.make_node("Sub", ["m2", "c"], ["d"]), helper.make_node("Mul", ["d", "k"], ["z"]),
             helper.make_node("Sigmoid", ["z"], ["out"])]
    nodes.insert(1, helper.make_node("Constant", [], ["ax"], value=helper.make_tensor("ax_t", TensorProto.INT64, [1], [1])))
    y = helper.make_tensor_value_info("out", TensorProto.FLOAT, ["N", 1])
    _save(helper.make_graph(nodes, "frame_dummy", [x], [y]), path)


def install(models_dir: str, which=("ai_voice", "ai_video", "watermark")) -> None:
    """在 models_dir 下建好假模型和说明文件"""
    specs = {
        "ai_voice": ("voice-dummy", {"sample_rate": 16000, "window": 2.0, "hop": 1.0, "normalize": "none"}, {"type": "logits2", "fake_index": 1}),
        "watermark": ("wm-dummy", {"sample_rate": 16000, "window": 1.0, "hop": 0.5}, {"type": "logit"}),
        "ai_video": ("frame-dummy", {"size": [32, 32], "resize": "stretch", "layout": "NCHW", "scale": 255}, {"type": "prob"}),
    }
    for det in which:
        name, inp, out = specs[det]
        d = os.path.join(models_dir, name)
        os.makedirs(d, exist_ok=True)
        if det == "ai_video":
            frame_graph(os.path.join(d, "model.onnx"))
        else:
            audio_graph(os.path.join(d, "model.onnx"), out["type"])
        with open(os.path.join(d, "model.json"), "w", encoding="utf-8") as f:
            json.dump({"name": name, "version": "test", "detector": det, "file": "model.onnx", "license": "测试用",
                       "input": inp, "output": out, "thresholds": {"medium": 0.5, "high": 0.9}, "batch": 4}, f, ensure_ascii=False)
