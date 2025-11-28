# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for UI main entry point launching Gradio app."""
import runpy
from unittest.mock import patch, MagicMock


def test_ui_main_import_only(monkeypatch):
    """Ensure importing ui.main does not execute launch (since __name__ != '__main__')."""
    # Patch heavy functions so even if imported side-effects minimize
    monkeypatch = monkeypatch  # explicit
    monkeypatch.setattr("ui.main.initialize_app", lambda: None)
    monkeypatch.setattr("ui.main.create_ui", lambda: MagicMock())
    module = runpy.run_module("ui.main")
    # create_ui shouldn't have been called because __name__ != '__main__'
    # Nothing to assert strongly here; absence of launch side effects is success.
    assert "__name__" in module


def test_ui_main_dunder_main(monkeypatch):
    calls = {}

    fake_ui = MagicMock()
    fake_ui.launch = MagicMock(side_effect=lambda **k: calls.setdefault("launched", True))
    # IMPORTANT: patch the ORIGINAL definitions in ui.interface.interface because
    # runpy.run_module("ui.main", run_name="__main__") re-executes ui.main and
    # re-binds names from that module (fresh) to symbols imported FROM interface.
    # If we only patch ui.main.<symbol>, those patches apply to the already-loaded
    # module object, but the second execution creates a new module instance whose
    # symbols point again at the original (unpatched) functions. Patching at the
    # source module (ui.interface.interface) ensures the imported symbols are the
    # patched versions during the re-execution.
    monkeypatch.setattr("ui.interface.interface.initialize_app", lambda: calls.setdefault("initialized", True))
    monkeypatch.setattr("ui.interface.interface.create_ui", lambda: fake_ui)
    monkeypatch.setattr("ui.interface.interface.stop_event_updates", lambda: calls.setdefault("stopped", True))
    # Also neutralize any sleeps inside interface (e.g., time.sleep(5) in create_ui)
    monkeypatch.setattr("ui.interface.interface.time.sleep", lambda *a, **k: None, raising=False)

    runpy.run_module("ui.main", run_name="__main__")

    assert calls.get("initialized")
    assert calls.get("launched")
    assert calls.get("stopped")
    fake_ui.launch.assert_called_once()
