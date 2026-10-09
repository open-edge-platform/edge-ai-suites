# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared pytest fixtures.

Also installs minimal stand-ins for the optional native/ML dependencies
(PyAV, OpenVINO, OpenVINO GenAI) when the real packages aren't installed.
These libraries need real hardware/model artifacts to actually *run*, but
several backend modules import them at module scope; the stubs only exist so
those modules can be imported for testing pure Python logic (e.g.
``parse_yes_no``, ``_calculate_scaled_dimensions``) without requiring the
full GPU/NPU toolchain. If the real packages are installed (e.g. inside the
project's Docker image), they are imported as-is and these stubs are never
used.
"""

from __future__ import annotations

import sys
import types


def _stub_module(name: str) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    return module


def _install_av_stub() -> None:
    try:
        import av  # noqa: F401

        return
    except ImportError:
        pass

    class _Interpolation:
        BILINEAR = "bilinear"
        AREA = "area"

    def _unavailable_open(*_args, **_kwargs):
        raise RuntimeError("PyAV ('av') is not installed in this test environment")

    reformatter_module = _stub_module("av.video.reformatter")
    reformatter_module.Interpolation = _Interpolation

    video_module = _stub_module("av.video")
    video_module.reformatter = reformatter_module

    av_module = _stub_module("av")
    av_module.video = video_module
    av_module.open = _unavailable_open


def _install_openvino_stub() -> None:
    try:
        import openvino  # noqa: F401

        return
    except ImportError:
        pass

    class _Unavailable:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("openvino is not installed in this test environment")

    ov_module = _stub_module("openvino")
    ov_module.Tensor = _Unavailable


def _install_openvino_genai_stub() -> None:
    try:
        import openvino_genai  # noqa: F401

        return
    except ImportError:
        pass

    class _VLMDecodedResults:
        """Placeholder referenced by utils._extract_perf_metrics' type hint."""

    class _Unavailable:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("openvino_genai is not installed in this test environment")

    py_ov_genai_module = _stub_module("openvino_genai.py_openvino_genai")
    py_ov_genai_module.VLMDecodedResults = _VLMDecodedResults

    ov_genai_module = _stub_module("openvino_genai")
    ov_genai_module.py_openvino_genai = py_ov_genai_module
    ov_genai_module.VLMPipeline = _Unavailable
    ov_genai_module.GenerationConfig = _Unavailable


_install_av_stub()
_install_openvino_stub()
_install_openvino_genai_stub()
