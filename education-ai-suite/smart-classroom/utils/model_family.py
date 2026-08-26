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

from dataclasses import dataclass
import re
from typing import Optional

# Substrings identifying the Qwen3.5 / Qwen3.6 / Qwen3.8 native vision-language
# family. Matched against the lowercased model name, so "qwen3.8" also covers
# any future Qwen3.8-<size> member.
_QWEN3_NATIVE_VLM_MARKERS = ("qwen3.5", "qwen3.6", "qwen3.8")


@dataclass(frozen=True)
class TextGenModelProfile:
  model_name: str
  weight_formats: tuple[str, ...]
  reasoning_effort: bool = False
  minimum_openvino: Optional[tuple[int, int]] = None
  minimum_openvino_genai: Optional[tuple[int, int]] = None


_TEXT_GEN_MODEL_PROFILES = {
  "qwen/qwen3.6-35b-a3b": TextGenModelProfile(
    model_name="Qwen/Qwen3.6-35B-A3B",
    weight_formats=("int4", "int8"),
  ),
  "qwen/qwen3.8-27b": TextGenModelProfile(
    model_name="Qwen/Qwen3.8-27B",
    weight_formats=("int8",),
    reasoning_effort=True,
    minimum_openvino=(2026, 4),
    minimum_openvino_genai=(2026, 4),
  ),
}


def text_gen_model_profile(model_name) -> Optional[TextGenModelProfile]:
  """Return switching constraints for a known text-gen model."""
  return _TEXT_GEN_MODEL_PROFILES.get(str(model_name).strip().lower())


def supports_reasoning_effort(model_name) -> bool:
  profile = text_gen_model_profile(model_name)
  return bool(profile and profile.reasoning_effort)


def _version_pair(version) -> tuple[int, int]:
  parts = [int(part) for part in re.findall(r"\d+", str(version))]
  return tuple((parts + [0, 0])[:2])


def validate_text_gen_model_config(model_name, device, weight_format) -> None:
  """Validate constraints that differ between selectable text-gen models."""
  profile = text_gen_model_profile(model_name)
  if profile is None:
    return

  normalized_device = str(device).strip().upper()
  normalized_weight = str(weight_format).strip().lower()
  if not normalized_device.startswith("GPU"):
    raise ValueError(
      f"{profile.model_name} is supported by Smart Classroom on GPU; "
      f"configured device={device!r}."
    )
  if normalized_weight not in profile.weight_formats:
    allowed = ", ".join(profile.weight_formats)
    raise ValueError(
      f"{profile.model_name} does not support weight_format={weight_format!r}; "
      f"use one of: {allowed}."
    )

  if profile.minimum_openvino is not None:
    import openvino

    version_parts = _version_pair(openvino.__version__)
    if version_parts < profile.minimum_openvino:
      minimum = ".".join(str(part) for part in profile.minimum_openvino)
      raise RuntimeError(
        f"{profile.model_name} requires OpenVINO {minimum}+; found "
        f"{openvino.__version__}. Install requirements-qwen3.8.txt."
      )

  if profile.minimum_openvino_genai is not None:
    import openvino_genai

    version = getattr(openvino_genai, "__version__", "0.0")
    if _version_pair(version) < profile.minimum_openvino_genai:
      minimum = ".".join(
        str(part) for part in profile.minimum_openvino_genai
      )
      raise RuntimeError(
        f"{profile.model_name} requires OpenVINO GenAI {minimum}+; found "
        f"{version}. Install requirements-qwen3.8.txt."
      )


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
