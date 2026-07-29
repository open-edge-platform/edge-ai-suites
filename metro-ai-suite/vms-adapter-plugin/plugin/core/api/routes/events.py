# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Event timeline endpoint."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from plugin.core.api.deps import get_db_session
from plugin.core.db import repository as repo
from plugin.core.models.domain import MetadataEvent

router = APIRouter()


@router.get("/events/timeline", response_model=list[MetadataEvent])
async def get_timeline(
    camera_id: str | None = Query(None),
    from_dt: datetime | None = Query(None),
    to_dt: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
):
    """Paginated event timeline."""
    return await repo.get_events_paginated(
        db, camera_id=camera_id, from_dt=from_dt, to_dt=to_dt,
        limit=limit, offset=offset,
    )
