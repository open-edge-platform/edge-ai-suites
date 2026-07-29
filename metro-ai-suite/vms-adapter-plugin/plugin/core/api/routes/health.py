# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Health check endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from plugin.core.api.deps import get_db_session, get_vms_shim_sets
from plugin.core.factory import VmsShimSet

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    db: AsyncSession = Depends(get_db_session),
    shim_sets: list[VmsShimSet] = Depends(get_vms_shim_sets),
):
    """Readiness probe. DB is gating; VMS connectivity is informational."""
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    vms_connected = any(s.vms_shim.is_connected() for s in shim_sets) if shim_sets else False

    return JSONResponse(
        content={
            "status": "ready" if db_ok else "not_ready",
            "database": db_ok,
            "vms_connected": vms_connected,
        },
        status_code=200 if db_ok else 503,
    )

