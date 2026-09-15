# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Single place where a chat history becomes a prompt string.

Rendering used to be split between callers (transformers ``AutoTokenizer``),
``VLMTextGen`` (the OpenVINO tokenizer) and ``VLMPipeline`` itself, so whether
thinking was suppressed depended on which of the three ran. Everything routes
through :func:`render_chat_prompt` now, which owns the three knobs that differ
per model family:

* the ``<ov_genai_image_0>`` media tag the multimodal pipeline expects,
* the ``/no_think`` soft switch, honoured only by dense Qwen3,
* the chat template's ``enable_thinking`` flag.
"""

import logging
from typing import Optional

import openvino_genai as ov_genai

from utils.model_family import is_qwen3_dense

logger = logging.getLogger(__name__)

# Placeholder the OpenVINO VLM pipeline substitutes with the first image tensor.
MEDIA_TAG = "<ov_genai_image_0>"

_NO_THINK = "/no_think"


def render_chat_prompt(
    tokenizer,
    messages: list,
    model_name,
    enable_thinking: Optional[bool] = None,
    has_images: bool = False,
) -> str:
    """Render ``messages`` into a prompt string ready for ``generate``.

    ``enable_thinking`` is tri-state: ``None`` leaves the model default alone,
    ``False`` suppresses reasoning, ``True`` requests it. Models whose template
    predates the flag (Qwen2.x, Qwen3-VL-*-Instruct) simply ignore it -- extra
    kwargs reach the Jinja renderer as variables and go unused.

    Works with both a transformers tokenizer and the OpenVINO one, which take
    the same information through incompatible signatures.
    """
    messages = _prepare(messages, model_name, enable_thinking, has_images)
    extra = {} if enable_thinking is None else {"enable_thinking": enable_thinking}

    if isinstance(tokenizer, ov_genai.Tokenizer):
        return _render_ov(tokenizer, messages, extra)
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True, **extra
    )


def _prepare(
    messages: list, model_name, enable_thinking: Optional[bool], has_images: bool
) -> list:
    """Copy ``messages`` with the media tag and ``/no_think`` switch applied."""
    prepared = [dict(m) for m in messages]

    if has_images:
        first_user = _find_user(prepared)
        if first_user is not None:
            prepared[first_user]["content"] = (
                MEDIA_TAG + str(prepared[first_user]["content"])
            )

    # Dense Qwen3 obeys the soft switch in the user turn; the MoE VLMs ignore it
    # and go by the template flag alone, so adding it there is just noise.
    # Applied after the media tag so the directive stays at position 0, the way
    # Qwen documents it; the tag is matched anywhere in the turn.
    if enable_thinking is False and is_qwen3_dense(model_name):
        last_user = _find_user(prepared, last=True)
        if last_user is not None:
            content = str(prepared[last_user]["content"])
            if not content.lstrip().startswith(_NO_THINK):
                prepared[last_user]["content"] = f"{_NO_THINK}\n{content}"

    return prepared


def _find_user(messages: list, last: bool = False) -> Optional[int]:
    indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    if not indices:
        return None
    return indices[-1] if last else indices[0]


def _render_ov(tokenizer, messages: list, extra: dict) -> str:
    """Render via the OpenVINO tokenizer.

    Its signature is positional -- ``(history, add_generation_prompt,
    chat_template, tools, extra_context)`` -- and ``extra_context`` only exists
    on recent runtimes, so fall back to the three-argument form.
    """
    try:
        return tokenizer.apply_chat_template(messages, True, "", None, extra or None)
    except TypeError:
        if extra:
            logger.warning(
                "OpenVINO tokenizer does not accept extra_context; %s will be "
                "ignored and the model default applies.", extra
            )
        return tokenizer.apply_chat_template(messages, True, "")
