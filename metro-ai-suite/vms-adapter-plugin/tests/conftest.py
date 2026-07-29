# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Shared test fixtures."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from plugin.core.models.domain import CommandResult


def _cmd_result(ctype: str, status: str = "accepted") -> CommandResult:
    return CommandResult(
        command_id=f"cmd-{ctype}", camera_id="test:cam1",
        command_type=ctype, status=status,
    )


@pytest.fixture
def mock_vms_shim():
    """Mock single ``IVmsShim`` (read + write + register)."""
    shim = AsyncMock()
    shim.connect = AsyncMock()
    shim.disconnect = AsyncMock()
    shim.is_connected = MagicMock(return_value=True)
    shim.discover_cameras = AsyncMock(return_value=[])
    shim.get_camera_metadata = AsyncMock(return_value=None)
    shim.get_live_stream_url = AsyncMock(return_value="rtsp://test/cam1")
    shim.get_clip_url = AsyncMock(return_value="http://test/clip.mp4")
    shim.register_analytics = AsyncMock(return_value={"status": "ok"})
    shim.acknowledge_event = AsyncMock(return_value=_cmd_result("acknowledge_event"))
    shim.set_bookmark = AsyncMock(return_value=_cmd_result("set_bookmark"))
    shim.push_label = AsyncMock(return_value=_cmd_result("push_label"))
    shim.trigger_recording = AsyncMock(return_value=_cmd_result("trigger_recording"))
    return shim


@pytest.fixture
def mock_analytics_app_shim():
    shim = AsyncMock()
    shim.deliver = AsyncMock(return_value=None)
    shim.is_reachable = AsyncMock(return_value=True)
    return shim
