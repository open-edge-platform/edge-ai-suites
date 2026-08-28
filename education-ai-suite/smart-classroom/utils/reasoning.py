# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Single source of truth for ``models.text_gen.reasoning_effort``.

The Qwen3.x chat templates gate reasoning on two independent variables:

* ``enable_thinking`` — ``false`` prefills an empty ``<think>\\n\\n</think>`` pair
  into the generation prompt so the model answers directly; undefined or
  ``true`` prefills a bare ``<think>\\n`` and lets the model reason first.
* ``reasoning_effort`` — ``low`` | ``medium`` | ``xhigh`` (Qwen3.8 only,
  defaulting to ``xhigh``), selecting the reasoning instructions injected into
  the system turn. Any other value makes the template raise.

Smart Classroom drives both from the single ``models.text_gen.reasoning_effort``
knob: set it to a valid effort and thinking is ON at that budget on every path
that renders a prompt; leave it ``Null`` and thinking stays off, which is the
behaviour the app had before Qwen3.8 was selectable. Only models whose
:mod:`utils.model_family` profile declares reasoning-effort support (today
``Qwen/Qwen3.8-27B``) honour the knob — for Qwen3.5/3.6 and the Qwen3 dense
models it resolves to ``None``.

Because the template prefills the opening ``<think>``, generated text starts
*inside* the reasoning block and only ever carries the closing tag;
:func:`utils.markdown_cleaner.strip_think_tokens` and
:class:`utils.markdown_cleaner.StreamThinkFilter` handle that shape.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from utils.model_family import supports_reasoning_effort

logger = logging.getLogger(__name__)

# Reasoning budgets accepted by the Qwen3.8 chat template. Its default is
# "xhigh"; anything outside this set makes the template raise.
REASONING_EFFORTS = ("low", "medium", "xhigh")

# YAML renders an unset value as None, but hand-edited configs and env overrides
# routinely arrive as these strings instead.
_UNSET_LITERALS = ("", "null", "none", "false", "off")


@lru_cache(maxsize=8)
def resolve_reasoning_effort(configured, model_name) -> Optional[str]:
    """Validate ``configured`` against ``model_name``, or ``None`` when unset.

    Cached so an unsupported value warns once rather than on every request.
    """
    if configured is None:
        return None
    effort = str(configured).strip().lower()
    if effort in _UNSET_LITERALS:
        return None
    if not supports_reasoning_effort(model_name):
        logger.info(
            "Ignoring models.text_gen.reasoning_effort=%r: %s does not support a "
            "reasoning budget; thinking stays off.",
            configured,
            model_name,
        )
        return None
    if effort not in REASONING_EFFORTS:
        logger.warning(
            "Ignoring unsupported models.text_gen.reasoning_effort=%r; expected "
            "one of %s. Thinking stays off.",
            configured,
            ", ".join(REASONING_EFFORTS),
        )
        return None
    return effort


def configured_reasoning_effort() -> Optional[str]:
    """Reasoning effort in force for the configured ``text_gen`` model."""
    try:
        from utils.config_loader import config

        text_gen = getattr(config.models, "text_gen", None)
    except Exception:  # noqa: BLE001 - config unavailable (tests, tooling)
        return None
    if text_gen is None:
        return None
    return resolve_reasoning_effort(
        getattr(text_gen, "reasoning_effort", None),
        getattr(text_gen, "vlm_name", None),
    )


def thinking_template_kwargs(enable_thinking: Optional[bool] = None) -> dict:
    """Chat-template kwargs for a caller that renders its own prompt.

    ``enable_thinking=False`` forces reasoning off (used where a reasoning pass
    would be wasted or actively harmful — schema-constrained decoding, grading).
    ``True`` forces it on. ``None`` — the usual case — defers to
    ``models.text_gen.reasoning_effort``: thinking is on at that budget when one
    is configured and the model supports it, off otherwise.
    """
    if enable_thinking is False:
        return {"enable_thinking": False}
    effort = configured_reasoning_effort()
    if effort:
        return {"enable_thinking": True, "reasoning_effort": effort}
    return {"enable_thinking": bool(enable_thinking)}


def thinking_enabled(enable_thinking: Optional[bool] = None) -> bool:
    """Whether :func:`thinking_template_kwargs` would leave reasoning on.

    Streaming callers need this to know that the prompt ends with an open
    ``<think>``, so their :class:`~utils.markdown_cleaner.StreamThinkFilter`
    must start inside the block.
    """
    return thinking_template_kwargs(enable_thinking).get("enable_thinking") is True
