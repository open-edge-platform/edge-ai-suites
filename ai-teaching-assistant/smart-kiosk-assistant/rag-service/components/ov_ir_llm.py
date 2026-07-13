"""OVModelForCausalLM-based text generation pipeline.

Uses optimum.intel.OVModelForCausalLM with direct model.generate() calls
(no HF pipeline wrapper).  GenerationConfig is loaded from the model's
generation_config.json — the same source ov_genai.LLMPipeline uses for its
default config — so top_k, top_p, repetition_penalty, eos_token_id, etc.
all match what the genai pipeline used.  Per-call overrides (temperature=0,
do_sample=False) are applied on top.
"""
from __future__ import annotations

import ctypes
import gc
import logging
import threading

from optimum.intel.openvino import OVModelForCausalLM
from transformers import GenerationConfig, TextIteratorStreamer

logger = logging.getLogger(__name__)


class OVIRTextGenPipeline:
    """
    Drop-in replacement for ov_genai.LLMPipeline that uses
    OVModelForCausalLM + direct model.generate().

    The HF generate() loop allocates the KV cache on-the-fly and releases
    it when the call returns — no GPU state leaks between separate calls.
    """

    def __init__(
        self,
        model_path: str,
        tokenizer,
        device: str = "GPU",
        ov_config: dict | None = None,
        generation_timeout: float = 90.0,
    ) -> None:
        self._tokenizer = tokenizer
        self._device = device
        self._generation_timeout = generation_timeout
        logger.info(
            "[OV-MODEL] Loading OVModelForCausalLM from %s on %s (ov_config=%s)",
            model_path, device, ov_config or "{}",
        )
        self._model = OVModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True,
            device=device,
            ov_config=ov_config or {},
        )

        # Load generation_config.json — same source ov_genai uses.
        # Keeps eos_token_id, pad_token_id, top_k, top_p, repetition_penalty, etc.
        try:
            self._gen_config = GenerationConfig.from_pretrained(model_path)
            logger.info(
                "[OV-MODEL] generation_config: do_sample=%s temperature=%s "
                "top_k=%s top_p=%s eos_token_id=%s",
                self._gen_config.do_sample,
                self._gen_config.temperature,
                getattr(self._gen_config, "top_k", None),
                getattr(self._gen_config, "top_p", None),
                self._gen_config.eos_token_id,
            )
        except Exception as exc:  # noqa: BLE001
            self._gen_config = GenerationConfig()
            logger.warning("[OV-MODEL] Could not load generation_config.json (%s), using defaults", exc)

        # Ensure pad_token_id is set (required for batched / left-pad scenarios).
        if self._gen_config.pad_token_id is None:
            eos = self._gen_config.eos_token_id
            self._gen_config.pad_token_id = eos[0] if isinstance(eos, list) else eos

        logger.info("[OV-MODEL] Ready on %s", device)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        max_new_tokens: int = 192,
        temperature: float = 0.0,
        do_sample: bool = False,
    ) -> str:
        # Format as a chat message so Qwen3-Instruct responds as an assistant
        # (direct JSON answer) rather than doing raw text continuation first.
        # enable_thinking=False suppresses Qwen3's <think>...</think> mode.
        messages = [{"role": "user", "content": prompt}]
        try:
            formatted = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            # Tokenizer doesn't support enable_thinking (non-Qwen3 model)
            formatted = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = self._tokenizer(formatted, return_tensors="pt")
        input_len = inputs["input_ids"].shape[1]

        # Clone base config and apply per-call overrides.
        cfg = GenerationConfig(**self._gen_config.to_dict())
        cfg.max_new_tokens = max_new_tokens
        # Greedy when temperature=0 or do_sample=False; preserve top_k/top_p
        # values from generation_config.json for when sampling is enabled.
        cfg.do_sample = do_sample and temperature > 0.0
        cfg.temperature = temperature if cfg.do_sample else None

        # Run model.generate() in a daemon thread so we can enforce a wall-clock
        # timeout. If the GPU hangs, TimeoutError is raised and the pipeline's
        # error-recovery path (reload + retry) kicks in automatically.
        _result: list = []
        _error: list = []

        def _run_generate() -> None:
            try:
                _result.append(self._model.generate(**inputs, generation_config=cfg))
            except Exception as exc:  # noqa: BLE001
                _error.append(exc)

        _t = threading.Thread(target=_run_generate, daemon=True)
        _t.start()
        _t.join(timeout=self._generation_timeout)

        if _t.is_alive():
            raise TimeoutError(
                f"LLM generation exceeded {self._generation_timeout:.0f}s — GPU may be hung"
            )
        if _error:
            raise _error[0]

        output_ids = _result[0]
        new_token_ids = output_ids[0][input_len:]
        return self._tokenizer.decode(new_token_ids, skip_special_tokens=True).strip()

    def generate_stream(
        self,
        prompt: str,
        max_new_tokens: int = 512,
        temperature: float = 0.0,
        do_sample: bool = False,
    ) -> TextIteratorStreamer:
        """Token-level streaming via TextIteratorStreamer + background thread.

        Starts generation in a daemon thread and returns the streamer immediately
        so the caller can iterate tokens as they are produced.
        """
        messages = [{"role": "user", "content": prompt}]
        try:
            formatted = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
        except TypeError:
            formatted = self._tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )

        inputs = self._tokenizer(formatted, return_tensors="pt")

        cfg = GenerationConfig(**self._gen_config.to_dict())
        cfg.max_new_tokens = max_new_tokens
        cfg.do_sample = do_sample and temperature > 0.0
        cfg.temperature = temperature if cfg.do_sample else None

        streamer = TextIteratorStreamer(
            self._tokenizer,
            skip_special_tokens=True,
            skip_prompt=True,
            timeout=self._generation_timeout,
        )

        def _run() -> None:
            try:
                self._model.generate(**inputs, generation_config=cfg, streamer=streamer)
            except Exception as exc:  # noqa: BLE001
                logger.error("[OV-MODEL] Streaming generation error: %s", exc, exc_info=True)
            finally:
                # Ensure the consumer loop always terminates even on error.
                try:
                    streamer.end()
                except Exception:  # noqa: BLE001
                    pass

        threading.Thread(target=_run, daemon=True).start()
        return streamer

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def destroy(self) -> None:
        try:
            del self._model
            gc.collect()
            try:
                ctypes.CDLL("libc.so.6").malloc_trim(0)
            except Exception:  # noqa: BLE001
                pass
            logger.info("[OV-MODEL] Model destroyed, GPU memory released")
        except Exception:  # noqa: BLE001
            pass

    def __del__(self) -> None:
        self.destroy()
