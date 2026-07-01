# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# """Per-VMS endpoints : register analytics manifest with a specific VMS."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from plugin.core.api.deps import get_db_session, get_vms_shim_sets
from plugin.core.factory import VmsShimSet

router = APIRouter()


@router.post("/vms/{name}/register")
async def register_vms(
    name: str,
    request: Request,
    shim_sets: list[VmsShimSet] = Depends(get_vms_shim_sets),
    db: AsyncSession = Depends(get_db_session),
):
    """Push an analytics manifest to one VMS.

    Delegates entirely to the VMS shim's ``handle_register()`` method.
    The shim owns all vendor-specific logic (manifest resolution, DB state,
    credential injection). Request body is passed as a raw dict so each shim
    can declare and parse its own fields.
    """
    ss = next((s for s in shim_sets if s.name == name), None)
    if ss is None:
        raise HTTPException(status_code=404, detail=f"VMS '{name}' not configured")

    try:
        body = await request.json()
    except Exception:
        body = {}

    return await ss.vms_shim.handle_register(body, db, name)
