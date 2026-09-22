# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Model-family checks for the ``text_gen`` VLM.

Qwen3 comes in two shapes that need different prompting, and both match a naive
``"qwen3" in name`` test:

* **Dense** (Qwen3-8B, Qwen3-VL-8B-Instruct) — honours the ``/no_think`` soft
  switch in the user turn, and emits no thinking when it is present.
* **MoE VLM** (Qwen3.5-9B, Qwen3.6-35B-A3B; HF ``model_type: qwen3_5_moe``) —
  ignores ``/no_think`` and controls reasoning solely through the chat
  template's ``enable_thinking`` flag.
"""

# Substrings identifying the Qwen3.5 / Qwen3.6 MoE vision-language family.
_QWEN3_MOE_VLM_MARKERS = ("qwen3.5", "qwen3.6")


def is_qwen3_moe_vlm(model_name) -> bool:
    name = str(model_name).lower()
    return any(marker in name for marker in _QWEN3_MOE_VLM_MARKERS)


def is_qwen3_dense(model_name) -> bool:
    name = str(model_name).lower()
    return "qwen3" in name and not is_qwen3_moe_vlm(name)
