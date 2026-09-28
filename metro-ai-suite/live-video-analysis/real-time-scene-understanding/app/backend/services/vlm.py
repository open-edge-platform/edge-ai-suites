# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""OpenVINO GenAI vision-language captioning engine.

A single :class:`VLMEngine` wraps one ``openvino_genai.VLMPipeline``. The model
is heavy and not safe to call concurrently, so all requests are served one at a
time by a single dispatcher thread from a priority queue: alert-driven streams
are served ahead of passive ones, FIFO within each tier, instead of racing for
a lock with no ordering guarantee.

The model tree is laid out per device as
``<VLM_MODELS_DIR>/<device>/<VLM_MODEL>`` (e.g. ``/models/cpu/InternVL2-1B``),
matching how the models are mounted into the container.
"""

from __future__ import annotations

import itertools
import json
import logging
import os
import queue
import re
import threading
import time
from typing import Any
from typing import Optional

import numpy as np
import openvino as ov
import openvino_genai as ov_genai

from ..config import settings
from . import utils

logger = logging.getLogger(__name__)

# JSON schema enforced on every VLM generation via StructuredOutputConfig, so the
# model can only ever emit a valid {"decision": "Yes"|"No", "description": str}
# object instead of free-form text that needs parsing.
# The field is named 'decision' (not 'threat') so its meaning is "does the
# prompt's described event match?" -- a 'threat' key biases the model toward
# judging danger instead of answering the prompt's actual visibility question.
# NOTE: StructuredOutputConfig is grammar-constrained decoding -- it enforces
# type/enum/maxLength at the token level but does not surface each property's
# JSON-schema 'description' text to the model. Anything the model actually
# needs to know about what 'decision' means has to be in the plain-text prompt
# (see _RESPONSE_FORMAT_SUFFIX), not just in the schema's metadata.
# description's maxLength is derived from ALERT_VLM_MAX_TOKENS (see
# _build_alert_verdict_schema), not fixed, so it never asks for more text than
# the configured token budget can actually finish writing.

# Rough English chars-per-token used to size description's maxLength; only
# needs to be in the right ballpark since it just bounds worst-case length.
_CHARS_PER_TOKEN = 4
# Tokens reserved for the 'decision' field plus JSON punctuation/keys, leaving
# the remainder of ALERT_VLM_MAX_TOKENS for the description text itself.
_JSON_OVERHEAD_TOKENS = 20

# Appended (visibly, in-prompt) to every alert prompt so 'decision' is tied to
# whatever question the prompt itself ends on, instead of the model guessing
# a meaning for the JSON key from training-data conventions. 'decision' is
# scoped to the prompt's own question answered against the image directly --
# not derived from re-reading 'description' -- so it isn't hostage to whatever
# wording the model happened to use for the free-text description.
_RESPONSE_FORMAT_SUFFIX = (
    "\n\nRespond with JSON only. Fill 'description' first, following the "
    "instructions above. Then fill 'decision' by directly answering, from the "
    "image itself, the specific yes/no question asked in the instructions "
    "above."
)


def _build_alert_verdict_schema(max_new_tokens: int) -> dict[str, Any]:
    """Build ALERT_VERDICT_SCHEMA with a description cap sized to max_new_tokens.

    A fixed maxLength would either be reached before max_new_tokens (wasting
    budget) or, if max_new_tokens is lowered below what the cap needs, force
    truncation before the JSON can close. Sizing it off the actual token
    budget keeps the two consistent regardless of configuration.
    """
    available_tokens = max(max_new_tokens - _JSON_OVERHEAD_TOKENS, 5)
    max_length = available_tokens * _CHARS_PER_TOKEN
    # 'description' is listed (and thus generated) before 'decision': structured
    # output fills object keys in property order, so putting the verdict first
    # would force the model to commit Yes/No before it has "reasoned" through
    # what's actually visible, decoupling the decision from its own description.
    return {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "One short sentence describing only what is visibly relevant to the prompt's question.",
                "maxLength": max_length,
            },
            "decision": {
                "type": "string",
                "enum": ["Yes", "No"],
                "description": "Yes if the image confirms the prompt's question; No otherwise.",
            },
        },
        "required": ["description", "decision"],
        "additionalProperties": False,
    }


def _parse_alert_verdict(raw_text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (decision, description) from the model's JSON output.

    Parses the substring between the first '{' and last '}' (tolerates stray
    characters GenAI occasionally emits around it, e.g. a lone "!"). Returns
    (None, None) if that substring isn't valid JSON with both fields present
    -- e.g. generation got cut off by max_new_tokens before the object closed
    -- since a partial verdict isn't reliable enough to show or act on.
    """
    text = str(raw_text or "")
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None, None

    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None, None

    if not isinstance(data, dict):
        return None, None

    decision = data.get("decision")
    description = data.get("description")
    if not isinstance(decision, str) or not isinstance(description, str):
        return None, None
    return decision, description


