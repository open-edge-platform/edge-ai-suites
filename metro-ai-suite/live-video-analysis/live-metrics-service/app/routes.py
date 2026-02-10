# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Health check routes for the Metrics Service.
"""

from fastapi import APIRouter

from .relay import get_status

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    
    Returns:
        {"status": "healthy"}
    """
    return {"status": "healthy"}


@router.get("/api/health")
async def api_health_check():
    """
    Detailed health check with service status.
    
    Returns:
        {
            "status": "healthy",
            "collector_connected": bool,
            "clients_connected": int
        }
    """
    relay_status = await get_status()
    
    return {
        "status": "healthy",
        **relay_status,
    }
