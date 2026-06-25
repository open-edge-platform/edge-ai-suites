# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Session management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from plugin.core.api.deps import get_db_session
from plugin.core.db import repository as repo
from plugin.core.models.domain import AnalyticsSession

router = APIRouter(prefix="/sessions", tags=["Sessions"])


@router.get("", response_model=list[AnalyticsSession])
async def list_sessions(
    camera_id: str | None = Query(None, description="Filter by camera ID"),
    analytics_app_id: str | None = Query(None, description="Filter by app (e.g. dlstreamer, live_captioning)"),
    status: str | None = Query(None, description="Filter by status: active or stopped"),
    db: AsyncSession = Depends(get_db_session),
):
    """List analytics sessions, optionally filtered by camera, app, or status."""
    return await repo.list_sessions(db, camera_id=camera_id, analytics_app_id=analytics_app_id, status=status)


@router.get("/{session_id}", response_model=AnalyticsSession)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Get details of a specific analytics session."""
    s = await repo.get_session(db, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return s
