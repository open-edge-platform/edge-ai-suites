# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for the results-handler routing."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from plugin.core.models.domain import AnalysisResult, CommandResult, MetadataEvent
from plugin.core.pipeline.results_handler import route_analysis_result


def _cr(ct: str) -> CommandResult:
    return CommandResult(
        command_id=f"cmd-{ct}", camera_id="frigate:front-door",
        command_type=ct, status="accepted",
    )


@pytest.fixture
def event() -> MetadataEvent:
    return MetadataEvent(
        event_id="frigate:test123",
        camera_id="frigate:front-door",
        event_type="recording_segment",
        started_at=datetime(2026, 3, 30, 12, 0, 0),
    )


@pytest.fixture
def vms_shim():
    s = AsyncMock()
    s.push_label = AsyncMock(return_value=_cr("push_label"))
    s.set_bookmark = AsyncMock(return_value=_cr("set_bookmark"))
    s.acknowledge_event = AsyncMock(return_value=_cr("acknowledge_event"))
    s.trigger_recording = AsyncMock(return_value=_cr("trigger_recording"))
    return s


@pytest.mark.asyncio
async def test_labels(event, vms_shim):
    out = await route_analysis_result(
        AnalysisResult(event_id=event.event_id, labels=["person"]),
        event, vms_shim,
    )
    assert len(out) == 1
    vms_shim.push_label.assert_called_once()


@pytest.mark.asyncio
async def test_bookmark(event, vms_shim):
    out = await route_analysis_result(
        AnalysisResult(event_id=event.event_id, bookmark=True, status="x"),
        event, vms_shim,
    )
    assert len(out) == 1
    vms_shim.set_bookmark.assert_called_once()


@pytest.mark.asyncio
async def test_acknowledge(event, vms_shim):
    out = await route_analysis_result(
        AnalysisResult(event_id=event.event_id, disposition="acknowledged"),
        event, vms_shim,
    )
    assert len(out) == 1
    vms_shim.acknowledge_event.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_recording(event, vms_shim):
    out = await route_analysis_result(
        AnalysisResult(event_id=event.event_id, trigger_recording=True),
        event, vms_shim,
    )
    assert len(out) == 1
    vms_shim.trigger_recording.assert_called_once()


@pytest.mark.asyncio
async def test_multiple(event, vms_shim):
    out = await route_analysis_result(
        AnalysisResult(
            event_id=event.event_id, labels=["p"],
            bookmark=True, status="x", trigger_recording=True,
        ),
        event, vms_shim,
    )
    assert len(out) == 3


@pytest.mark.asyncio
async def test_no_shim(event):
    out = await route_analysis_result(
        AnalysisResult(event_id=event.event_id, labels=["x"]),
        event, None,
    )
    assert out == []


@pytest.mark.asyncio
async def test_no_commands(event, vms_shim):
    out = await route_analysis_result(
        AnalysisResult(event_id=event.event_id), event, vms_shim,
    )
    assert out == []
