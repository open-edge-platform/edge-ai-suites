# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for DebouncedHandler (directory watcher logic)."""
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from service.directory_watcher import DebouncedHandler


def make_tmp_video(dir_path: Path, name="clip.mp4", size=600_000):
    fp = dir_path / name
    with open(fp, "wb") as f:
        f.write(b"0" * size)
    return str(fp)


def test_camera_disabled_ignored(monkeypatch, tmp_path):
    root = tmp_path / "2025-09-25" / "12" / "garage"
    root.mkdir(parents=True)
    video = make_tmp_video(root)

    called = {"files": None}

    def fake_action(files):
        called["files"] = files

    # disable all cameras
    monkeypatch.setattr("service.directory_watcher._root_watch_paths", [str(tmp_path)])
    monkeypatch.setattr("service.directory_watcher._enabled_cameras", {"garage": False})

    h = DebouncedHandler(debounce_time=0, action=fake_action)
    # simulate event
    class E:  # minimal event stub
        is_directory = False
        src_path = video
    h.on_created(E())
    assert called["files"] is None  # not processed


def test_camera_enabled_processes(monkeypatch, tmp_path):
    root = tmp_path / "2025-09-25" / "12" / "garage"
    root.mkdir(parents=True)
    video = make_tmp_video(root)

    processed_batches = []

    def fake_action(files):
        processed_batches.append(set(files))

    monkeypatch.setattr("service.directory_watcher._root_watch_paths", [str(tmp_path)])
    monkeypatch.setattr("service.directory_watcher._enabled_cameras", {"garage": True})

    h = DebouncedHandler(debounce_time=0, action=fake_action)

    class E:
        is_directory = False
        src_path = video

    h.on_created(E())
    # Force immediate processing
    h._process_files()
    # Wait briefly for action thread to run
    import time
    time.sleep(0.2)
    # Filter out any empty batches defensively (should no longer occur after fix)
    non_empty = [b for b in processed_batches if b]
    assert len(non_empty) == 1
    assert any(video in batch for batch in non_empty)


def test_ignores_small_files(monkeypatch, tmp_path):
    root = tmp_path / "2025-09-25" / "12" / "garage"
    root.mkdir(parents=True)
    fp = root / "small.mp4"
    with open(fp, "wb") as f:
        f.write(b"1234")  # < threshold

    events = []
    def fake_action(files):
        events.append(files)

    monkeypatch.setattr("service.directory_watcher._root_watch_paths", [str(tmp_path)])
    monkeypatch.setattr("service.directory_watcher._enabled_cameras", {"garage": True})

    h = DebouncedHandler(debounce_time=0, action=fake_action)

    class E:
        is_directory = False
        src_path = str(fp)

    h.on_created(E())
    h._process_files()
    import time
    time.sleep(0.1)
    # Should not have invoked action (events list empty)
    assert events == []  # nothing processed
