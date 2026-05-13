# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
API request and response schemas (Pydantic models for all FastAPI endpoints).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class StreamAddRequest(BaseModel):
    stream_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Stream ID (auto-generated UUID if omitted)",
    )
    name: str = Field(
        default="",
        max_length=128,
        description="Human-readable stream label",
    )
    url: str = Field(..., description="RTSP, HTTP, HTTPS, or file:// URL")
    tools: List[str] = Field(
        default_factory=list,
        description="Allowed tools for this stream (empty = all tools allowed)",
    )
    alerts: List[str] = Field(
        default_factory=list,
        description="Alert names to evaluate for this stream (empty = all enabled alerts)",
    )

    @field_validator("stream_id")
    @classmethod
    def id_safe(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError("Stream ID may only contain letters, digits, hyphens and underscores")
        return v

    def resolve_id(self) -> str:
        """Return the explicit stream_id or generate a short UUID."""
        return self.stream_id if self.stream_id else uuid.uuid4().hex[:12]

    @field_validator("url")
    @classmethod
    def url_scheme(cls, v: str) -> str:
        allowed = ("rtsp://", "rtsps://", "http://", "https://", "file://")
        if not any(v.startswith(s) for s in allowed):
            raise ValueError(f"URL must start with one of: {', '.join(allowed)}")
        return v


class StreamResponse(BaseModel):
    status: Literal["added", "removed"]
    stream_id: str


class StreamStatus(BaseModel):
    stream_id: str
    name: str = ""
    url: str
    connected: bool
    fps: Optional[float] = None
    resolution: Optional[str] = None
    buffer_fill: int = 0
    tools: List[str] = Field(default_factory=list)
    alerts: List[str] = Field(default_factory=list)


class StreamPatchRequest(BaseModel):
    alerts: Optional[List[str]] = None


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    streams_active: int
    alerts_enabled: int
    vlm_reachable: bool
    uptime_seconds: float
    timestamp: datetime


class StreamMetrics(BaseModel):
    stream_id: str
    analysis_count: int = 0
    alert_count: int = 0
    last_inference_ms: Optional[float] = None


class SystemMetrics(BaseModel):
    cpu_percent: float
    memory_percent: float
    streams: List[StreamMetrics] = Field(default_factory=list)


class ToolInfo(BaseModel):
    name: str
    description: str
    enabled: bool
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolInvokeRequest(BaseModel):
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ToolInvokeResponse(BaseModel):
    tool: str
    status: Literal["success", "error"]
    result: Any
    duration_ms: float


class AlertHistoryQuery(BaseModel):
    stream_id: Optional[str] = None
    alert_name: Optional[str] = None
    answer: Optional[Literal["YES", "NO"]] = None
    limit: int = Field(default=50, ge=1, le=500)


class ErrorResponse(BaseModel):
    error: str
    detail: str
    code: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
