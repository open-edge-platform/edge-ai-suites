# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import os
import tempfile
import time
import sys
import importlib
import logging

# --- Test-only shim ---------------------------------------------------------
# The ui.utils.common module imports `from config import logger`, but the backend
# `src/config.py` (found earlier on sys.path) does not define a logger symbol.
# Instead of altering production code, we inject a logger attribute into the
# loaded config module (or alias ui.config) before importing common.
try:
    backend_config = importlib.import_module("config")  # may resolve to src/config
    if not hasattr(backend_config, "logger"):
        logging.basicConfig(level=logging.INFO)
        backend_config.logger = logging.getLogger("injected-test-logger")
except ImportError:
    # Fall back to ui.config and register it as 'config'
    ui_config = importlib.import_module("ui.config")
    sys.modules["config"] = ui_config

from ui.utils import common  # noqa: E402 (import after shim)


def test_cleanup_temp_files_deletes_old_mp4(monkeypatch, tmp_path):
    # Arrange: create a fake temp dir with an old mp4 and a recent mp4
    old_file = tmp_path / "old_clip.mp4"
    recent_file = tmp_path / "recent_clip.mp4"
    other_file = tmp_path / "note.txt"

    old_file.write_text("old")
    recent_file.write_text("new")
    other_file.write_text("ignore")

    # Set mtime: old file older than 1h (3600s)
    now = time.time()
    os.utime(old_file, (now - 4000, now - 4000))
    os.utime(recent_file, (now - 100, now - 100))

    # Monkeypatch gettempdir to return our temp path
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

    # Act
    common.cleanup_temp_files()

    # Assert
    assert not old_file.exists(), "Old mp4 should be deleted"
    assert recent_file.exists(), "Recent mp4 should NOT be deleted"
    assert other_file.exists(), "Non-mp4 files should be ignored"


def test_cleanup_temp_files_handles_exception(monkeypatch):
    # Force os.listdir to raise
    monkeypatch.setattr(os, "listdir", lambda *_: (_ for _ in ()).throw(RuntimeError("boom")))
    # Should not raise
    common.cleanup_temp_files()
