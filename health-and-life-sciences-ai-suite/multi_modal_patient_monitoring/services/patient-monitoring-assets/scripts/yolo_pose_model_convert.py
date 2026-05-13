#!/usr/bin/env python3
"""Download and convert YOLO-Pose model to OpenVINO IR.

Exports a YOLO-Pose model (from ultralytics) to ONNX, then converts to
OpenVINO IR FP16 for efficient inference on Intel GPUs.

The model entry in model-config.yaml should have type: yolo-pose, e.g.:

    pose-3d:
      models:
        - name: yolo11m-pose
          type: yolo-pose
          hub: ultralytics
          model_id: yolo11m-pose
          target_dir: /models/3d-pose
          ir_file: yolo11m-pose.xml
"""

import logging
from pathlib import Path

import yaml
import openvino as ov

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("yolo-pose-convert")

CONFIG_PATH = Path("/app/configs/model-config.yaml")


def _load_yolo_pose_config():
    """Load YOLO-Pose model config from model-config.yaml.

    Returns (model_id, target_dir, ir_file) or None if no yolo-pose
    entry is defined.
    """
    if not CONFIG_PATH.exists():
        return None

    cfg = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    pose_cfg = cfg.get("pose-3d", {})
    models = pose_cfg.get("models", [])

    for m in models:
        if (m or {}).get("type") == "yolo-pose":
            model_id = m.get("model_id")
            target_dir = m.get("target_dir")
            ir_file = m.get("ir_file")
            if not model_id or not target_dir or not ir_file:
                raise ValueError(
                    "yolo-pose model entry must define model_id, target_dir, and ir_file"
                )
            return model_id, target_dir, ir_file

    return None


def convert_yolo_pose():
    """Download YOLO-Pose model and convert to OpenVINO IR."""
    result = _load_yolo_pose_config()
    if result is None:
        logger.info("No yolo-pose model configured in model-config.yaml, skipping.")
        return

    model_id, target_dir, ir_file = result
    target_path = Path(target_dir)
    target_path.mkdir(parents=True, exist_ok=True)
    ir_path = target_path / ir_file

    if ir_path.exists():
        logger.info("YOLO-Pose OpenVINO IR already exists: %s", ir_path)
        return

    logger.info("Downloading YOLO-Pose model: %s", model_id)

    from ultralytics import YOLO

    model = YOLO(f"{model_id}.pt")

    # Export to ONNX
    onnx_path_str = model.export(format="onnx", imgsz=640, half=False, dynamic=False)
    onnx_path = Path(onnx_path_str)

    if not onnx_path.exists():
        raise FileNotFoundError(f"ONNX export failed — file not found: {onnx_path}")

    # Convert ONNX to OpenVINO IR FP16
    logger.info("Converting ONNX to OpenVINO IR FP16: %s", ir_path)
    ov_model = ov.convert_model(str(onnx_path))
    ov.save_model(ov_model, str(ir_path), compress_to_fp16=True)

    # Clean up intermediary files
    onnx_path.unlink(missing_ok=True)
    pt_path = Path(f"{model_id}.pt")
    pt_path.unlink(missing_ok=True)

    logger.info("YOLO-Pose OpenVINO IR saved: %s", ir_path)


if __name__ == "__main__":
    convert_yolo_pose()
