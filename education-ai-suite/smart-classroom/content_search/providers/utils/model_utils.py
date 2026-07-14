# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared helpers for converted OpenVINO models on disk.

These are cross-provider concerns: model-IR readiness gates conversion in
``vlm_openvino_serving`` and model loading in ``file_ingest_and_retrieve``, and
the max input length caps tokenization for the encoder pipelines used by
``file_ingest_and_retrieve``. Single definitions here keep those callers
consistent.
"""

import json
import re
from pathlib import Path
from typing import Optional, Union

# Matches the model IR filename produced by the OpenVINO export
# (e.g. ``openvino_model.xml``, ``openvino_language_model.xml``).
_MODEL_IR_RE = re.compile(r"(.*)?openvino(.*)?_model(.*)?\.xml$")

# The OV tokenizer IR filename written by ``convert_tokenizer`` / ``ov.save_model``.
_TOKENIZER_IR_NAME = "openvino_tokenizer.xml"

# The OV detokenizer IR filename. Only generative models (llm/vlm) need this,
# since ``Tokenizer::decode`` requires it to turn generated ids back into text.
_DETOKENIZER_IR_NAME = "openvino_detokenizer.xml"

# Fallback when a model exposes no usable length metadata; 512 is the standard
# BERT/XLM-R context and a safe default for sentence-encoder models.
_DEFAULT_MAX_LENGTH = 512

# RoBERTa-family models reserve position ids ``0..pad_token_id`` and start real
# positions at ``pad_token_id + 1``, so usable length is offset below
# ``max_position_embeddings``.
_ROBERTA_MODEL_TYPES = {"roberta", "xlm-roberta", "camembert", "xlm-roberta-xl"}


def is_model_ready(model_dir: Path, require_detokenizer: bool = False) -> bool:
    """Return True only if the required converted IR files exist.

    Args:
        model_dir (Path): The directory where the converted model is stored.
        require_detokenizer (bool): When True, also require the detokenizer IR.
            Generative models (llm/vlm) call ``Tokenizer::decode`` and therefore
            need ``openvino_detokenizer.xml``; encoder-only models do not.
    Returns:
        bool: True if the model IR, tokenizer IR (and detokenizer IR when
        required) are all present.
    """
    if not model_dir.exists():
        return False
    xml_names = [p.name for p in model_dir.rglob("*.xml")]
    has_model = any(_MODEL_IR_RE.search(name) for name in xml_names)
    has_tokenizer = _TOKENIZER_IR_NAME in xml_names
    has_detokenizer = (not require_detokenizer) or (_DETOKENIZER_IR_NAME in xml_names)
    return has_model and has_tokenizer and has_detokenizer


def _read_json(path: Path) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def resolve_model_max_length(
    model_dir: Union[str, Path], default: int = _DEFAULT_MAX_LENGTH
) -> int:
    """Return the max input token length an encoder model accepts.

    Encoder models (BERT / XLM-R) have a fixed position-embedding table; feeding
    a longer sequence overflows it and crashes at inference ("Eltwise shape infer
    ... mismatch"). Capping tokenization to this value mirrors HuggingFace's
    ``truncation=True`` behaviour.

    Resolution order:
      1. The tokenizer's ``model_max_length`` (HF's own truncation source of
         truth) when present and plausible.
      2. ``max_position_embeddings`` from the model config, adjusted for the
         RoBERTa-family position offset.
      3. ``default``.

    Args:
        model_dir: Directory holding the converted model's ``config.json`` /
            ``tokenizer_config.json``.
        default: Value returned when no usable metadata is found.
    """
    model_dir = Path(model_dir)

    # HF stores a huge sentinel (e.g. 1e30) when model_max_length is unset;
    # ignore implausible values.
    tokenizer_config = _read_json(model_dir / "tokenizer_config.json") or {}
    model_max_length = tokenizer_config.get("model_max_length")
    if isinstance(model_max_length, (int, float)) and 0 < model_max_length <= 100_000:
        return int(model_max_length)

    config = _read_json(model_dir / "config.json") or {}
    max_pos = config.get("max_position_embeddings")
    if isinstance(max_pos, int) and 0 < max_pos <= 100_000:
        model_type = str(config.get("model_type", "")).lower()
        if model_type in _ROBERTA_MODEL_TYPES:
            pad_token_id = config.get("pad_token_id")
            pad_token_id = pad_token_id if isinstance(pad_token_id, int) else 1
            return max_pos - (pad_token_id + 1)
        return max_pos

    return default
