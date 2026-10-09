# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import time
from datetime import datetime
from datetime import timezone

from fastapi import APIRouter


def build_health_router(registry, startup_time: float) -> APIRouter:
    """Builds a health check router for the FastAPI application"""
    router = APIRouter(prefix="/api", tags=["health"])

    @router.get("/health", response_model=dict, summary="Health check endpoint")
    async def health() -> dict:
        """Health check endpoint"""
        return {
			"status": "healthy",
			"streams_active": len(registry.ids()),
			"uptime_seconds": round(time.monotonic() - startup_time, 1),
			"timestamp": datetime.now(tz=timezone.utc).isoformat(),
        }

    return router
