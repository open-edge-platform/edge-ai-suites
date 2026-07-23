from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

_COMPONENT_ROOT = Path(__file__).resolve().parents[2]  # components/grading/
_SC_ROOT = _COMPONENT_ROOT.parents[1]                   # smart-classroom/

_ocr_instance = None


def _load_ocr_config() -> dict:
    import yaml
    cfg_path = _SC_ROOT / "config.yaml"
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    return (raw.get("models") or {}).get("ocr") or {}


def _inject_config_loader(ocr_cfg: dict) -> None:
    """Inject a lightweight mock of utils.config_loader so that
    OpenVINOOCRProcessor can resolve model sub-directory names without
    importing the full main-app config stack."""
    if "utils.config_loader" in sys.modules:
        return

    model_dir = str((_SC_ROOT / ocr_cfg.get("model_dir", "models/ocr")).resolve())

    ocr_ns = types.SimpleNamespace(
        det_model=ocr_cfg.get("det_model", "PP-OCRv6_small_det"),
        rec_model=ocr_cfg.get("rec_model", "PP-OCRv6_small_rec"),
        cls_model=ocr_cfg.get("cls_model", "PP-LCNet_x1_0_doc_ori"),
        model_dir=model_dir,
        device=ocr_cfg.get("device", "CPU"),
    )
    models_ns = types.SimpleNamespace(ocr=ocr_ns)
    config_ns = types.SimpleNamespace(models=models_ns)

    mock = types.ModuleType("utils.config_loader")
    mock.config = config_ns

    utils_mock = sys.modules.get("utils") or types.ModuleType("utils")
    utils_mock.config_loader = mock
    sys.modules.setdefault("utils", utils_mock)
    sys.modules["utils.config_loader"] = mock


def reset_ocr() -> None:
    """Drop the cached processor so the next ocr_region() call rebuilds it
    in the current thread (OpenVINO compiled models are not thread-safe)."""
    global _ocr_instance
    _ocr_instance = None


def _get_processor():
    global _ocr_instance
    if _ocr_instance is not None:
        return _ocr_instance

    ocr_cfg = _load_ocr_config()
    model_dir = str((_SC_ROOT / ocr_cfg.get("model_dir", "models/ocr")).resolve())

    if str(_SC_ROOT) not in sys.path:
        sys.path.insert(0, str(_SC_ROOT))

    _inject_config_loader(ocr_cfg)

    from components.ocr.openvino.openvino_ocr_processor import OpenVINOOCRProcessor

    _ocr_instance = OpenVINOOCRProcessor(
        lang=ocr_cfg.get("lang", "zh"),
        use_angle_cls=True,
        device=ocr_cfg.get("device", "CPU"),
        ir_models_dir=model_dir,
    )
    return _ocr_instance


def _to_ndarray(image: Any) -> np.ndarray:
    if isinstance(image, (str, Path)):
        return np.array(Image.open(image).convert("RGB"))
    if isinstance(image, Image.Image):
        return np.array(image.convert("RGB"))
    if isinstance(image, np.ndarray):
        return image
    raise TypeError(f"unsupported image type: {type(image)}")


_OCR_MIN_HEIGHT = 80


def ocr_region(image: Any, bbox: list[float]) -> str:
    """OCR the text inside a single bounding box of a page image.

    image: full page (path / PIL / ndarray).
    bbox:  [x1, y1, x2, y2] in the page's pixel coordinates.
    Returns the concatenated recognized text (may be multi-line), "" if none.
    """
    arr = _to_ndarray(image)
    x1, y1, x2, y2 = (int(round(v)) for v in bbox)
    h, w = arr.shape[:2]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)
    if x2 <= x1 or y2 <= y1:
        return ""
    crop = arr[y1:y2, x1:x2]
    ch, cw = crop.shape[:2]
    if ch < _OCR_MIN_HEIGHT:
        scale = _OCR_MIN_HEIGHT / ch
        new_size = (max(1, int(cw * scale)), _OCR_MIN_HEIGHT)
        crop = np.array(Image.fromarray(crop).resize(new_size, Image.LANCZOS))
    result = _get_processor().extract_text(crop)
    return result


def ocr_image(image: Any) -> str:
    """OCR a whole image, returns all recognized text joined by newlines."""
    arr = _to_ndarray(image)
    return _get_processor().extract_text(arr)


def ocr_regions(image: Any, bboxes: list[list[float]]) -> list[str]:
    """OCR multiple bboxes on the same page; returns text per bbox (same order)."""
    arr = _to_ndarray(image)
    return [ocr_region(arr, bbox) for bbox in bboxes]


def get_ocr():
    return _get_processor()
