# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Context-length aware prompt rendering for the ``text_gen`` VLM.

The Qwen3.x native VLMs (Qwen3.8-27B, Qwen3.6-35B-A3B, Qwen3.5-9B) support very
long contexts -- 262k positions, bounded here to a default 160k tokens by
``models.text_gen.context_length``, which keeps KV-cache growth in check on a
single GPU. On CPU/GPU
the pipeline uses dynamic shapes, so there is no runtime knob for the context
limit; we bound it here at build time instead by trimming the user content to
fit the configured budget.
"""

import logging
from utils.config_loader import config

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_LENGTH = 160000


def _text_gen_config():
    return getattr(config.models, "text_gen", None)


def text_gen_context_length() -> int:
    """Configured text_gen context length (tokens), defaulting to 160k."""
    text_gen = _text_gen_config()
    if text_gen is None:
        return DEFAULT_CONTEXT_LENGTH
    return getattr(text_gen, "context_length", DEFAULT_CONTEXT_LENGTH)


def render_prompt_within_budget(tokenizer, messages, max_input_tokens, **template_kwargs):
    """Render a chat-templated prompt, trimming the last user message so the whole
    prompt fits within ``max_input_tokens``.

    The system prompt and chat-template structure are preserved; only the tail of
    the user content (e.g. the oldest transcript text) is dropped when the prompt
    would otherwise exceed the configured context length. Returns the prompt string.
    """
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, **template_kwargs)
    if not max_input_tokens or max_input_tokens <= 0:
        return prompt

    token_count = len(tokenizer.encode(prompt))
    if token_count <= max_input_tokens:
        return prompt

    # Find the last user turn to trim; leave system/instruction turns intact.
    user_idx = next(
        (i for i in range(len(messages) - 1, -1, -1) if messages[i].get("role") == "user"),
        None,
    )
    if user_idx is None:
        logger.warning(
            "Prompt (%d tokens) exceeds context budget (%d) but has no user message "
            "to trim; passing through unchanged.", token_count, max_input_tokens,
        )
        return prompt

    overflow = token_count - max_input_tokens
    content = messages[user_idx].get("content", "") or ""
    content_ids = tokenizer.encode(content, add_special_tokens=False)
    # Drop the overflow (plus a small margin for template edges) from the end of the
    # user content, keeping the earliest content.
    margin = 8
    keep = max(0, len(content_ids) - overflow - margin)
    dropped = len(content_ids) - keep
    truncated_content = tokenizer.decode(content_ids[:keep], skip_special_tokens=True)

    trimmed = list(messages)
    trimmed[user_idx] = {**messages[user_idx], "content": truncated_content}
    prompt = tokenizer.apply_chat_template(trimmed, tokenize=False, **template_kwargs)

    logger.warning(
        "Prompt exceeded context length: %d > %d tokens. Trimmed user content by "
        "%d of %d tokens to fit.", token_count, max_input_tokens, dropped, len(content_ids),
    )
    return prompt


def render_summarizer_prompt(tokenizer, messages):
    """Render the standard summarizer/mindmap/segmentation prompt (thinking off,
    generation prompt appended) bounded by the configured context length, reserving
    room for ``max_new_tokens`` of generation.

    The result is already chat-templated, so callers must pass
    ``pre_templated=True`` to ``generate()`` to stop ``VLMPipeline`` templating it
    a second time.
    """
    context_length = text_gen_context_length()
    text_gen = _text_gen_config()
    max_new_tokens = getattr(text_gen, "max_new_tokens", 0) or 0 if text_gen else 0
    max_input_tokens = context_length - max_new_tokens if context_length else 0
    return render_prompt_within_budget(
        tokenizer,
        messages,
        max_input_tokens,
        add_generation_prompt=True,
        enable_thinking=False,
    )