def parse_yes_no(caption: str) -> Optional[bool]:
    """Parse the 'Decision: Yes/No' line of a formatted alert caption into a bool.

    Operates on the display string produced by VLMEngine._format_alert_caption
    (not the raw model JSON). Returns None when no verdict line is present.
    """
    match = re.search(r"\bdecision\s*:\s*(yes|no)\b", str(caption or ""), flags=re.IGNORECASE)
    if match is None:
        return None
    return match.group(1).lower() == "yes"


class _CaptionRequest:
    """One queued captioning request; the submitting thread blocks on `event`."""

    __slots__ = ("rgb_frame", "prompt", "event", "result", "error")

    def __init__(self, rgb_frame: np.ndarray, prompt: str) -> None:
        self.rgb_frame = rgb_frame
        self.prompt = prompt
        self.event = threading.Event()
        self.result: Optional[tuple[Optional[str], dict[str, Optional[float]]]] = None
        self.error: Optional[BaseException] = None


class VLMEngine:
    """Thread-safe wrapper around an OpenVINO GenAI VLM pipeline."""

    def __init__(self) -> None:
        self._pipe = None
        self._gen_config = None
        self._model_path = os.path.join(
            settings.VLM_MODELS_DIR,
            settings.ALERT_VLM_DEVICE.lower(),
            settings.ALERT_VLM_MODEL,
        )
        self._load()
        self._metrics_debug_logged = False

        # Priority queue of (rank, seq, request): rank 0 = alert-priority lane,
        # rank 1 = normal lane; seq preserves FIFO order within a lane.
        self._queue: "queue.PriorityQueue[tuple[int, int, _CaptionRequest]]" = queue.PriorityQueue()
        self._seq_counter = itertools.count()
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop, name="vlm-dispatch", daemon=True
        )
        self._dispatch_thread.start()

    def _load(self) -> None:
        # Imported lazily so the app still starts if GenAI is unavailable.
        if not os.path.isdir(self._model_path):
            raise FileNotFoundError(f"VLM model not found at '{self._model_path}'")

        logger.info(
            "Loading VLM '%s' on %s from %s",
            settings.ALERT_VLM_MODEL,
            settings.ALERT_VLM_DEVICE,
            self._model_path,
        )
        pipeline_config = None
        if str(settings.ALERT_VLM_DEVICE).upper() == "NPU":
            pipeline_config = {
                "MAX_PROMPT_LEN": settings.NPU_MAX_PROMPT_LEN,
                "MIN_RESPONSE_LEN": settings.NPU_MIN_RESPONSE_LEN,
            }

        if pipeline_config is None:
            self._pipe = ov_genai.VLMPipeline(self._model_path, settings.ALERT_VLM_DEVICE)
        else:
            self._pipe = ov_genai.VLMPipeline(
                self._model_path,
                settings.ALERT_VLM_DEVICE,
                **pipeline_config,
            )
        self._gen_config = ov_genai.GenerationConfig()
        self._gen_config.max_new_tokens = settings.ALERT_VLM_MAX_TOKENS
        if hasattr(self._gen_config, "do_sample"):
            self._gen_config.do_sample = settings.ALERT_VLM_DO_SAMPLE
        # Constrains generation to a schema sized off ALERT_VLM_MAX_TOKENS so the
        # output is always valid JSON that finishes within budget, never free
        # text that needs best-effort regex parsing.
        self._gen_config.structured_output_config = ov_genai.StructuredOutputConfig(
            json_schema=json.dumps(_build_alert_verdict_schema(settings.ALERT_VLM_MAX_TOKENS))
        )
        logger.info("VLM pipeline ready")

    @staticmethod
    def _extract_caption_text(result: Any) -> str:
        # GenAI result often carries `texts`; fall back to string conversion.
        texts = getattr(result, "texts", None)
        if isinstance(texts, (list, tuple)) and texts:
            return str(texts[0]).strip()
        return str(result).strip()

    @staticmethod
    def _format_alert_caption(raw_text: str) -> Optional[str]:
        """Render the schema-constrained JSON verdict as a 'Decision: .. / Description: ..' string.

        Returns None if the output wasn't a complete, valid verdict (e.g.
        truncated mid-description) -- callers should drop the response for
        this cycle rather than show a partial/malformed result.
        """
        decision, description = _parse_alert_verdict(raw_text)
        if decision is None or description is None:
            return None
        return f"Decision: {decision}\nDescription: {description}"

    def _dispatch_loop(self) -> None:
        """Single worker thread; the only caller of `_generate`, so no lock is needed there."""
        while True:
            _rank, _seq, request = self._queue.get()
            try:
                request.result = self._generate(request.rgb_frame, request.prompt)
            except Exception as exc:  # noqa: BLE001
                request.error = exc
            finally:
                request.event.set()

    def _generate(
        self, rgb_frame: np.ndarray, prompt_text: str
    ) -> tuple[Optional[str], dict[str, Optional[float]]]:
        """Call the GenAI VLM pipeline on one frame and prompt.

        Returns caption=None when the output wasn't a complete, valid verdict
        (see _format_alert_caption) -- callers should drop it for this cycle.
        """
        # GenAI expects a batched NHWC uint8 tensor.
        tensor = ov.Tensor(np.expand_dims(rgb_frame, axis=0))
        t0 = time.perf_counter()
        result = self._pipe.generate(
            prompt_text + _RESPONSE_FORMAT_SUFFIX,
            images=[tensor],
            generation_config=self._gen_config,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        metrics = utils._extract_perf_metrics(result)
        if metrics.get("ttft_ms") is None and not self._metrics_debug_logged:
            self._metrics_debug_logged = True
            logger.warning(
                "VLM result has no usable perf_metrics; falling back to estimated metrics"
            )

        caption_text = self._format_alert_caption(self._extract_caption_text(result))
        return caption_text, metrics

    def caption_with_metrics(
        self,
        rgb_frame: np.ndarray,
        prompt: Optional[str] = None,
        *,
        priority: bool = False,
    ) -> tuple[Optional[str], dict[str, Optional[float]]]:
        """Queue a captioning request and block until served.

        `priority=True` (e.g. alert-driven streams) is served ahead of normal
        requests; ordering within each tier is FIFO. Caption is None when the
        response was truncated/malformed (see _format_alert_caption).
        """
        prompt_text = (prompt or "").strip()
        if not prompt_text:
            raise ValueError("prompt is required")

        request = _CaptionRequest(rgb_frame, prompt_text)
        rank = 0 if priority else 1
        self._queue.put((rank, next(self._seq_counter), request))
        request.event.wait()

        if request.error is not None:
            raise request.error
        if request.result is None:
            raise RuntimeError(
                "Internal error: caption worker signalled completion without a "
                "result or an error."
            )
        return request.result

    def caption(self, rgb_frame: np.ndarray, prompt: Optional[str] = None) -> Optional[str]:
        """Return a caption for one RGB frame (H×W×3, uint8), or None if truncated/malformed."""
        caption_text, _metrics = self.caption_with_metrics(rgb_frame, prompt=prompt)
        return caption_text


_engine: Optional[VLMEngine] = None
_engine_lock = threading.Lock()


def get_vlm_engine() -> VLMEngine:
    """Return the shared VLM engine, loading it once on first use."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = VLMEngine()
    return _engine
