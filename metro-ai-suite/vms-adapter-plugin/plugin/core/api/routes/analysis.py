# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Analysis results callback endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from plugin.core.api.deps import get_db_session, get_vms_shim_sets
from plugin.core.db import repository as repo
from plugin.core.factory import VmsShimSet
from plugin.core.models.domain import AnalysisResult, CommandResult
from plugin.core.pipeline.results_handler import route_analysis_result

router = APIRouter()


@router.post("/analysis/results", response_model=list[CommandResult])
async def receive_analysis_results(
    result: AnalysisResult,
    db: AsyncSession = Depends(get_db_session),
    shim_sets: list[VmsShimSet] = Depends(get_vms_shim_sets),
):
    """Async callback : Analytics App POSTs ``AnalysisResult`` here.

    The plugin persists the (event, result) pair if the event is unknown
    (the App may be the source of truth in RTSP-only mode), then routes
    the result via the matching ``IVmsShim``.
    """
    event = await repo.get_event(db, result.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    vms_shim = None
    for ss in shim_sets:
        prefix = "nx:" if ss.config.vendor == "nx_witness" else f"{ss.config.vendor}:"
        if event.camera_id.startswith(prefix):
            vms_shim = ss.vms_shim
            break

    return await route_analysis_result(result, event, vms_shim)
