"""LLM lifecycle + generation service.

Owns the OpenVINO pipeline, its tokenizer, and the GPU-recycling logic. All
LLM calls (chunking, RAG generation, streaming) go through this service so
the resource-exhaustion retry, generation-count recycling, and post-call
memory cleanup live in one place.
"""
from __future__ import annotations

import ctypes
import gc
import logging
import pathlib
import queue
import threading
import time
from typing import Generator

from components.ov_ir_llm import OVIRTextGenPipeline
from transformers import AutoTokenizer

from utils.latency_store import llm_latency


logger = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        model_path: str,
        hf_id: str,
        device: str,
        temperature: float,
        default_max_new_tokens: int,
        max_generations_before_reload: int,
        generation_timeout: float,
        cache_dir: str | None,
    ) -> None:
        self._model_path = model_path
        self._device = device.upper()
        self._temperature = temperature
        self._default_max_new_tokens = default_max_new_tokens
        self._max_generations_before_reload = max_generations_before_reload
        self._generation_timeout = generation_timeout
        self._cache_dir = cache_dir
        self._generations_since_reload = 0
        self._lock = threading.RLock()

        logger.info(
            "Loading HF tokenizer for %s (model path: %s, device: %s)",
            hf_id, self._model_path, self._device,
        )
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self._model_path, fix_mistral_regex=True)
        except TypeError:
            self.tokenizer = AutoTokenizer.from_pretrained(self._model_path)
        self._llm: OVIRTextGenPipeline | None = self._load_llm()

    # ── public API ───────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> str:
        gen_kwargs = self._generation_kwargs(max_tokens=max_tokens, temperature=temperature)
        prompt_tokens = self.count_tokens(prompt)
        _t0 = time.monotonic()
        with self._lock:
            try:
                result = self._llm.generate(prompt, **gen_kwargs)
            except Exception as exc:  # noqa: BLE001
                if not self._is_resource_exhaustion(exc):
                    raise
                logger.warning(
                    "[LLM] Generation hit resource exhaustion or timeout; recycling pipeline and retrying once: %s",
                    exc,
                )
                self._reload_llm_locked()
                result = self._llm.generate(prompt, **gen_kwargs)
            self._post_generation_locked()
        dt = time.monotonic() - _t0
        text = str(result)
        completion_tokens = self.count_tokens(text)
        tps = (completion_tokens / dt) if dt > 0 else 0.0
        # For non-streaming, approximate TTFT as total_time - decode_window.
        # decode_window = completion_tokens / tps (when tps > 0).
        decode_secs = (completion_tokens / tps) if tps > 0 else 0.0
        approx_ttft_ms = max(0.0, (dt - decode_secs) * 1000)
        logger.info(
            "[LLM] generate prompt_tokens=%d completion_tokens=%d elapsed=%.2fs tps=%.1f",
            prompt_tokens, completion_tokens, dt, tps,
        )
        llm_latency.record(dt * 1000)
        llm_latency.record_metrics(
            ttft_ms=approx_ttft_ms,
            tokens_per_sec=tps,
            total_tokens=completion_tokens,
        )
        return text

    def generate_stream(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Generator[str, None, None]:
        gen_kwargs = self._generation_kwargs(max_tokens=max_tokens, temperature=temperature)
        _t0 = time.monotonic()
        first_token_time: float | None = None
        generated_chunks: list[str] = []
        with self._lock:
            try:
                streamer = self._llm.generate_stream(prompt, **gen_kwargs)
                try:
                    for token in streamer:
                        if first_token_time is None:
                            first_token_time = time.monotonic()
                        generated_chunks.append(token)
                        yield token
                except queue.Empty:
                    # TextIteratorStreamer raises queue.Empty when no token arrives
                    # within its timeout window — treat it the same as a GPU hang.
                    raise TimeoutError(
                        f"LLM streaming exceeded {self._generation_timeout:.0f}s — GPU may be hung"
                    )
            except Exception as exc:  # noqa: BLE001
                if not self._is_resource_exhaustion(exc):
                    raise
                logger.warning(
                    "[LLM] Streaming hit resource exhaustion or timeout; recycling and falling back: %s",
                    exc,
                )
                self._reload_llm_locked()
                result = self._llm.generate(prompt, **gen_kwargs)
                if result:
                    if first_token_time is None:
                        first_token_time = time.monotonic()
                    text = str(result)
                    generated_chunks.append(text)
                    yield text
            finally:
                end_time = time.monotonic()
                elapsed = end_time - _t0
                llm_latency.record(elapsed * 1000)
                completion_text = "".join(generated_chunks)
                completion_tokens = self.count_tokens(completion_text)
                ttft_ms = ((first_token_time - _t0) * 1000) if first_token_time is not None else None
                decode_secs = (end_time - first_token_time) if first_token_time is not None else elapsed
                tps = (completion_tokens / decode_secs) if decode_secs > 0 and completion_tokens > 0 else None
                llm_latency.record_metrics(
                    ttft_ms=ttft_ms,
                    tokens_per_sec=tps,
                    total_tokens=completion_tokens,
                )
                self._post_generation_locked()

    def count_tokens(self, text: str) -> int:
        if not text:
            return 0
        try:
            return len(self.tokenizer.encode(text, add_special_tokens=False))
        except Exception:
            return max(1, len(text) // 4)

    def close(self) -> None:
        with self._lock:
            if self._llm is not None:
                self._destroy_llm(self._llm)
                self._llm = None

    # ── chunker-style callback shim ──────────────────────────────────

    def as_text_generator(self):
        """Returns ``generate`` bound as a plain callable for components that
        accept a ``Callable[[str, int|None, float|None], str]`` (chunker)."""
        return self.generate

    # ── internals ────────────────────────────────────────────────────

    def _build_ov_config(self) -> dict:
        cfg: dict[str, str] = {}
        if self._device == "GPU":
            # cfg["KV_CACHE_PRECISION"] = "u8"
            # cfg["DYNAMIC_QUANTIZATION_GROUP_SIZE"] = "32"
            # cfg["NUM_STREAMS"] = "1"
            # cfg["GPU_HOST_TASK_PRIORITY"] = "HIGH"
            pass
        # cfg["PERFORMANCE_HINT"] = "LATENCY"
        if self._cache_dir:
            cache_path = pathlib.Path(self._cache_dir).expanduser().resolve()
            cache_path.mkdir(parents=True, exist_ok=True)
            cfg["CACHE_DIR"] = str(cache_path)
        logger.info("[LLM] ov_config=%s", cfg)
        return cfg

    def _load_llm(self) -> OVIRTextGenPipeline:
        logger.info(
            "[LLM] Loading OVIRTextGenPipeline from %s on %s",
            self._model_path, self._device,
        )
        return OVIRTextGenPipeline(
            model_path=self._model_path,
            tokenizer=self.tokenizer,
            device=self._device,
            ov_config=self._build_ov_config(),
            generation_timeout=self._generation_timeout,
        )

    def _destroy_llm(self, model: OVIRTextGenPipeline) -> None:
        try:
            model.destroy()
            gc.collect()
            try:
                ctypes.CDLL("libc.so.6").malloc_trim(0)
            except Exception:  # noqa: BLE001
                pass
            logger.info("[LLM] Pipeline destroyed, memory reclaimed")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[LLM] Failed to fully destroy pipeline: %s", exc)

    def _reload_llm_locked(self) -> None:
        if self._llm is not None:
            self._destroy_llm(self._llm)
            self._llm = None
        # Give the GPU driver time to actually reclaim pages before reloading.
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:  # noqa: BLE001
            pass
        time.sleep(3)
        self._llm = self._load_llm()
        self._generations_since_reload = 0

    def _post_generation_locked(self) -> None:
        """Cleanup after a successful generation.

        OVIRTextGenPipeline has no persistent GPU state — each generate() call
        allocates and frees its own InferRequest.  We still run gc.collect and
        malloc_trim to promptly return Python/libc heap pages to the OS, and
        proactively reload the compiled model at the configured threshold to
        prevent any long-term GPU allocator fragmentation.
        """
        self._generations_since_reload += 1
        try:
            gc.collect()
        except Exception:  # noqa: BLE001
            pass
        try:
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        except Exception:  # noqa: BLE001
            pass
        if (
            self._max_generations_before_reload > 0
            and self._generations_since_reload >= self._max_generations_before_reload
        ):
            logger.info(
                "[LLM] Reached %d generations; recycling pipeline proactively",
                self._generations_since_reload,
            )
            self._reload_llm_locked()

    def _generation_kwargs(self, max_tokens: int | None, temperature: float | None) -> dict:
        temp = temperature if temperature is not None else self._temperature
        return {
            "max_new_tokens": max_tokens if max_tokens is not None else self._default_max_new_tokens,
            "temperature": temp,
            "do_sample": temp > 0.0,
        }

    @staticmethod
    def _is_resource_exhaustion(exc: Exception) -> bool:
        if isinstance(exc, TimeoutError):
            return True
        message = str(exc).upper()
        return any(
            marker in message
            for marker in (
                "CL_OUT_OF_RESOURCES",
                "OUT OF MEMORY",
                "NOT ENOUGH MEMORY",
                "ALLOCATE",
                "EXCEEDED MAX SIZE OF MEMORY ALLOCATION",
            )
        )
