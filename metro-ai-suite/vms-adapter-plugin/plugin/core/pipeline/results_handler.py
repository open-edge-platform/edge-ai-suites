# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Routes ``AnalysisResult`` to the appropriate ``IVmsShim`` write-back commands."""

from __future__ import annotations

import asyncio

import structlog

from plugin.base.interfaces import IVmsShim
from plugin.core.models.domain import AnalysisResult, CommandResult, MetadataEvent

logger = structlog.get_logger(__name__)


async def route_analysis_result(
    result: AnalysisResult,
    event: MetadataEvent,
    vms_shim: IVmsShim | None,
) -> list[CommandResult]:
    """Map ``AnalysisResult`` fields to ``IVmsShim`` calls (concurrent)."""
    if vms_shim is None:
        logger.info("no_vms_shim", event_id=result.event_id)
        return []

    tasks: list[asyncio.Task] = []
    cam = event.camera_id

    if result.labels:
        tasks.append(asyncio.create_task(
            vms_shim.push_label(camera_id=cam, event_id=result.event_id,
                                labels=result.labels)
        ))
    if result.bookmark:
        tasks.append(asyncio.create_task(
            vms_shim.set_bookmark(camera_id=cam, timestamp=event.started_at,
                                  label=result.status or result.event_id)
        ))
    if result.disposition in ("acknowledged", "dismissed"):
        tasks.append(asyncio.create_task(
            vms_shim.acknowledge_event(camera_id=cam, event_id=result.event_id,
                                       message=result.status or "")
        ))
    if result.trigger_recording:
        tasks.append(asyncio.create_task(
            vms_shim.trigger_recording(camera_id=cam)
        ))

    if not tasks:
        return []

    raw = await asyncio.gather(*tasks, return_exceptions=True)
    out: list[CommandResult] = []
    for cr in raw:
        if isinstance(cr, CommandResult):
            out.append(cr)
        elif isinstance(cr, Exception):
            logger.error("command_execution_error", error=str(cr))
    logger.info("results_routed", event_id=result.event_id, commands=len(out))
    return out
