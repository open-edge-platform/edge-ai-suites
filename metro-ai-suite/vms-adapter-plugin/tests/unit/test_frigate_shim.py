# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the Frigate single-shim contract."""

from datetime import datetime

import pytest

from plugin.core.config import VmsInstanceConfig
from vms_shim.frigate.shim import FrigateVmsShim


@pytest.fixture
def frigate_config() -> VmsInstanceConfig:
    return VmsInstanceConfig(
        name="frigate-test", vendor="frigate",
        base_url="http://localhost:5000",
    )


@pytest.mark.asyncio
async def test_unsupported_commands(frigate_config):
    shim = FrigateVmsShim(frigate_config)
    # acknowledge_event when not connected returns unsupported
    ack = await shim.acknowledge_event("frigate:cam1", "evt1")
    assert ack.status == "unsupported"
    bm = await shim.set_bookmark("frigate:cam1", datetime.utcnow(), "lbl")
    assert bm.status == "unsupported"


@pytest.mark.asyncio
async def test_register_analytics_is_noop(frigate_config):
    shim = FrigateVmsShim(frigate_config)
    out = await shim.register_analytics({"engineId": "x"})
    assert out["status"] == "noop"


@pytest.mark.asyncio
async def test_get_clip_url_builds_path(frigate_config):
    shim = FrigateVmsShim(frigate_config)
    url = await shim.get_clip_url(
        "frigate:cam1",
        datetime(2026, 1, 1, 0, 0, 0),
        datetime(2026, 1, 1, 0, 0, 30),
    )
    assert url is not None
    assert "/api/cam1/recordings/" in url
    assert "/clip.mp4" in url


def test_initial_state(frigate_config):
    shim = FrigateVmsShim(frigate_config)
    assert shim.is_connected() is False
