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

from utils.chat_prompt import render_chat_prompt
from utils.markdown_cleaner import StreamThinkFilter, strip_think_tokens
from utils.ov_genai_util import YieldingTextStreamer

logger = logging.getLogger(__name__)

_SC_ROOT = Path(__file__).resolve().parents[2]
_CONTENT_SEARCH_DIR = _SC_ROOT / "content_search"

_DEFAULT_MAX_NEW_TOKENS = 5120


def _filtered(tokens: Iterator[str]) -> Iterator[str]:
    """Drop reasoning from a token stream, suppressing now-empty chunks."""
    think_filter = StreamThinkFilter()
    for token in tokens:
        clean = think_filter.filter(token)
        if clean:
            yield clean


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
            # Think tags are ordinary vocabulary entries in every Qwen3 family,
            # so the streamer decodes them intact. Marking them special would
            # make skip_special_tokens drop the tags while keeping the reasoning
            # text between them, leaving nothing for StreamThinkFilter to match.
            self.tokenizer = AutoTokenizer.from_pretrained(
                str(model_dir), extra_special_tokens={}
            )
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
        prompt: Optional[str] = None,
        *,
        messages: Optional[list] = None,
        images: Optional[list] = None,
        stream: bool = True,
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        enable_thinking: Optional[bool] = None,
        json_schema: Optional[str] = None,
    ) -> Union[Iterator[str], str]:
        """Generate from a chat history using the warm pipeline.

        Mirrors ``TextGen.generate``: streaming yields decoded token chunks,
        non-streaming returns the full string.

        Pass ``messages`` (a chat history) or ``prompt`` (a single user turn),
        never both. Either way this method owns the templating, so callers must
        not run ``apply_chat_template`` themselves -- doing so would wrap the
        rendered string in a second user turn, burying the ``<think></think>``
        prefill and bringing reasoning back.

        ``images`` (a list of ``ov.Tensor`` frames, already decoded by the
        caller) enables the multimodal path used by content-search video
        summarization; when omitted the call is text-only.
        ``enable_thinking=False`` suppresses Qwen3 thinking and strips any
        reasoning that slips through; ``None`` keeps the model default.
        ``json_schema`` (a JSON-schema string) constrains decoding to output
        matching that schema.
        """
        if self._pipe is None:
            raise RuntimeError("VLM pipeline is not loaded")
        if (messages is None) == (prompt is None):
            raise ValueError("Provide exactly one of prompt or messages.")
        if messages is None:
            if not prompt.strip():
                raise ValueError("Invalid prompt provided.")
            messages = [{"role": "user", "content": prompt}]
        elif not messages:
            raise ValueError("Invalid messages provided.")

        config = self._generation_config(max_new_tokens, temperature, json_schema)
        prompt = self._render(messages, config, enable_thinking, bool(images))

        if stream:
            tokens = self._generate_stream(prompt, config, images)
            return _filtered(tokens) if enable_thinking is False else tokens
        if images:
            raw = str(
                self._pipe.generate(prompt, images=images, generation_config=config)
            )
        else:
            raw = str(self._pipe.generate(prompt, generation_config=config))
        return strip_think_tokens(raw) if enable_thinking is False else raw

    def _render(
        self,
        messages: list,
        config: "ov_genai.GenerationConfig",
        enable_thinking: Optional[bool],
        has_images: bool,
    ) -> str:
        """Render ``messages`` here rather than inside the pipeline.

        Keeping templating on this side means one engine and one set of rules
        for every caller. The pipeline only takes over for a model that has no
        chat template at all, where rendering is impossible.
        """
        try:
            prompt = render_chat_prompt(
                self.tokenizer,
                messages,
                self._model_name,
                enable_thinking,
                has_images,
            )
            config.apply_chat_template = False
            return prompt
        except Exception as exc:  # noqa: BLE001 - model without a chat template
            logger.warning(
                "Chat template rendering failed (%s); letting the pipeline "
                "template the last user turn.", exc
            )
            config.apply_chat_template = True
            return str(messages[-1].get("content", ""))

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
