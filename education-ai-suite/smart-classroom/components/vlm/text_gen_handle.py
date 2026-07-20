# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Handler that fronts the warm ``text_gen`` VLM with a CapabilityRunner.

Mirrors ``components/ocr/ocr_handle.py``: the raw capability (``VLMTextGen``)
is loaded lazily on first use and kept resident, and every call is routed
through a ``CapabilityRunner`` enforcing the ``max_concurrency`` / ``queue_max``
limits. With ``max_concurrency=1`` this is a true FIFO queue — concurrent
callers (in-proc Summary/Mindmap/Segmentation and the re-exposed HTTP endpoint)
serialize behind the single warm pipeline. Queue saturation raises
``QueueFullError`` and a GPU OOM raises ``OomError`` while the capability stays
resident (no process restart).
"""

from threading import Lock
from typing import Iterator, Optional, Union
import logging

logger = logging.getLogger(__name__)

try:
    from model_manager.capability.state import CapabilityState
except ImportError:
    from model_manager.capability import CapabilityState


_TEXT_GEN_MAX_CONCURRENCY = 1   # design default: one warm VLM, no parallel gen
_TEXT_GEN_QUEUE_MAX = 8         # fallback if config key absent (design §6.1)


def _process_memory_mb() -> Optional[float]:
    """Return process RSS in MB, or None if psutil is unavailable."""
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        return None


class TextGenHandler:
    """Owns VLM selection, runner wiring, and the ``generate`` API.

    The VLM is loaded lazily on the first call and kept resident. All calls
    are routed through a CapabilityRunner that enforces concurrency/queue
    limits.
    """

    def __init__(self) -> None:
        self._runner = None
        self._vlm = None
        self._provider: Optional[str] = "vlm"
        self._device: Optional[str] = None
        self._state = CapabilityState.UNLOADED
        self._max_concurrency: int = _TEXT_GEN_MAX_CONCURRENCY  # updated from config on first load
        self._lock = Lock()

    def generate(
        self,
        prompt: str,
        *,
        images: Optional[list] = None,
        stream: bool = True,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> Union[Iterator[str], str]:
        """Generate from ``prompt`` (optionally with ``images``) through the runner."""
        return self._get_runner().submit(
            prompt,
            images=images,
            stream=stream,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
        )

    def load(self) -> None:
        """Force the VLM and runner to initialise (warmup)."""
        self._get_runner()

    @property
    def state(self) -> CapabilityState:
        return self._state

    @property
    def loaded(self) -> bool:
        """Alias for ``state == READY``."""
        return self._state == CapabilityState.READY

    @property
    def provider(self) -> Optional[str]:
        return self._provider

    @property
    def device(self) -> Optional[str]:
        return self._device

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    @property
    def tokenizer(self):
        """HF tokenizer of the warm VLM; loads the capability on first access."""
        self._get_runner()
        return self._vlm.tokenizer

    def memory_stats(self) -> dict:
        """Return process memory stats. Only meaningful when loaded."""
        stats: dict = {}
        rss = _process_memory_mb()
        if rss is not None:
            stats["process_rss_mb"] = rss
        return stats

    def shutdown(self) -> None:
        """Transition READY → EVICTING → UNLOADED, releasing the VLM (GPU)."""
        with self._lock:
            if self._state == CapabilityState.READY:
                self._state = CapabilityState.EVICTING
            if self._vlm is not None:
                try:
                    self._vlm.release()
                except Exception:  # noqa: BLE001 - shutdown best-effort
                    logger.warning("text_gen VLM release failed", exc_info=True)
            self._runner = None
            self._vlm = None
            self._device = None
            self._state = CapabilityState.UNLOADED

    # ------------------------------------------------------------------
    # Internal wiring
    # ------------------------------------------------------------------
    def _get_runner(self):
        if self._state == CapabilityState.READY:  # fast path
            return self._runner
        with self._lock:
            if self._runner is None:
                self._state = CapabilityState.LOADING
                try:
                    vlm = self._build_vlm()
                    max_concurrency, queue_max = self._concurrency_config()
                    self._max_concurrency = max_concurrency
                    try:
                        from model_manager.capability.runner import CapabilityRunner
                    except ImportError:
                        from model_manager.capability import CapabilityRunner
                    self._runner = CapabilityRunner(
                        vlm.generate,
                        max_concurrency=max_concurrency,
                        queue_max=queue_max,
                    )
                    self._state = CapabilityState.READY
                except Exception:
                    self._state = CapabilityState.UNLOADED
                    raise
        return self._runner

    def _concurrency_config(self):
        """Return (max_concurrency, queue_max) from config, with fallback to defaults."""
        try:
            from utils.config_loader import config
            text_gen = getattr(config.models, "text_gen", None)
            if text_gen is None:
                return _TEXT_GEN_MAX_CONCURRENCY, _TEXT_GEN_QUEUE_MAX
            return (
                int(getattr(text_gen, "concurrency", _TEXT_GEN_MAX_CONCURRENCY)),
                int(getattr(text_gen, "queue_max", _TEXT_GEN_QUEUE_MAX)),
            )
        except Exception:
            return _TEXT_GEN_MAX_CONCURRENCY, _TEXT_GEN_QUEUE_MAX

    def _build_vlm(self):
        """Instantiate the warm VLM adapter and record its device."""
        from components.vlm.text_gen_vlm import VLMTextGen

        vlm = VLMTextGen()
        self._vlm = vlm
        self._device = vlm.device
        return vlm
