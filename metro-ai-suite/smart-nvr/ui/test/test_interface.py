# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import types
import threading
from datetime import datetime, timedelta
import sys
import importlib

import gradio as gr
import pytest

# --- Test shim to satisfy interface.py absolute imports --------------------
# interface.py uses un-namespaced imports like `from services.api_client import ...`
# In normal runtime the working directory is `ui/` so Python resolves `services`.
# During test collection from repo root, `services` isn't on sys.path and import fails.
# We map the real ui.services.* modules into a synthetic top-level `services` package.
services_pkg = types.ModuleType("services")
sys.modules.setdefault("services", services_pkg)

for sub in [
    "api_client",
    "video_processor",
    "event_utils",
]:
    try:
        real_mod = importlib.import_module(f"ui.services.{sub}")
        sys.modules[f"services.{sub}"] = real_mod
        setattr(services_pkg, sub, real_mod)
    except ImportError:
        # If a particular submodule is missing we let tests fail later with clearer context
        pass

from ui.interface import interface as iface  # noqa: E402  (import after shim)


class DummyStatusOutput:
    """Lightweight stand-in for a Gradio component for unit testing logic branches."""
    def __init__(self):
        self.value = None


def _get_update_value(obj):
    """Helper to normalize gr.update(...) return objects.

    In Gradio, gr.update returns a plain dict like {"value": ..., "visible": ...}.
    Older tests assumed an object with a .value attribute. This helper safely
    extracts the intended 'value' field for assertions.
    """
    if isinstance(obj, dict):
        return obj.get("value", "") or ""
    return getattr(obj, "value", "") or ""


def test_extract_summary_id():
    assert iface.extract_summary_id(None) is None
    assert iface.extract_summary_id({"abc": 1}) == "abc"
    assert iface.extract_summary_id("xyz") == "xyz"


def test_wrapper_fn_invalid_future_start():
    future = datetime.now() + timedelta(minutes=5)
    result = iface.wrapper_fn(
        camera="cam1",
        start=future,
        duration=10,
        action="Summarize",
        status_output_box=DummyStatusOutput(),
        previous_summary_id=None,
    )
    # result[1] is a gr.update() dict; assert error marker in its value
    assert _get_update_value(result[1]).startswith("❌ Error: Start time cannot be in the future")


def test_wrapper_fn_invalid_duration():
    past = datetime.now() - timedelta(minutes=5)
    result = iface.wrapper_fn(
        camera="cam1",
        start=past,
        duration=0,
        action="Summarize",
        status_output_box=DummyStatusOutput(),
        previous_summary_id=None,
    )
    assert "Duration must be a number" in _get_update_value(result[1])


def test_wrapper_fn_duration_end_in_future():
    now = datetime.now()
    start = now - timedelta(seconds=5)
    # duration pushes end time slightly into future
    result = iface.wrapper_fn(
        camera="cam1",
        start=start,
        duration=400000,  # huge, ensures future end
        action="Summarize",
        status_output_box=DummyStatusOutput(),
        previous_summary_id=None,
    )
    assert "End time (start + duration) cannot be in the future" in _get_update_value(result[1])


@pytest.mark.parametrize("invalid_start", [123.456, 123, object()])
def test_wrapper_fn_invalid_start_formats(invalid_start):
    # Force object path to invalid by wrapping an object not datetime/float/int accepted path rules
    result = iface.wrapper_fn(
        camera="cam1",
        start=invalid_start,
        duration=10,
        action="Summarize",
        status_output_box=DummyStatusOutput(),
        previous_summary_id=None,
    )
    # For int/float wrapper converts to datetime, so only generic object yields error
    if isinstance(invalid_start, (int, float)):
        # Accepts conversion path; ensure no generic invalid format message
        assert not _get_update_value(result[1]).startswith("❌ Error: Invalid start time format")
    else:
        assert _get_update_value(result[1]).startswith("❌ Error: Invalid start time format")
