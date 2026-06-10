# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""CRUD repository for Nx Witness analytics integration records."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from vms_shim.nxwitness.models import NxAnalyticsIntegration, NxAnalyticsIntegrationRow


async def upsert_nx_integration(
    session: AsyncSession,
    vms_name: str,
    analytics_app_id: str,
    integration_manifest: dict,
    engine_manifest: dict,
    device_agent_manifest: dict | None,
    nx_username: str | None,
    nx_password: str | None,
    nx_request_id: str | None,
    status: str,
) -> NxAnalyticsIntegration:
    """Insert or update an Nx analytics integration record keyed by (vms_name, analytics_app_id)."""
    registered_at = datetime.now(timezone.utc) if status == "approved" else None
    base = pg_insert(NxAnalyticsIntegrationRow).values(
        id=str(uuid.uuid4()),
        vms_name=vms_name,
        analytics_app_id=analytics_app_id,
        integration_manifest=integration_manifest,
        engine_manifest=engine_manifest,
        device_agent_manifest=device_agent_manifest,
        nx_username=nx_username,
        nx_password=nx_password,
        nx_request_id=nx_request_id,
        status=status,
        registered_at=registered_at,
    )
    stmt = base.on_conflict_do_update(
        index_elements=["vms_name", "analytics_app_id"],
        set_={
            "integration_manifest": base.excluded.integration_manifest,
            "engine_manifest": base.excluded.engine_manifest,
            "device_agent_manifest": base.excluded.device_agent_manifest,
            "nx_username": base.excluded.nx_username,
            "nx_password": base.excluded.nx_password,
            "nx_request_id": base.excluded.nx_request_id,
            "status": base.excluded.status,
            "registered_at": base.excluded.registered_at,
        },
    ).returning(NxAnalyticsIntegrationRow)
    result = await session.execute(stmt)
    await session.commit()
    row = result.scalar_one()
    return _row_to_nx_integration(row)


async def get_nx_integration(
    session: AsyncSession, vms_name: str, analytics_app_id: str,
) -> NxAnalyticsIntegration | None:
    result = await session.execute(
        select(NxAnalyticsIntegrationRow).where(
            NxAnalyticsIntegrationRow.vms_name == vms_name,
            NxAnalyticsIntegrationRow.analytics_app_id == analytics_app_id,
        )
    )
    row = result.scalar_one_or_none()
    return _row_to_nx_integration(row) if row else None


def _row_to_nx_integration(row: NxAnalyticsIntegrationRow) -> NxAnalyticsIntegration:
    return NxAnalyticsIntegration(
        id=row.id,
        vms_name=row.vms_name,
        analytics_app_id=row.analytics_app_id,
        integration_manifest=row.integration_manifest or {},
        engine_manifest=row.engine_manifest or {},
        device_agent_manifest=row.device_agent_manifest,
        nx_username=row.nx_username,
        nx_password=row.nx_password,
        nx_request_id=row.nx_request_id,
        status=row.status,
        registered_at=row.registered_at,
    )
