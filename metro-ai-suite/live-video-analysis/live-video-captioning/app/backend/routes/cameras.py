# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool
from ..models import CameraDevice, CameraDeviceList
from ..services import discover_capture_cameras

router = APIRouter(prefix="/api", tags=["cameras"])


@router.get("/cameras", response_model=CameraDeviceList)
async def list_cameras() -> CameraDeviceList:
    """List camera devices from /dev/videoX that support Video Capture."""
    cameras = await run_in_threadpool(discover_capture_cameras)
    return CameraDeviceList(cameras=[CameraDevice(**camera) for camera in cameras])
