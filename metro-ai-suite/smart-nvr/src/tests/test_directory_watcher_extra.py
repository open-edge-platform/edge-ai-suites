"""Additional directory_watcher tests for small helpers and mapping restoration."""
import os
import pytest
from unittest.mock import AsyncMock, patch
from service import directory_watcher as dw

def test_looks_like_date_helper():
    assert dw._looks_like_date("2025-01-31") is True
    assert dw._looks_like_date("2025-13-31") is False
    assert dw._looks_like_date("bad-date") is False

@pytest.mark.asyncio
async def test_restore_camera_watchers_no_mapping(monkeypatch):
    # Ensure function handles empty redis result gracefully
    async def fake_load(_=None):
        return {}
    monkeypatch.setattr("service.directory_watcher.load_camera_watcher_mapping", fake_load)
    # action stub counts calls
    calls = {"count": 0}
    def action_stub(paths):
        calls["count"] += 1
    await dw.restore_camera_watchers_from_redis(action_stub, debounce_time=1, request=None)
    assert calls["count"] == 0  # no action when no stored mapping

@pytest.mark.asyncio
async def test_set_camera_watcher_mapping_starts_watcher(monkeypatch, tmp_path):
    # Point watcher roots to temp dir
    monkeypatch.setattr("service.directory_watcher._root_watch_paths", [str(tmp_path)])
    # Prevent actual Observer start side effects by patching Observer
    class DummyObserver:
        def schedule(self, *a, **k):
            pass
        def start(self):
            pass
    monkeypatch.setattr("service.directory_watcher.Observer", lambda: DummyObserver())
    async def fake_save(mapping, request):
        return True
    monkeypatch.setattr("service.directory_watcher.save_camera_watcher_mapping", fake_save)
    def action_stub(paths):
        return True
    result = await dw.set_camera_watcher_mapping({"camA": True}, 1, action_stub)
    assert result["camA"] is True
    assert dw.get_enabled_cameras()["camA"] is True
