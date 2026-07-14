"""Export trained .pt weights to OpenVINO IR (FP16).

Ported from poc/st2_app/trainer/export.py.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from . import xpu_compat  # noqa: F401
from ultralytics import YOLO

xpu_compat.install_select_device_xpu_shim()


ExportProgress = Callable[[dict], None]


def export_model(
    best_pt: Path,
    export_cfg: dict,
    out_dir: Path,
    progress: ExportProgress | None = None,
) -> Path:
    """Export best.pt → OpenVINO IR. Returns the resulting IR directory path."""
    best_pt = Path(best_pt)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if progress:
        progress({
            "phase": "export",
            "state": "starting",
            "best_pt": str(best_pt),
            "format": export_cfg["format"],
            "half": export_cfg["half"],
            "imgsz": export_cfg["imgsz"],
        })

    model = YOLO(str(best_pt))
    exported = model.export(
        format=export_cfg["format"],
        half=export_cfg["half"],
        imgsz=export_cfg["imgsz"],
    )
    exported = Path(exported)

    dst = out_dir / exported.name  # e.g. <out_dir>/best_openvino_model
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(exported, dst)

    if progress:
        progress({"phase": "export", "state": "done", "ir_dir": str(dst)})
    return dst
