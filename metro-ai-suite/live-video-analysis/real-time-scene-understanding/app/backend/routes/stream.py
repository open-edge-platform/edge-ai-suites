# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel
from pydantic import Field

logger = logging.getLogger(__name__)

# SDL425/SDL443: stream_id is interpolated directly into segment filesystem
# paths (see StreamManager._segment_path) and into the WHEP URL path, so it
# must be restricted to a safe allowlist — no "/", "..", or other path/URL
# metacharacters.
_STREAM_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ALLOWED_URL_SCHEMES = {"rtsp", "rtsps"}
_MAX_URL_LENGTH = 2048
_MAX_PROMPT_LENGTH = 4096


class AddStreamRequest(BaseModel):
    """Validated body for POST /api/streams (SDL425/SDL443)."""

    url: str = Field(default="", max_length=_MAX_URL_LENGTH)
    stream_id: str = Field(default="", max_length=64)
    alert_prompt: str = Field(default="", max_length=_MAX_PROMPT_LENGTH)
    deep_analyzer_prompt: str = Field(default="", max_length=_MAX_PROMPT_LENGTH)


def build_stream_router(registry, alert_index) -> APIRouter:
    """Builds a stream management router for the FastAPI application"""
    router = APIRouter(prefix="/api", tags=["stream"])

    @router.get("/streams", summary="List all active streams")
    async def list_streams() -> dict:
        """List all active streams"""
        result = []
        for manager in registry.all():
            act_stream = manager.get_health()
            result.append(
                {
                    "stream_id": manager.stream_id,
                    "url": manager.source_url,
                    "alert_prompt": manager.vlm_prompt,
                    "deep_analyzer_prompt": manager.deep_analyzer_prompt,
                    "publishing": act_stream.publishing,
                    "codec": act_stream.codec,
                    "resolution": act_stream.resolution,
                    "reconnect_count": act_stream.reconnect_count,
                    "whep_path": f"/{manager.stream_id}/whep",
                    "caption": act_stream.caption,
                    "caption_history": act_stream.caption_history,
                    "caption_ts": act_stream.caption_ts,
                    "ttft_ms": act_stream.ttft_ms,
                    "tpot_ms": act_stream.tpot_ms,
                    "throughput_tps": act_stream.throughput_tps,
                    "alert_count": alert_index.count(manager.stream_id),
                }
            )
        return {"streams": result}

    @router.post("/streams", summary="Add a new stream")
    async def add_stream(payload: AddStreamRequest):
        """Add a new stream"""
        source_url = payload.url.strip()
        stream_id = payload.stream_id.strip() or "default"
        alert_prompt = payload.alert_prompt
        deep_analyzer_prompt = payload.deep_analyzer_prompt
        normalized_alert_prompt = alert_prompt.strip()
        normalized_deep_analyzer_prompt = deep_analyzer_prompt.strip()
        if not source_url:
            raise HTTPException(status_code=400, detail="'url' is required")

        # SDL425: allowlist URL scheme — reject file://, javascript:, etc.
        parsed_url = urlparse(source_url)
        if parsed_url.scheme.lower() not in _ALLOWED_URL_SCHEMES:
            logger.warning("Rejected add_stream request with disallowed URL scheme: %r", parsed_url.scheme)
            raise HTTPException(status_code=400, detail="'url' must use rtsp:// or rtsps://")

        # SDL425: stream_id becomes part of a filesystem path (segment files)
        # and a URL path (WHEP endpoint) — restrict to a safe allowlist to
        # prevent path traversal / injection.
        if not _STREAM_ID_RE.match(stream_id):
            logger.warning("Rejected add_stream request with invalid stream_id")
            raise HTTPException(
                status_code=400,
                detail="'stream_id' must match ^[A-Za-z0-9_-]{1,64}$",
            )

        if not alert_prompt.strip():
            raise HTTPException(
                status_code=400,
                detail="'alert_prompt' is required",
            )
        if not deep_analyzer_prompt.strip():
            raise HTTPException(
                status_code=400,
                detail="'deep_analyzer_prompt' is required",
            )

        try:
            registry.add(
                stream_id,
                source_url,
                normalized_alert_prompt,
                normalized_deep_analyzer_prompt,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return {"status": "added", "stream_id": stream_id}

    @router.delete("/streams/{stream_id}", summary="Delete a stream")
    async def delete_stream(stream_id: str):
        """Delete a stream"""
        try:
            registry.remove(stream_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Stream '{stream_id}' not found")
        return {"status": "removed", "stream_id": stream_id}

    return router
