#!/usr/bin/env python3
import logging
import tempfile
from pathlib import Path

import torch
import openvino as ov
import yaml
from transformers import AutoModel


CONFIG_PATH = Path("/app/configs/model-config.yaml")


logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("hubert-ecg-convert")


def _load_hubert_ecg_model_cfg() -> tuple[str, str, Path]:
    """Return (model_id, model_name, target_dir) for HuBERT-ECG from model-config.yaml.

    We expect model-config.yaml to define an ai-ecg.models entry with
    `source: hubert-ecg`. Its `name` field is used as the IR base
    filename and `target_dir` as the directory where IR files are
    stored (typically /models/ai-ecg).
    """

    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"HuBERT-ECG config not found at {CONFIG_PATH}. Ensure model-config.yaml is mounted."
        )

    try:
        cfg = yaml.safe_load(CONFIG_PATH.read_text()) or {}
    except Exception as e:  # pragma: no cover - config errors are runtime issues
        raise RuntimeError(f"Failed to parse config {CONFIG_PATH}: {e}") from e

    ai_ecg = cfg.get("ai-ecg", {})
    models = ai_ecg.get("models", [])
    if not models:
        raise ValueError(
            "model-config.yaml has no ai-ecg.models entries; cannot determine HuBERT-ECG model."
        )

    hubert_models = [m for m in models if (m or {}).get("source") == "hubert-ecg"]
    if not hubert_models:
        raise ValueError(
            "No ai-ecg.models entry with source: hubert-ecg found in model-config.yaml."
        )
    if len(hubert_models) > 1:
        raise ValueError(
            "Multiple ai-ecg.models entries with source: hubert-ecg found; please keep only one."
        )

    m = hubert_models[0] or {}
    model_id = m.get("model_id")
    name = m.get("name")
    target_dir = m.get("target_dir")

    if not name or not target_dir:
        raise ValueError(
            "HuBERT-ECG ai-ecg.models entry must define both name and target_dir in model-config.yaml."
        )

    return str(model_id), str(name), Path(str(target_dir))


def main() -> int:
    model_id, model_name, target_dir = _load_hubert_ecg_model_cfg()
    target_dir.mkdir(parents=True, exist_ok=True)

    ov_model_path = target_dir / f"{model_name}.xml"

    if ov_model_path.exists():
        logger.info("HuBERT-ECG IR already exists at %s, skipping conversion", ov_model_path)
        return 0

    logger.info("Loading HuBERT-ECG backbone '%s' from Hugging Face", model_id)
    hubert = AutoModel.from_pretrained(model_id, trust_remote_code=True)
    hubert.eval()

    logger.info("Converting HuBERT-ECG to OpenVINO IR at %s", ov_model_path)
    with torch.no_grad():
        example_input = torch.zeros([1, 5000], dtype=torch.float32)

        # Export via ONNX to avoid torch.jit.trace incompatibility with
        # transformers>=4.45 attention masking (q_length/q_offset).
        with tempfile.NamedTemporaryFile(suffix=".onnx", delete=False) as tmp:
            onnx_path = Path(tmp.name)

        torch.onnx.export(
            hubert,
            (example_input,),
            str(onnx_path),
            input_names=["input_values"],
            output_names=["last_hidden_state"],
            dynamic_axes={
                "input_values": {0: "batch", 1: "seq_len"},
                "last_hidden_state": {0: "batch"},
            },
            opset_version=17,
        )

        ov_model = ov.convert_model(str(onnx_path))
        ov.save_model(ov_model, ov_model_path)
        onnx_path.unlink(missing_ok=True)

    logger.info("HuBERT-ECG OpenVINO IR saved: %s", ov_model_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
