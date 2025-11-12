# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for camera watcher mapping persistence and merge logic."""
import pytest
from unittest.mock import patch, AsyncMock

from api.router import get_camera_watcher_mapping, set_camera_watchers, CameraWatcherRequest

@pytest.mark.asyncio
async def test_get_camera_watcher_mapping_runtime_only():
    # No redis, empty runtime mapping
    async def empty_load(_=None):
        return {}
    with patch("api.router.get_enabled_cameras", return_value={"garage": True}), \
         patch("service.redis_store.load_camera_watcher_mapping", empty_load):
        data = await get_camera_watcher_mapping()
        assert data["mapping"] == {"garage": True}


@pytest.mark.asyncio
async def test_set_camera_watchers_persists_and_returns():
    fake_save = AsyncMock()
    fake_load = AsyncMock(return_value={})
    with patch("service.directory_watcher.save_camera_watcher_mapping", fake_save), \
         patch("service.directory_watcher._ensure_watcher_running"), \
         patch("service.directory_watcher._initial_scan_for_cameras"), \
         patch("service.directory_watcher._enabled_cameras", {}):
        req = CameraWatcherRequest(cameras=[{"garage": True}, {"livingroom": False}])
        # Directly call underlying function through router wrapper
        from api.router import set_camera_watchers as endpoint
        resp = await endpoint(req)
        assert "mapping" in resp
        assert resp["mapping"]["garage"] is True
        assert resp["mapping"]["livingroom"] is False
        assert set(resp["enabled"]) == {"garage"}


@pytest.mark.asyncio
async def test_get_camera_watcher_mapping_merges_redis(monkeypatch):
    async def fake_load(_=None):
        return {"garage": False, "livingroom": True}
    # Patch redis loader where it's imported inside router (service.redis_store)
    with patch("service.redis_store.load_camera_watcher_mapping", fake_load), \
         patch("api.router.get_enabled_cameras", return_value={"garage": True, "backyard": True}):
        data = await get_camera_watcher_mapping()
        # persisted garage False overridden by runtime True; livingroom from redis; backyard from runtime
        assert data["mapping"] == {"garage": True, "livingroom": True, "backyard": True}
