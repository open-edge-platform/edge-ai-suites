# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.services.stream_registry.StreamRegistry.

StreamManager itself owns real PyAV threads/sockets, so it's replaced here
with a lightweight fake that mirrors just the interface StreamRegistry
depends on (start/stop/stream_id/source_url/vlm_prompt/deep_analyzer_prompt/alert_event).
"""

from __future__ import annotations

import pytest
from backend.services import stream_registry as stream_registry_module
from backend.services.frame_registry import SegmentFrameRegistry
from backend.services.stream_registry import StreamRegistry


class FakeStreamManager:
    instances: list["FakeStreamManager"] = []

    def __init__(
        self,
        stream_id,
        source_url,
        vlm_prompt="",
        deep_analyzer_prompt="",
        alert_event="",
        frame_registry=None,
    ):
        self.stream_id = stream_id
        self.source_url = source_url
        self.vlm_prompt = vlm_prompt
        self.deep_analyzer_prompt = deep_analyzer_prompt
        self.alert_event = alert_event
        self.frame_registry = frame_registry
        self.started = False
        self.stopped = False
        FakeStreamManager.instances.append(self)

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True


@pytest.fixture(autouse=True)
def _patch_stream_manager(monkeypatch):
    FakeStreamManager.instances = []
    monkeypatch.setattr(stream_registry_module, "StreamManager", FakeStreamManager)


@pytest.fixture
def registry() -> StreamRegistry:
    return StreamRegistry(SegmentFrameRegistry(max_records_per_stream=10))


class TestAdd:
    def test_add_creates_and_starts_a_manager(self, registry):
        manager = registry.add("cam-1", "rtsp://example/cam1")

        assert isinstance(manager, FakeStreamManager)
        assert manager.started is True
        assert registry.ids() == ["cam-1"]

    def test_add_rejects_empty_source_url(self, registry):
        with pytest.raises(ValueError, match="source_url"):
            registry.add("cam-1", "")

    def test_add_rejects_duplicate_stream_id(self, registry):
        registry.add("cam-1", "rtsp://example/cam1")
        with pytest.raises(ValueError, match="already exists"):
            registry.add("cam-1", "rtsp://example/cam1-again")

    def test_add_enforces_max_streams(self, registry, monkeypatch):
        monkeypatch.setattr(stream_registry_module.settings, "MAX_STREAMS", 1)
        registry.add("cam-1", "rtsp://example/cam1")
        with pytest.raises(ValueError, match="Maximum of 1 streams"):
            registry.add("cam-2", "rtsp://example/cam2")


class TestRemove:
    def test_remove_stops_and_forgets_the_manager(self, registry):
        manager = registry.add("cam-1", "rtsp://example/cam1")

        registry.remove("cam-1")

        assert manager.stopped is True
        assert registry.ids() == []

    def test_remove_unknown_stream_raises_key_error(self, registry):
        with pytest.raises(KeyError):
            registry.remove("does-not-exist")


class TestQueries:
    def test_all_returns_every_manager(self, registry):
        registry.add("cam-1", "rtsp://example/cam1")
        registry.add("cam-2", "rtsp://example/cam2")

        managers = registry.all()

        assert {m.stream_id for m in managers} == {"cam-1", "cam-2"}

    def test_stop_all_stops_every_manager_and_clears_registry(self, registry):
        registry.add("cam-1", "rtsp://example/cam1")
        registry.add("cam-2", "rtsp://example/cam2")

        registry.stop_all()

        assert registry.ids() == []
        assert all(m.stopped for m in FakeStreamManager.instances)
