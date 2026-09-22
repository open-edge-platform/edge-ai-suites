"""Base YOLO weights loader. Ported from poc/st2_app/trainer/model_factory.py."""
from __future__ import annotations

from pathlib import Path

# xpu_compat must be applied before ultralytics is imported.
from . import xpu_compat  # noqa: F401
from ultralytics import YOLO


def load_train_model(name: str, weights_dir: Path | None = None) -> YOLO:
    """Return a YOLO instance initialized from the named base weights.

    ``name``: ``yolo11n``, ``yolo11s``, ``yolo26n``, ...
    ``weights_dir``: optional dir holding the local .pt; if absent Ultralytics
    auto-downloads to its own cache.
    """
    if weights_dir is not None:
        cand = Path(weights_dir) / f"{name}.pt"
        if cand.exists():
            return YOLO(str(cand))
    return YOLO(f"{name}.pt")
