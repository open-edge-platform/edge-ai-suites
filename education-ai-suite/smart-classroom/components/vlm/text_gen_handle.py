# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


from threading import Lock
from typing import Iterator, Optional, Union
import logging

logger = logging.getLogger(__name__)

try:
    from model_manager.capability.state import CapabilityState
except ImportError:
    from model_manager.capability import CapabilityState


_TEXT_GEN_MAX_CONCURRENCY = 1
_TEXT_GEN_QUEUE_MAX = 8
_TEXT_GEN_QUEUE_TIMEOUT_S = 180  # bound worst-case wait so a stuck pipe 503s instead of hanging forever


def _process_memory_mb() -> Optional[float]:
    """Return process RSS in MB, or None if psutil is unavailable."""
    try:
        import psutil
        return round(psutil.Process().memory_info().rss / 1024 / 1024, 1)
    except Exception:
        return None


class TextGenHandler:

    def __init__(self) -> None:
        self._runner = None
        self._vlm = None
        self._provider: Optional[str] = "vlm"
        self._device: Optional[str] = None
        self._state = CapabilityState.UNLOADED
        self._max_concurrency: int = _TEXT_GEN_MAX_CONCURRENCY 
        self._lock = Lock()

    def generate(
        self,
        prompt: str,
        *,
        images: Optional[list] = None,
        stream: bool = True,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        enable_thinking: Optional[bool] = None,
        json_schema: Optional[str] = None,
        pre_templated: bool = False,
    ) -> Union[Iterator[str], str]:
        return self._get_runner().submit(
            prompt,
            images=images,
            stream=stream,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            enable_thinking=enable_thinking,
            json_schema=json_schema,
            pre_templated=pre_templated,
        )

    def load(self) -> None:
        self._get_runner()

    @property
    def state(self) -> CapabilityState:
        return self._state

    @property
    def loaded(self) -> bool:
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
        self._get_runner()
        return self._vlm.tokenizer

    def memory_stats(self) -> dict:
        stats: dict = {}
        rss = _process_memory_mb()
        if rss is not None:
            stats["process_rss_mb"] = rss
        return stats

    def shutdown(self) -> None:
        with self._lock:
            if self._state == CapabilityState.READY:
                self._state = CapabilityState.EVICTING
                logger.info("text_gen: shutting down warm VLM (state -> EVICTING)")
            if self._vlm is not None:
                try:
                    self._vlm.release()
                except Exception:  
                    logger.warning("text_gen VLM release failed", exc_info=True)
            self._runner = None
            self._vlm = None
            self._device = None
            self._state = CapabilityState.UNLOADED


    def _get_runner(self):
        if self._state == CapabilityState.READY:  
            return self._runner
        with self._lock:
            if self._runner is None:
                self._state = CapabilityState.LOADING
                logger.info("text_gen: building warm VLM (state -> LOADING)")
                try:
                    vlm = self._build_vlm()
                    max_concurrency, queue_max, queue_timeout_s = self._concurrency_config()
                    self._max_concurrency = max_concurrency
                    try:
                        from model_manager.capability.runner import CapabilityRunner
                    except ImportError:
                        from model_manager.capability import CapabilityRunner
                    self._runner = CapabilityRunner(
                        vlm.generate,
                        max_concurrency=max_concurrency,
                        queue_max=queue_max,
                        timeout_s=queue_timeout_s,
                    )
                    self._state = CapabilityState.READY
                    logger.info(
                        "text_gen: warm VLM ready (state -> READY, device=%s, "
                        "max_concurrency=%d, queue_max=%d, queue_timeout_s=%s)",
                        self._device, max_concurrency, queue_max, queue_timeout_s,
                    )
                except Exception:
                    self._state = CapabilityState.UNLOADED
                    logger.error("text_gen: failed to build warm VLM (state -> UNLOADED)", exc_info=True)
                    raise
        return self._runner

    def _concurrency_config(self):
        try:
            from utils.config_loader import config
            text_gen = getattr(config.models, "text_gen", None)
            if text_gen is None:
                return _TEXT_GEN_MAX_CONCURRENCY, _TEXT_GEN_QUEUE_MAX, _TEXT_GEN_QUEUE_TIMEOUT_S
            return (
                int(getattr(text_gen, "concurrency", _TEXT_GEN_MAX_CONCURRENCY)),
                int(getattr(text_gen, "queue_max", _TEXT_GEN_QUEUE_MAX)),
                int(getattr(text_gen, "queue_timeout_s", _TEXT_GEN_QUEUE_TIMEOUT_S)),
            )
        except Exception:
            return _TEXT_GEN_MAX_CONCURRENCY, _TEXT_GEN_QUEUE_MAX, _TEXT_GEN_QUEUE_TIMEOUT_S

    def _build_vlm(self):
        from components.vlm.text_gen_vlm import VLMTextGen

        vlm = VLMTextGen()
        self._vlm = vlm
        self._device = vlm.device
        return vlm
