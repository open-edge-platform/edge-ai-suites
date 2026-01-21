# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])

@router.get("/health", response_model=dict)
async def health_check() -> dict:
    """A simple health check endpoint."""
    return {"status": "healthy"}