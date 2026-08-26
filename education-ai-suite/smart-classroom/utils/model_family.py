# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Model-family checks for the ``text_gen`` VLM.

Qwen3 comes in two shapes that need different prompting, and both match a naive
``"qwen3" in name`` test:

* **Dense** (Qwen3-8B, Qwen3-VL-8B-Instruct) — honours the ``/no_think`` soft
  switch in the user turn, and emits no thinking when it is present.
* **Native VLM** (Qwen3.5-9B, Qwen3.6-35B-A3B, Qwen3.8-27B; HF ``model_type``
  ``qwen3_5`` or ``qwen3_5_moe``) — ignores ``/no_think`` and controls reasoning
  solely through the chat template's ``enable_thinking`` flag. Qwen3.5/3.6 are
  MoE and Qwen3.8-27B is a dense hybrid-attention model, but all three share the
  same qwen3_5 export path and the same prompting contract.
"""

# Substrings identifying the Qwen3.5 / Qwen3.6 / Qwen3.8 native vision-language
# family. Matched against the lowercased model name, so "qwen3.8" also covers
# any future Qwen3.8-<size> member.
_QWEN3_NATIVE_VLM_MARKERS = ("qwen3.5", "qwen3.6", "qwen3.8")


def is_qwen3_native_vlm(model_name) -> bool:
    """Whether ``model_name`` is a Qwen3.5 / Qwen3.6 / Qwen3.8 native VLM.

    These are multimodal even when used text-only, and must be exported with the
    image-text-to-text task and run through ``VLMPipeline``.
    """
    name = str(model_name).lower()
    return any(marker in name for marker in _QWEN3_NATIVE_VLM_MARKERS)


# Kept for callers written before Qwen3.8-27B joined this family as its first
# non-MoE member.
is_qwen3_moe_vlm = is_qwen3_native_vlm


def is_qwen3_dense(model_name) -> bool:
    """Whether ``model_name`` is a Qwen3 dense model (``/no_think`` applies)."""
    name = str(model_name).lower()
    return "qwen3" in name and not is_qwen3_native_vlm(name)
