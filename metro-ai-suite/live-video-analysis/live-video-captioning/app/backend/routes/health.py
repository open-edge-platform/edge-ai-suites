# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter
from ..services import has_gpu_device, has_npu_device

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=dict)
async def health_check() -> dict:
    """A simple health check endpoint."""
    return {"status": "healthy"}


@router.get("/capabilities", response_model=dict)
async def get_capabilities() -> dict:
    """Report host capabilities needed by the UI."""
    return {
        "has_gpu": has_gpu_device(),
        "has_npu": has_npu_device()
    }
