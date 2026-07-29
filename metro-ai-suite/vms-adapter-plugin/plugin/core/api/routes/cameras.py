# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Camera management endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from plugin.core.api.deps import get_db_session, get_vms_shim_sets
from plugin.core.db import repository as repo
from plugin.core.factory import VmsShimSet
from plugin.core.models.domain import (
    Camera,
    CameraEnableRequest,
    CameraEnableResponse,
    CameraView,
    ClipUrlResponse,
    mask_url_credentials,
    StreamUrlResponse,
)

router = APIRouter()


def _shim_for(camera_id: str, shim_sets: list[VmsShimSet]) -> VmsShimSet | None:
    for ss in shim_sets:
        if camera_id.startswith(ss.vms_shim.camera_id_prefix):
            return ss
    return None


@router.get("/cameras", response_model=list[CameraView])
async def list_cameras(db: AsyncSession = Depends(get_db_session)):
    cams = await repo.get_all_cameras(db)
    return [CameraView.from_camera(c) for c in cams]


@router.post("/cameras/discover", response_model=list[CameraView])
async def discover_cameras(
    db: AsyncSession = Depends(get_db_session),
    shim_sets: list[VmsShimSet] = Depends(get_vms_shim_sets),
):
    """Active discovery scan across all NVRs : upserts results into DB (30s timeout)."""
    async def _discover_one(ss: VmsShimSet) -> list[Camera]:
        try:
            return await ss.vms_shim.discover_cameras()
        except Exception:
            return []

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[_discover_one(s) for s in shim_sets]),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Discovery timed out")

    for cam_list in results:
        for cam in cam_list:
            await repo.upsert_camera(db, cam)
    cams = await repo.get_all_cameras(db)
    return [CameraView.from_camera(c) for c in cams]


@router.post("/cameras/enable", response_model=CameraEnableResponse)
async def enable_cameras(
    body: CameraEnableRequest,
    db: AsyncSession = Depends(get_db_session),
):
    if not body.camera_ids:
        raise HTTPException(status_code=400, detail="camera_ids cannot be empty")
    updated, not_found = await repo.update_camera_enabled(
        db, body.camera_ids, body.enabled
    )
    return CameraEnableResponse(updated=updated, not_found=not_found)


@router.get("/cameras/{camera_id}/live-stream", response_model=StreamUrlResponse)
async def get_live_stream(
    camera_id: str,
    shim_sets: list[VmsShimSet] = Depends(get_vms_shim_sets),
):
    ss = _shim_for(camera_id, shim_sets)
    if ss is None:
        raise HTTPException(status_code=404, detail="No shim for camera")
    url = await ss.vms_shim.get_live_stream_url(camera_id)
    if not url:
        raise HTTPException(status_code=404, detail="Live stream unavailable")
    return StreamUrlResponse(camera_id=camera_id, rtsp_url=mask_url_credentials(url) or url)


@router.get("/cameras/{camera_id}/clip", response_model=ClipUrlResponse)
async def get_clip(
    camera_id: str,
    from_dt: datetime = Query(..., alias="from"),
    to_dt: datetime = Query(..., alias="to"),
    shim_sets: list[VmsShimSet] = Depends(get_vms_shim_sets),
):
    ss = _shim_for(camera_id, shim_sets)
    if ss is None:
        raise HTTPException(status_code=404, detail="No shim for camera")
    url = await ss.vms_shim.get_clip_url(camera_id, from_dt, to_dt)
    if not url:
        raise HTTPException(status_code=404, detail="Clip URL unavailable")
    return ClipUrlResponse(
        camera_id=camera_id,
        clip_url=mask_url_credentials(url) or url,
        from_dt=from_dt,
        to_dt=to_dt,
    )


@router.get("/cameras/{camera_id}", response_model=CameraView)
async def get_camera(camera_id: str, db: AsyncSession = Depends(get_db_session)):
    cam = await repo.get_camera(db, camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return CameraView.from_camera(cam)
