# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Nx Witness-specific ORM and domain models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import CheckConstraint, DateTime, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from plugin.core.models.db import Base


class NxAnalyticsIntegrationRow(Base):
    """Persists Nx analytics integration records (one per VMS + analytics app pair)."""

    __tablename__ = "nx_analytics_integrations"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    vms_name: Mapped[str] = mapped_column(String(255), nullable=False)
    analytics_app_id: Mapped[str] = mapped_column(String(100), nullable=False)
    integration_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    engine_manifest: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    device_agent_manifest: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    nx_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nx_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nx_request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )
    registered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # One integration per (vms, analytics_app) pair
        Index("uq_nx_integration_vms_app", "vms_name", "analytics_app_id", unique=True),
        CheckConstraint(
            "status IN ('pending', 'registered', 'approved', 'failed')",
            name="ck_nx_integration_status",
        ),
    )


class NxAnalyticsIntegration(BaseModel):
    """Nx Analytics Integration record persisted to the DB after Phase 1 registration."""

    id: str
    vms_name: str
    analytics_app_id: str
    integration_manifest: dict = Field(default_factory=dict)
    engine_manifest: dict = Field(default_factory=dict)
    device_agent_manifest: dict | None = None
    nx_username: str | None = None
    nx_password: str | None = None
    nx_request_id: str | None = None
    status: Literal["pending", "registered", "approved", "failed"] = "pending"
    registered_at: datetime | None = None


class NxRegisterRequest(BaseModel):
    """Request body for POST /v1/vms/{name}/register (Nx Witness and generic vendors)."""

    manifest: dict = Field(default_factory=dict)
    analytics_app_id: str = "default"
    # Nx-specific structured manifests (take priority over the flat manifest dict)
    integration_manifest: dict | None = None
    engine_manifest: dict | None = None
    device_agent_manifest: dict | None = None
    pin_code: str = "1234"
