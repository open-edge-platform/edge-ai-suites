# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""SQLAlchemy 2 async ORM models for PostgreSQL persistence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, Index, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CameraRow(Base):
    __tablename__ = "cameras"

    camera_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="unknown")
    stream_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    vendor_meta: Mapped[dict] = mapped_column(JSONB, default=dict)


class MetadataEventRow(Base):
    __tablename__ = "metadata_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    camera_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    labels: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    clip_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    vendor_meta: Mapped[dict] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        Index("ix_events_camera_started", "camera_id", started_at.desc()),
    )


class AnalyticsSessionRow(Base):
    __tablename__ = "analytics_sessions"

    session_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    camera_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    analytics_app_id: Mapped[str] = mapped_column(String(100), nullable=False)
    app_instance_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    launch_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    app_state: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow,
    )
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # At most one active session per camera+app combination
        Index(
            "uq_sessions_camera_app_active",
            "camera_id", "analytics_app_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        # app_instance_id must be unique when set
        Index(
            "uq_sessions_instance_id",
            "app_instance_id",
            unique=True,
            postgresql_where=text("app_instance_id IS NOT NULL"),
        ),
        # status must be one of the known values
        CheckConstraint("status IN ('active', 'stopped')", name="ck_session_status"),
        # stopped_at must be set iff status = 'stopped'
        CheckConstraint(
            "(status = 'stopped') = (stopped_at IS NOT NULL)",
            name="ck_session_stopped_at_consistency",
        ),
    )
