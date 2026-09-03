"""Cache-first bootstrap orchestrator.

State machine:

    initializing
        │
        ├─ ir_dir/best.xml + artifact_marker present ──► ready
        │
        └─ downloading_weights ──► downloading_dataset ──► training
             ──► exporting ──► ready

Each transition fires ``progress(event: dict)`` where ``event`` always has
``state`` + ``phase`` + a human-readable ``message``. Extra fields depend on
the phase (see individual step modules).

This module has NO Flask/FastAPI coupling. It's used by:
  * ``backend/main_bootstrap.py`` — standalone CLI for verification
  * (Phase 3) the real backend server, which subscribes progress → SSE
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .config import load_config


# ---------------------------------------------------------------------------
# Public state model
# ---------------------------------------------------------------------------

STATES = (
    "initializing",
    "checking_cache",
    "downloading_weights",
    "downloading_dataset",
    "training",
    "exporting",
    "ready",
    "error",
)

ProgressCallback = Callable[[dict], None]


@dataclass
class BootstrapState:
    state: str = "initializing"
    phase: str = ""
    message: str = ""
    ir_dir: Optional[str] = None
    error: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    # Sub-progress (e.g. current training epoch)
    detail: dict = field(default_factory=dict)

    def snapshot(self) -> dict:
        return {
            "state": self.state,
            "phase": self.phase,
            "message": self.message,
            "ir_dir": self.ir_dir,
            "error": self.error,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "detail": dict(self.detail),
        }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


class Orchestrator:
    """Runs the cache-first bootstrap.

    Thread-safe. ``run()`` blocks until ready or error; ``run_async()`` returns
    immediately and does the same work in a background thread. State is
    observable via ``.state_snapshot()``.
    """

    def __init__(self, config_path: str | Path, progress: ProgressCallback | None = None):
        self.config_path = Path(config_path)
        self.cfg = load_config(self.config_path)
        self._progress = progress
        self._lock = threading.Lock()
        self._state = BootstrapState()
        self._thread: Optional[threading.Thread] = None

    # -- public --------------------------------------------------------------

    def state_snapshot(self) -> dict:
        with self._lock:
            return self._state.snapshot()

    def run_async(self) -> threading.Thread:
        if self._thread and self._thread.is_alive():
            return self._thread
        self._thread = threading.Thread(target=self.run, name="bootstrap", daemon=True)
        self._thread.start()
        return self._thread

    def run(self) -> dict:
        try:
            self._transition("checking_cache", "cache", "checking model cache")
            hit = self._cache_check()
            if hit:
                self._transition(
                    "ready",
                    "cache",
                    f"cache hit — using {self._state.ir_dir}",
                    ir_dir=self._state.ir_dir,
                )
                return self.state_snapshot()

            self._transition(
                "downloading_weights",
                "weights",
                f"downloading base weights {self.cfg['model']['base_weights']}",
            )
            self._step_weights()

            self._transition(
                "downloading_dataset",
                "dataset",
                f"ensuring dataset {self.cfg['dataset']['name']} at {self.cfg['dataset']['output_dir']}",
            )
            data_yaml = self._step_dataset()

            self._transition(
                "training",
                "train",
                f"training {self.cfg['model']['name']} for {self.cfg['train']['epochs']} epochs",
            )
            train_result = self._step_train(data_yaml)

            self._transition("exporting", "export", "exporting to OpenVINO IR")
            ir_dir = self._step_export(train_result["best_pt"])

            # Touch marker so future runs cache-hit.
            marker = Path(self.cfg["model"]["artifact_marker"])
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(
                f"trained_at={time.time()}\n"
                f"best_pt={train_result['best_pt']}\n"
                f"elapsed_s={train_result['elapsed_s']:.1f}\n"
                f"ir_dir={ir_dir}\n"
            )

            self._transition(
                "ready",
                "done",
                f"bootstrap complete — IR at {ir_dir}",
                ir_dir=str(ir_dir),
            )
            return self.state_snapshot()

        except Exception as exc:  # noqa: BLE001
            self._transition(
                "error",
                self._state.phase or "unknown",
                f"bootstrap failed: {exc}",
                error=repr(exc),
            )
            raise

    # -- steps ---------------------------------------------------------------

    def _cache_check(self) -> bool:
        ir_dir = Path(self.cfg["model"]["ir_dir"])
        marker = Path(self.cfg["model"]["artifact_marker"])
        best_xml = ir_dir / "best.xml"
        best_bin = ir_dir / "best.bin"
        if best_xml.exists() and best_bin.exists() and marker.exists():
            with self._lock:
                self._state.ir_dir = str(ir_dir)
            return True
        # Also honour the case where the IR is present but the marker isn't
        # (user drop-in / make assets). Create the marker retroactively.
        if best_xml.exists() and best_bin.exists():
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(f"externally_seeded_at={time.time()}\nir_dir={ir_dir}\n")
            with self._lock:
                self._state.ir_dir = str(ir_dir)
            return True
        return False

    def _step_weights(self):
        # Lazy import — bootstrap should not require torch/ultralytics on
        # import when we're only checking the cache.
        from .weights_fetcher import ensure_base_weights

        weights_dir = Path(self.cfg["paths"]["cache_dir"]) / "weights"
        ensure_base_weights(
            self.cfg["model"]["name"],
            weights_dir,
            progress=lambda m: self._detail("weights", m),
        )

    def _step_dataset(self) -> Path:
        from .dataset_fetcher import ensure_dataset, dataset_stats

        data_yaml = ensure_dataset(
            self.cfg["dataset"],
            progress=lambda m: self._detail("dataset", m),
        )
        stats = dataset_stats(data_yaml)
        with self._lock:
            self._state.detail["dataset_stats"] = stats
        return data_yaml

    def _step_train(self, data_yaml: Path) -> dict:
        from .train import train_model

        artifacts_dir = Path(self.cfg["paths"]["models_dir"])
        return train_model(
            self.cfg["model"]["name"],
            self.cfg["train"],
            data_yaml,
            artifacts_dir,
            progress=self._forward,
        )

    def _step_export(self, best_pt: str) -> Path:
        from .export import export_model

        # Land the IR at the exact path the cache check looks for.
        ir_target_parent = Path(self.cfg["model"]["ir_dir"]).parent
        return export_model(
            Path(best_pt),
            self.cfg["export"],
            ir_target_parent,
            progress=self._forward,
        )

    # -- internals -----------------------------------------------------------

    def _transition(self, state: str, phase: str, message: str, **extra):
        assert state in STATES, f"unknown state {state!r}"
        with self._lock:
            self._state.state = state
            self._state.phase = phase
            self._state.message = message
            self._state.updated_at = time.time()
            for k, v in extra.items():
                setattr(self._state, k, v) if hasattr(self._state, k) else self._state.detail.update({k: v})
        self._emit({"state": state, "phase": phase, "message": message, **extra})

    def _detail(self, phase: str, message: str):
        with self._lock:
            self._state.detail[phase] = message
            self._state.updated_at = time.time()
        self._emit({"state": self._state.state, "phase": phase, "message": message})

    def _forward(self, event: dict):
        # Callback from train/export subprocesses — surface into detail + emit.
        with self._lock:
            self._state.detail.update(event)
            self._state.updated_at = time.time()
        self._emit(event)

    def _emit(self, event: dict):
        if self._progress:
            try:
                self._progress(event)
            except Exception:
                pass
