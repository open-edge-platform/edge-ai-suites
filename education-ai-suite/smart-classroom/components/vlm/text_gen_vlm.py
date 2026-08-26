# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0


from __future__ import annotations

import gc
import logging
import sys
import threading
import time
from pathlib import Path
from typing import Iterator, Optional, Union

import openvino_genai as ov_genai
from transformers import AutoTokenizer

from utils.model_family import is_qwen3_dense
from utils.ov_genai_util import YieldingTextStreamer

logger = logging.getLogger(__name__)

_SC_ROOT = Path(__file__).resolve().parents[2]
_CONTENT_SEARCH_DIR = _SC_ROOT / "content_search"

_DEFAULT_MAX_NEW_TOKENS = 5120

# Reasoning budgets accepted by the Qwen3.8 chat template. Its default is
# "xhigh"; anything outside this set makes the template raise.
_REASONING_EFFORTS = ("low", "medium", "xhigh")


def _import_convert_helpers():
    if str(_CONTENT_SEARCH_DIR) not in sys.path:
        sys.path.append(str(_CONTENT_SEARCH_DIR))
    from components.vlm.vlm_openvino_serving.utils.utils import (  # noqa: E402
        convert_model,
        is_model_ready,
    )

    return convert_model, is_model_ready


class VLMTextGen:
    """Warm ``ov_genai.VLMPipeline`` fronting the ``text_gen`` capability."""

    def __init__(self) -> None:
        self._pipe = None
        self.tokenizer = None
        self._model_name: Optional[str] = None
        self._device: Optional[str] = None
        self._weight_format: Optional[str] = None
        self._max_new_tokens: int = _DEFAULT_MAX_NEW_TOKENS
        self._reasoning_effort: Optional[str] = None
        self._load_config()
        self._load()

    @property
    def device(self) -> Optional[str]:
        return self._device

    @property
    def model_name(self) -> Optional[str]:
        return self._model_name

    def _load_config(self) -> None:
        from utils.config_loader import config

        text_gen = getattr(config.models, "text_gen", None)
        if text_gen is None:
            raise ValueError(
                "models.text_gen is not configured; the warm VLM cannot start"
            )
        self._model_name = str(text_gen.vlm_name)
        self._device = str(text_gen.device).upper()
        self._weight_format = str(text_gen.weight_format).lower()
        self._max_new_tokens = int(
            getattr(text_gen, "max_new_tokens", _DEFAULT_MAX_NEW_TOKENS)
        )
        self._reasoning_effort = self._resolve_reasoning_effort(
            getattr(text_gen, "reasoning_effort", None)
        )

    @staticmethod
    def _resolve_reasoning_effort(configured) -> Optional[str]:
        """Validate ``models.text_gen.reasoning_effort``, or ``None`` if unset."""
        if not configured:
            return None
        effort = str(configured).strip().lower()
        if effort not in _REASONING_EFFORTS:
            logger.warning(
                "Ignoring unsupported models.text_gen.reasoning_effort=%r; "
                "expected one of %s.",
                configured,
                ", ".join(_REASONING_EFFORTS),
            )
            return None
        return effort

    def _model_dir(self) -> Path:
        """Return the shared IR directory ``models/openvino/<name>/<weight>``."""
        short_name = self._model_name.split("/")[-1]
        return _SC_ROOT / "models" / "openvino" / short_name / self._weight_format

    def _ov_config(self) -> dict:
        """Runtime config for the pipeline; large allocations help on GPU."""
        if self._device.startswith("GPU"):
            return {"GPU_ENABLE_LARGE_ALLOCATIONS": "YES"}
        return {}

    def _load(self) -> None:
        model_dir = self._model_dir()
        model_dir.mkdir(parents=True, exist_ok=True)

        convert_model, is_model_ready = _import_convert_helpers()
        if not is_model_ready(model_dir, require_detokenizer=True):
            logger.info(
                "Converting VLM %s -> OpenVINO IR (%s) at %s",
                self._model_name,
                self._weight_format,
                model_dir,
            )
            convert_model(
                self._model_name,
                str(model_dir),
                model_type="vlm",
                weight_format=self._weight_format,
            )

        logger.info(
            "Loading warm VLMPipeline: model=%s device=%s weight=%s",
            self._model_name,
            self._device,
            self._weight_format,
        )
        self._pipe = ov_genai.VLMPipeline(
            str(model_dir), device=self._device, **self._ov_config()
        )
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(
                str(model_dir), extra_special_tokens={}
            )
            if is_qwen3_dense(self._model_name):
                _think_tokens = ["<think>", "</think>"]
                _existing = set(getattr(self.tokenizer, "additional_special_tokens", []) or [])
                _missing = [t for t in _think_tokens if t not in _existing]
                if _missing:
                    self.tokenizer.add_special_tokens({"additional_special_tokens": _missing})
                    logger.info("Registered think tags as special tokens: %s", _missing)
        except Exception as exc:
            logger.warning(
                "transformers AutoTokenizer failed (%s); falling back to the "
                "OpenVINO pipeline tokenizer.", exc
            )
            self.tokenizer = self._pipe.get_tokenizer()
        logger.info("Warm VLM ready.")

    def release(self) -> None:
        """Release the resident pipeline and reclaim device/host memory."""
        try:
            self._pipe = None
            self.tokenizer = None
            gc.collect()
            logger.info("Warm VLM released and memory reclaimed.")
        except Exception:  # noqa: BLE001 - shutdown best-effort
            logger.warning("Failed to fully release warm VLM", exc_info=True)

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------
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
        """Generate from ``prompt`` (optionally multimodal) using the warm pipeline.

        Mirrors ``TextGen.generate``: streaming yields decoded token chunks,
        non-streaming returns the full string. ``images`` (a list of
        ``ov.Tensor`` frames, already decoded by the caller) enables the
        multimodal path used by content-search video summarization; when
        omitted the call is text-only. ``enable_thinking=False`` suppresses
        Qwen3 thinking for this request only; ``None`` keeps the model default,
        capped by ``models.text_gen.reasoning_effort`` where the template
        supports it. ``json_schema`` (a JSON-schema string) constrains decoding
        to output matching that schema.

        ``pre_templated=True`` means ``prompt`` is already a fully rendered chat
        template (see ``utils.prompt_budget.render_summarizer_prompt``), so the
        pipeline must not apply the template again. Without it ``VLMPipeline``
        double-wraps the prompt and re-enables thinking, which shows up as
        reasoning preambles and greedy repetition loops. HTTP callers
        (``/v1/chat/completions``) pass raw prompts and leave this False.
        """
        if self._pipe is None:
            raise RuntimeError("VLM pipeline is not loaded")
        if not prompt or not prompt.strip():
            raise ValueError("Invalid prompt provided.")

        config = self._generation_config(max_new_tokens, temperature, json_schema)
        if pre_templated:
            config.apply_chat_template = False
        else:
            template_kwargs = self._template_kwargs(enable_thinking)
            if template_kwargs:
                prompt = self._apply_chat_template(
                    prompt, config, bool(images), template_kwargs
                )
        if stream:
            return self._generate_stream(prompt, config, images)
        if images:
            return str(
                self._pipe.generate(prompt, images=images, generation_config=config)
            )
        return str(self._pipe.generate(prompt, generation_config=config))

    def _template_kwargs(self, enable_thinking: Optional[bool]) -> dict:
        """Chat-template kwargs for this request, ``{}`` to let the pipeline template.

        ``enable_thinking=False`` turns reasoning off outright. When thinking is
        left at the model default, Qwen3.8's template resolves
        ``reasoning_effort`` to ``xhigh``, which prefixes every answer with a long
        reasoning pass; the configured ``models.text_gen.reasoning_effort`` caps
        that. Templates that predate the flag (Qwen3.5/3.6, Qwen3-VL) ignore the
        key, so passing it is harmless there.
        """
        if enable_thinking is False:
            return {"enable_thinking": False}
        if self._reasoning_effort:
            return {"reasoning_effort": self._reasoning_effort}
        return {}

    def _apply_chat_template(
        self,
        prompt: str,
        config: "ov_genai.GenerationConfig",
        has_images: bool,
        template_kwargs: dict,
    ) -> str:
        try:
            media_tags = "<ov_genai_image_0>" if has_images else ""
            history = [{"role": "user", "content": media_tags + prompt}]
            templated = self._pipe.get_tokenizer().apply_chat_template(
                history, True, "", None, template_kwargs
            )
            config.apply_chat_template = False
            return templated
        except Exception as exc:  # noqa: BLE001 - fall back to the pipeline default
            logger.warning(
                "chat template %s failed (%s); using raw prompt",
                template_kwargs,
                exc,
            )
            return prompt

    def _generation_config(
        self,
        max_new_tokens: Optional[int],
        temperature: Optional[float],
        json_schema: Optional[str] = None,
    ) -> "ov_genai.GenerationConfig":
        max_tokens = (
            int(max_new_tokens) if max_new_tokens is not None else self._max_new_tokens
        )
        kwargs = {"max_new_tokens": max_tokens, "do_sample": False}
        if temperature is not None:
            kwargs["temperature"] = float(temperature)
            kwargs["do_sample"] = float(temperature) > 0.0
        config = ov_genai.GenerationConfig(**kwargs)
        if json_schema:
            try:
                config.structured_output_config = ov_genai.StructuredOutputConfig(
                    json_schema=json_schema
                )
            except Exception as exc:  # noqa: BLE001 - runtime without a grammar backend
                logger.warning(
                    "Structured output unavailable (%s); generating unconstrained.", exc
                )
        return config

    def _generate_stream(
        self,
        prompt: str,
        config: "ov_genai.GenerationConfig",
        images: Optional[list] = None,
    ) -> Iterator[str]:
        """Run generation on a worker thread, yielding tokens as they arrive.

        A memory/runtime error raised during generation is re-raised in the
        consuming thread once the queue drains, so the ``CapabilityRunner`` can
        surface it as an ``OomError`` while keeping the capability resident.
        """
        streamer = YieldingTextStreamer(self.tokenizer)
        error: list[Exception] = []

        def run_generation() -> None:
            try:
                streamer.generation_start_time = time.perf_counter()
                if images:
                    self._pipe.generate(
                        prompt,
                        images=images,
                        generation_config=config,
                        streamer=streamer,
                    )
                else:
                    self._pipe.generate(
                        prompt, generation_config=config, streamer=streamer
                    )
            except Exception as exc:  # noqa: BLE001 - re-raised in the consumer
                logger.error("VLM text_gen streaming failed: %s", exc)
                error.append(exc)
            finally:
                streamer.end()

        threading.Thread(target=run_generation, daemon=True).start()

        def _iterator() -> Iterator[str]:
            for token in streamer:
                yield token
            if error:
                raise error[0]

        return _iterator()
