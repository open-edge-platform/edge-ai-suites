"""Traditional PP-OCRv4 text recognition (det + rec), callable as a function.

Loads the local PaddleOCR-v4 det/rec inference models and exposes helpers to
OCR a whole image or a single bounding box cropped from a page — the latter is
what you want for reading text inside a specific doc-layout bbox.

Notes
-----
- paddleocr 2.10 pulls in albumentations at import time, which does
  `import torch` and crashes on this env's torch DLLs (WinError 127). OCR
  inference never uses albumentations/torch, so we stub albumentations.pytorch
  BEFORE importing paddleocr to skip that import cleanly.
- The PaddleOCR object is built once and cached (models are heavy to load).
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any, Optional

import numpy as np
from PIL import Image

# ---- default local model locations -----------------------------------------
_MODELS_ROOT = Path(r"C:/Users/user/jianfeng/EDU-AI/PR/temp/models_hub/models")
_DEFAULT_DET = _MODELS_ROOT / "ch_PP-OCRv4_det_infer"
_DEFAULT_REC = _MODELS_ROOT / "ch_PP-OCRv4_rec_infer"

_ocr_instance = None  # cached PaddleOCR


def _stub_albumentations_pytorch() -> None:
    """Prevent paddleocr's import chain from importing torch via albumentations."""
    for mod in ("albumentations.pytorch", "albumentations.pytorch.transforms"):
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)


def get_ocr(det_model_dir: Optional[str] = None,
            rec_model_dir: Optional[str] = None,
            lang: str = "ch"):
    """Return a cached PaddleOCR instance using the local PP-OCRv4 models."""
    global _ocr_instance
    if _ocr_instance is not None:
        return _ocr_instance

    _stub_albumentations_pytorch()
    from paddleocr import PaddleOCR

    det = str(det_model_dir or _DEFAULT_DET)
    rec = str(rec_model_dir or _DEFAULT_REC)
    if not Path(det).exists():
        raise FileNotFoundError(f"det model dir not found: {det}")
    if not Path(rec).exists():
        raise FileNotFoundError(f"rec model dir not found: {rec}")

    _ocr_instance = PaddleOCR(
        det_model_dir=det,
        rec_model_dir=rec,
        use_angle_cls=False,
        lang=lang,
        show_log=False,
    )
    return _ocr_instance


def _to_ndarray(image: Any) -> np.ndarray:
    """Accept a file path, PIL Image, or ndarray; return an RGB ndarray."""
    if isinstance(image, (str, Path)):
        return np.array(Image.open(image).convert("RGB"))
    if isinstance(image, Image.Image):
        return np.array(image.convert("RGB"))
    if isinstance(image, np.ndarray):
        return image
    raise TypeError(f"unsupported image type: {type(image)}")


def _parse_result(result: list) -> list[dict]:
    """Flatten paddleocr .ocr() output into [{text, confidence, bbox}, ...]."""
    lines: list[dict] = []
    if not result:
        return lines
    # paddleocr 2.10 returns [page][line] where line = [bbox, (text, conf)]
    for page in result:
        if not page:
            continue
        for entry in page:
            try:
                bbox, (text, conf) = entry
            except (ValueError, TypeError):
                continue
            lines.append({"text": text, "confidence": float(conf), "bbox": bbox})
    return lines


def ocr_image(image: Any) -> list[dict]:
    """OCR a whole image. Returns [{text, confidence, bbox}, ...] (reading order)."""
    ocr = get_ocr()
    arr = _to_ndarray(image)
    return _parse_result(ocr.ocr(arr, cls=False))


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
    lines = _parse_result(get_ocr().ocr(crop, cls=False))
    return "\n".join(l["text"] for l in lines)


def ocr_regions(image: Any, bboxes: list[list[float]]) -> list[str]:
    """OCR multiple bboxes on the same page; returns text per bbox (same order)."""
    arr = _to_ndarray(image)  # decode once
    return [ocr_region(arr, bbox) for bbox in bboxes]
