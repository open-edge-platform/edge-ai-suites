import os
import sys
import argparse
import subprocess
import importlib.metadata
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

import yaml

CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    cfg = config.get("layout_model_setup")
    if not cfg:
        raise KeyError("config.yaml 中缺少 layout_model_setup 配置段")
    return cfg


def resolve(p):
    p = Path(p)
    return p if p.is_absolute() else (CONFIG_PATH.parent / p)


def download_model(source, repo_id, download_dir):
    download_dir = str(resolve(download_dir))
    print(f"[1/2] 下载模型 | source={source} repo_id={repo_id}")
    print(f"      目标目录: {download_dir}")

    if source == "hf":
        os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
        import huggingface_hub as hf_hub
        hf_hub.snapshot_download(
            repo_id=repo_id,
            local_dir=download_dir,
            resume_download=True,
            max_workers=4,
        )
    elif source == "modelscope":
        from modelscope import snapshot_download
        snapshot_download(model_id=repo_id, local_dir=download_dir, max_workers=4)
    else:
        raise ValueError(f"未知下载来源: {source} (应为 hf 或 modelscope)")

    print(f"      下载完成")
    return download_dir


def get_version(pkg):
    try:
        return importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        return None


def pip_install(spec):
    subprocess.run([sys.executable, "-m", "pip", "install", spec], check=True)


def find_paddle2onnx():
    exe = os.path.join(os.path.dirname(sys.executable), "paddle2onnx")
    return exe if os.path.exists(exe) or os.path.exists(exe + ".exe") else "paddle2onnx"


def paddle_to_onnx(model_dir, onnx_path):
    cmd = [
        find_paddle2onnx(),
        "--model_dir", str(model_dir),
        "--model_filename", "inference.json",
        "--params_filename", "inference.pdiparams",
        "--save_file", str(onnx_path),
        "--opset_version", "16",
    ]
    print("      paddle -> onnx: " + " ".join(cmd))
    subprocess.run(cmd, check=True)


INPUT_SIZE = 800
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


def _collect_calib_images(calib_dir, max_samples):
    calib_dir = resolve(calib_dir)
    if not calib_dir.exists():
        return []
    files = sorted({p for e in IMAGE_EXTS for p in calib_dir.glob(f"*{e}")})
    return files[:max_samples]


def _build_calib_dataset(files, input_names):
    import cv2
    import numpy as np
    import nncf

    def transform(path):
        img = cv2.imread(str(path))
        h, w = img.shape[:2]
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_CUBIC)
        blob = (resized.astype(np.float32) / 255.0).transpose(2, 0, 1)[np.newaxis, ...]
        feed = {}
        for n in input_names:
            if n == "image":
                feed[n] = blob
            elif n == "scale_factor":
                feed[n] = np.array([[INPUT_SIZE / h, INPUT_SIZE / w]], dtype=np.float32)
            elif n == "im_shape":
                feed[n] = np.array([[INPUT_SIZE, INPUT_SIZE]], dtype=np.float32)
        return feed

    return nncf.Dataset(files, transform)


def quantize_int8(ov_model, calib_dir, calib_samples):
    if get_version("nncf") is None:
        print("      安装 nncf...")
        pip_install("nncf")
    import nncf

    input_names = [i.get_any_name() for i in ov_model.inputs]
    files = _collect_calib_images(calib_dir, calib_samples)
    if not files:
        print(f"      在 {calib_dir} 未找到校准图，退回 weight-only int8")
        return nncf.compress_weights(ov_model)

    print(f"      int8 PTQ 全量化，校准样本 {len(files)} 张 (来自 {resolve(calib_dir)})")
    dataset = _build_calib_dataset(files, input_names)
    return nncf.quantize(ov_model, dataset)


