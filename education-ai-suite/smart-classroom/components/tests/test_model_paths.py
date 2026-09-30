# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""One place decides where a converted IR lives, so every caller looks alike."""

import os
import sys
from pathlib import Path

_SC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _SC_ROOT not in sys.path:
    sys.path.insert(0, _SC_ROOT)

from utils import model_paths


def test_the_ir_root_is_the_repo_not_the_cwd():
    """Resolved from this file, so a service started elsewhere still finds it."""
    assert model_paths.SC_ROOT == Path(_SC_ROOT)
    assert model_paths.OPENVINO_MODELS_DIR == Path(_SC_ROOT) / "models" / "openvino"


def test_a_hub_id_becomes_its_last_path_segment():
    """``Qwen/Qwen3-VL-8B-Instruct`` must not dig an org directory on disk."""
    path = model_paths.openvino_model_dir("Qwen/Qwen3-VL-8B-Instruct", "int4")
    assert path == model_paths.OPENVINO_MODELS_DIR / "Qwen3-VL-8B-Instruct" / "int4"


def test_the_weight_format_is_case_folded():
    """config.yaml is hand-written; INT4 and int4 are the same directory."""
    assert model_paths.openvino_model_dir("a/b", "INT4") == \
        model_paths.openvino_model_dir("a/b", "int4")


def test_a_bare_name_needs_no_org():
    assert model_paths.openvino_model_dir("whisper-small", "int8").name == "int8"
    assert model_paths.openvino_model_dir("whisper-small", "int8").parent.name == \
        "whisper-small"


# ------------------------------------------------ the configured text_gen model

def test_the_text_gen_dir_follows_the_config():
    from utils.config_loader import config

    text_gen = config.models.text_gen
    assert model_paths.text_gen_model_dir() == model_paths.openvino_model_dir(
        str(text_gen.vlm_name), str(text_gen.weight_format)
    )


def test_the_text_gen_dir_is_none_when_the_config_says_nothing(monkeypatch):
    """text_chunker treats None as 'size the KV cache from the default'."""
    from utils.config_loader import config

    monkeypatch.setattr(config.models, "text_gen", None, raising=False)
    assert model_paths.text_gen_model_dir() is None


def test_vlm_text_gen_resolves_its_dir_through_this_module():
    """The duplicate path arithmetic in VLMTextGen was replaced by this call."""
    from components.vlm.text_gen_vlm import VLMTextGen

    handler = VLMTextGen.__new__(VLMTextGen)
    handler._model_name = "Qwen/Qwen3-VL-8B-Instruct"
    handler._weight_format = "int4"

    assert handler._model_dir() == model_paths.openvino_model_dir(
        "Qwen/Qwen3-VL-8B-Instruct", "int4"
    )
