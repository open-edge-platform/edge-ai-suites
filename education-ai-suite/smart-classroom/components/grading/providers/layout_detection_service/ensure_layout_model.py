import os
import sys
import shutil
import subprocess
import importlib.metadata
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent          # layout_detection_service/
_SC_ROOT = _HERE.parents[3]                      # smart-classroom/
_LAYOUT_CONFIG = _HERE / "config.yaml"
_MAIN_CONFIG = _SC_ROOT / "config.yaml"

INPUT_SIZE = 800
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}


def _load_layout_cfg() -> dict:
    raw = yaml.safe_load(_LAYOUT_CONFIG.read_text(encoding="utf-8")) or {}
    return raw.get("layout_detection") or {}


def _load_main_hub() -> str:
    try:
        raw = yaml.safe_load(_MAIN_CONFIG.read_text(encoding="utf-8")) or {}
        return str((raw.get("models") or {}).get("model_hub", "huggingface"))
    except Exception:
        return "huggingface"


def _resolve(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (_SC_ROOT / path).resolve()


def _ir_exists(model_dir: Path, precision: str) -> bool:
    return (model_dir / precision / "model.xml").exists()


def _download(source: str, repo_id: str, download_dir: Path) -> None:
    print(f"[1/2] 下载模型  source={source}  repo_id={repo_id}")
    print(f"      目标目录: {download_dir}")
    download_dir.mkdir(parents=True, exist_ok=True)

    if source == "huggingface":
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
        import huggingface_hub as hf_hub
        hf_hub.snapshot_download(
            repo_id=repo_id,
            local_dir=str(download_dir),
            resume_download=True,
            max_workers=4,
        )
    elif source == "modelscope":
        from modelscope import snapshot_download
        snapshot_download(model_id=repo_id, local_dir=str(download_dir), max_workers=4)
    else:
        raise ValueError(f"不支持的下载源: {source}，应为 huggingface 或 modelscope")
    print("      下载完成")


def _find_paddle2onnx() -> str:
    candidates = [
        str(_HERE / "venv_convert" / "Scripts" / "paddle2onnx"),
        os.path.join(os.path.dirname(sys.executable), "paddle2onnx"),
    ]
    for c in candidates:
        if os.path.exists(c) or os.path.exists(c + ".exe"):
            return c
    raise FileNotFoundError(
        "paddle2onnx not found. "
        "Create the conversion venv first:\n"
        f"  python -m venv {_HERE / 'venv_convert'}\n"
        f"  {_HERE / 'venv_convert' / 'Scripts' / 'pip'} install -r {_HERE / 'requirements_convert.txt'}"
    )


def _paddle_to_onnx(model_dir: Path, onnx_path: Path) -> None:
    cmd = [
        _find_paddle2onnx(),
        "--model_dir", str(model_dir),
        "--model_filename", "inference.json",
        "--params_filename", "inference.pdiparams",
        "--save_file", str(onnx_path),
        "--opset_version", "16",
    ]
    print("      paddle -> onnx:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _collect_calib_images(calib_dir: str, max_samples: int) -> list:
    path = _HERE / calib_dir
    if not path.exists():
        return []
    files = sorted({p for e in IMAGE_EXTS for p in path.glob(f"*{e}")})
    return files[:max_samples]


def _build_calib_dataset(files: list, input_names: list):
    import cv2, numpy as np, nncf

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


def _quantize_int8(ov_model, calib_dir: str, calib_samples: int):
    if importlib.metadata.version("nncf") is None:
        subprocess.run([sys.executable, "-m", "pip", "install", "nncf"], check=True)
    import nncf
    input_names = [i.get_any_name() for i in ov_model.inputs]
    files = _collect_calib_images(calib_dir, calib_samples)
    if not files:
        print(f"      在 {calib_dir} 未找到校准图，退回 weight-only int8")
        return nncf.compress_weights(ov_model)
    print(f"      int8 PTQ 全量化，校准样本 {len(files)} 张")
    return nncf.quantize(ov_model, _build_calib_dataset(files, input_names))


def _downgrade_ops_for_npu(ov_model):
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


def _onnx_to_ir(onnx_path: Path, ir_path: Path, precision: str,
                calib_dir: str, calib_samples: int, npu_compat: bool) -> None:
    import openvino as ov
    print(f"      onnx -> OpenVINO IR  precision={precision}")
    ov_model = ov.convert_model(str(onnx_path))
    if npu_compat:
        ov_model = _downgrade_ops_for_npu(ov_model)
    if precision == "int8":
        ov_model = _quantize_int8(ov_model, calib_dir, calib_samples)
        compress_fp16 = False
    else:
        compress_fp16 = (precision == "fp16")
    ov.save_model(ov_model, str(ir_path), compress_to_fp16=compress_fp16)
    print(f"      保存: {ir_path}")


def _convert(download_dir: Path, model_dir: Path, precision: str,
             calib_dir: str, calib_samples: int, npu_compat: bool) -> None:
    out = model_dir / precision
    model_file = download_dir / "inference.json"
    if not model_file.exists():
        raise FileNotFoundError(f"找不到 Paddle 模型: {model_file}")

    out.mkdir(parents=True, exist_ok=True)
    onnx_path = out / (download_dir.name + ".onnx")
    ir_path = out / "model.xml"

    print(f"[2/2] 转换模型 -> {ir_path}")
    _paddle_to_onnx(download_dir, onnx_path)
    _onnx_to_ir(onnx_path, ir_path, precision, calib_dir, calib_samples, npu_compat)

    if onnx_path.exists():
        onnx_path.unlink()
    print("      转换完成")


def ensure_layout_model() -> Path:
    """Ensure the PP-DocLayout OpenVINO IR model is ready.

    Returns the model directory (model_dir/precision) that the detection
    service should load from.
    """
    cfg = _load_layout_cfg()
    source = _load_main_hub()
    repo_id = cfg["repo_id"]
    download_dir = _resolve(cfg["download_dir"])
    model_dir = _resolve(cfg["model_dir"])
    precision = cfg.get("precision", "fp16")
    calib_dir = cfg.get("calibration_dir", "./input")
    calib_samples = int(cfg.get("calibration_samples", 100))
    npu_compat = bool(cfg.get("npu_compatible", True))

    if _ir_exists(model_dir, precision):
        print(f"[layout] IR 已存在，跳过下载和转换: {model_dir / precision}")
        return model_dir / precision

    print("=" * 70)
    print("PP-DocLayout 模型准备")
    print("=" * 70)
    _download(source, repo_id, download_dir)
    _convert(download_dir, model_dir, precision, calib_dir, calib_samples, npu_compat)

    if download_dir.exists():
        shutil.rmtree(download_dir)
        print(f"      已删除原始下载目录: {download_dir}")

    return model_dir / precision


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="确保 PP-DocLayout OpenVINO IR 模型就绪")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-convert", action="store_true")
    args = parser.parse_args()

    cfg = _load_layout_cfg()
    source = _load_main_hub()
    download_dir = _resolve(cfg["download_dir"])
    model_dir = _resolve(cfg["model_dir"])
    precision = cfg.get("precision", "fp16")

    if not args.skip_download:
        _download(source, cfg["repo_id"], download_dir)
    if not args.skip_convert:
        _convert(
            download_dir, model_dir, precision,
            cfg.get("calibration_dir", "./input"),
            int(cfg.get("calibration_samples", 100)),
            bool(cfg.get("npu_compatible", True)),
        )
        if download_dir.exists():
            shutil.rmtree(download_dir)
            print(f"已删除原始下载目录: {download_dir}")

    print(f"\n完成。模型目录: {model_dir / precision}")
