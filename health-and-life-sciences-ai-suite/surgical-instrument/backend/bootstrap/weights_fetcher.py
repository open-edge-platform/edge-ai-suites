"""Ensure the base YOLO .pt weights are locally available.

Ultralytics auto-downloads by name (e.g. ``YOLO("yolo11n.pt")``) into its own
cache the first time the constructor is called. This helper triggers that
download once so the bootstrap can advance its lifecycle deterministically
BEFORE the expensive training step.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable


def ensure_base_weights(
    name: str,
    weights_dir: Path,
    progress: Callable[[str], None] | None = None,
) -> Path:
    """Return the local path to ``<name>.pt``, downloading if absent.

    ``weights_dir`` is where we want the .pt to live long-term. If Ultralytics'
    auto-download leaves the file in its default cache, we copy/symlink it in.
    """
    weights_dir = Path(weights_dir)
    weights_dir.mkdir(parents=True, exist_ok=True)
    dst = weights_dir / f"{name}.pt"

    if dst.exists():
        if progress:
            progress(f"weights: cache hit -> {dst}")
        return dst

    if progress:
        progress(f"weights: fetching {name}.pt via Ultralytics hub")

    # Import lazily so callers that only need config parsing don't pay the cost.
    from . import xpu_compat  # noqa: F401
    from ultralytics import YOLO

    # Constructing YOLO(name) triggers the download.
    _ = YOLO(f"{name}.pt")

    # Ultralytics drops the file in CWD by default when only a name is passed.
    for candidate in (Path.cwd() / f"{name}.pt", Path.home() / f".config/Ultralytics/{name}.pt"):
        if candidate.exists():
            # shutil.move handles cross-filesystem moves (bind-mount / named vol
            # sit on a different device than the container overlay).
            shutil.move(str(candidate), str(dst))
            break
    else:
        # If we can't find it, YOLO() would have raised — but be explicit.
        raise FileNotFoundError(
            f"Ultralytics reported success but {name}.pt was not found on disk"
        )

    if progress:
        progress(f"weights: staged -> {dst} ({dst.stat().st_size / 1e6:.1f} MB)")
    return dst
