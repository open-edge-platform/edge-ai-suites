"""Train a YOLO model on the fetched dataset.

Wraps Ultralytics YOLO.train() with the hyperparameters from
``backend/config/model.yaml`` and the XPU workarounds (xpu_compat shim,
``torch.device('xpu:0')``, ``amp=False``).

Emits per-epoch progress via an optional callback so the FastAPI/Flask
backend can stream training state to the UI.

Ported from poc/st2_app/trainer/train.py.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

# xpu_compat must patch torch.cuda.* before ultralytics is imported.
from . import xpu_compat
from .model_factory import load_train_model


TrainProgress = Callable[[dict], None]


def train_model(
    name: str,
    train_cfg: dict,
    data_yaml: Path,
    artifacts_dir: Path,
    progress: TrainProgress | None = None,
) -> dict:
    """Train a single model. Returns {name, best_pt, elapsed_s, project}."""
    artifacts_dir = Path(artifacts_dir)
    project = artifacts_dir / f"{name}_xpu"
    project.mkdir(parents=True, exist_ok=True)

    dev_kind = train_cfg.get("device", "xpu")
    if dev_kind == "xpu":
        dev = xpu_compat.xpu_device()
    else:
        dev = dev_kind  # let Ultralytics parse "cpu" / "cuda:0" / etc.

    if progress:
        progress({
            "phase": "train",
            "state": "starting",
            "model": name,
            "device": str(dev),
            "epochs": train_cfg["epochs"],
            "data_yaml": str(data_yaml),
        })

    model = load_train_model(name)
    xpu_compat.install_select_device_xpu_shim()

    # Wire per-epoch callback so the caller gets progress ticks.
    if progress:
        def _on_train_epoch_end(trainer):
            try:
                progress({
                    "phase": "train",
                    "state": "epoch_end",
                    "model": name,
                    "epoch": int(trainer.epoch) + 1,
                    "total_epochs": int(trainer.epochs),
                    "loss": float(getattr(trainer, "loss", 0.0) or 0.0),
                })
            except Exception:  # never let a callback break the training loop
                pass

        model.add_callback("on_train_epoch_end", _on_train_epoch_end)

    t0 = time.time()
    model.train(
        data=str(data_yaml),
        epochs=train_cfg["epochs"],
        imgsz=train_cfg["imgsz"],
        batch=train_cfg["batch"],
        workers=train_cfg["workers"],
        device=dev,
        amp=train_cfg["amp"],
        optimizer=train_cfg["optimizer"],
        lr0=train_cfg["lr0"],
        lrf=train_cfg["lrf"],
        weight_decay=train_cfg["weight_decay"],
        momentum=train_cfg["momentum"],
        warmup_epochs=train_cfg["warmup_epochs"],
        cos_lr=train_cfg["cos_lr"],
        box=train_cfg["box"],
        cls=train_cfg["cls"],
        dfl=train_cfg["dfl"],
        hsv_h=train_cfg["hsv_h"],
        hsv_s=train_cfg["hsv_s"],
        hsv_v=train_cfg["hsv_v"],
        degrees=train_cfg["degrees"],
        translate=train_cfg["translate"],
        scale=train_cfg["scale"],
        fliplr=train_cfg["fliplr"],
        mosaic=train_cfg["mosaic"],
        mixup=train_cfg["mixup"],
        close_mosaic=train_cfg["close_mosaic"],
        patience=train_cfg["patience"],
        save_period=train_cfg["save_period"],
        plots=True,
        verbose=True,
        project=str(project),
        name="run",
        exist_ok=True,
    )
    elapsed = time.time() - t0

    best_pt = project / "run" / "weights" / "best.pt"
    if not best_pt.exists():
        raise RuntimeError(f"training finished but {best_pt} missing")

    result = {
        "name": name,
        "best_pt": str(best_pt),
        "elapsed_s": elapsed,
        "project": str(project),
    }
    if progress:
        progress({"phase": "train", "state": "done", **result})
    return result