def downgrade_ops_for_npu(ov_model):
    """把 ScatterNDUpdate 从 opset15 降级到 opset4。

    OpenVINO 2026.x 转换会生成 opset15 的 ScatterNDUpdate(带 reduction 属性)，
    NPU 编译器不支持该属性。reduction="none" 是默认值、语义等价 opset4，降级后 NPU 可用。
    """
    from openvino import opset4
    from openvino.utils import replace_node
    replaced = 0
    for op in ov_model.get_ordered_ops():
        if op.get_type_info().name == "ScatterNDUpdate":
            d, i, u = op.input_value(0), op.input_value(1), op.input_value(2)
            new = opset4.scatter_nd_update(d, i, u)
            new.set_friendly_name(op.get_friendly_name())
            replace_node(op, new)
            replaced += 1
    if replaced:
        print(f"      NPU 兼容: 降级 {replaced} 个 ScatterNDUpdate opset15 -> opset4")
    return ov_model


def onnx_to_ir(onnx_path, ir_path, precision, calib_dir, calib_samples, npu_compat):
    import openvino as ov
    print(f"      onnx -> openvino IR (precision={precision})")
    ov_model = ov.convert_model(str(onnx_path))
    if npu_compat:
        ov_model = downgrade_ops_for_npu(ov_model)
    if precision == "int8":
        ov_model = quantize_int8(ov_model, calib_dir, calib_samples)
        compress_fp16 = False
    else:
        compress_fp16 = (precision == "fp16")
    ov.save_model(ov_model, str(ir_path), compress_to_fp16=compress_fp16)
    print("      模型接口:")
    for inp in ov_model.inputs:
        print(f"        in  {inp.get_any_name()}: {inp.get_partial_shape()}")
    for out in ov_model.outputs:
        print(f"        out {out.get_any_name()}: {out.get_partial_shape()}")


def convert_model(download_dir, output_dir, precision, calib_dir, calib_samples, npu_compat):
    download_dir = resolve(download_dir)
    output_dir = resolve(output_dir) / precision
    model_file = download_dir / "inference.json"
    if not model_file.exists():
        raise FileNotFoundError(f"找不到 Paddle 模型: {model_file}")

    output_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = output_dir / (download_dir.name + ".onnx")
    ir_path = output_dir / "model.xml"

    print(f"[2/2] 转换模型 -> {ir_path}")
    paddle_to_onnx(download_dir, onnx_path)
    onnx_to_ir(onnx_path, ir_path, precision, calib_dir, calib_samples, npu_compat)

    if onnx_path.exists():
        onnx_path.unlink()
    print(f"      转换完成: {ir_path}")


def main():
    parser = argparse.ArgumentParser(
        description="下载 PP-DocLayoutV3 并转换为 OpenVINO IR (配置见 config.yaml 的 layout_model_setup)"
    )
    parser.add_argument("--skip-download", action="store_true", help="跳过下载，只做转换")
    parser.add_argument("--skip-convert", action="store_true", help="跳过转换，只做下载")
    args = parser.parse_args()

    cfg = load_config()
    source = cfg.get("source", "modelscope")
    repo_id = cfg["repo_id"]
    download_dir = cfg["download_dir"]
    output_dir = cfg["output_dir"]
    precision = cfg.get("precision", "fp32")
    calib_dir = cfg.get("calibration_dir", "./input")
    calib_samples = cfg.get("calibration_samples", 100)
    npu_compat = cfg.get("npu_compatible", True)

    print("=" * 80)
    print("PP-DocLayout 模型准备 (下载 + 转换 OpenVINO)")
    print("=" * 80)

    if not args.skip_download:
        download_model(source, repo_id, download_dir)
    else:
        print("[1/2] 跳过下载")

    if not args.skip_convert:
        convert_model(download_dir, output_dir, precision, calib_dir, calib_samples, npu_compat)
    else:
        print("[2/2] 跳过转换")

    print("\n完成。config.yaml 的 layout_detection.model_path 应指向:")
    print(f"  {resolve(output_dir) / precision}")


if __name__ == "__main__":
    main()
