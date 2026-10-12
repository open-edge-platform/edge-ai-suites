# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import uuid

from fastapi import APIRouter
from fastapi import HTTPException


def build_registry_router(frame_registry) -> APIRouter:
    """Builds a registry management router for the FastAPI application"""
    router = APIRouter(prefix="/api", tags=["registry"])

    @router.get("/registry/stats", summary="Get registry statistics")
    async def registry_stats():
        """Get registry statistics"""
        return frame_registry.stats()

    @router.get("/registry/stream/{stream_id}", summary="Get latest records for a specific stream")
    async def registry_stream(stream_id: str, limit: int = 50):
        """Get latest records for a specific stream"""
        records = frame_registry.latest(stream_id, limit)
        return {
			"records": [
				{
					"frame_id": str(r.frame_id),
					"stream_id": r.stream_id,
					"segment_path": r.segment_path,
					"pts_seconds": r.pts_seconds,
					"created_ts": r.created_ts,
				}
				for r in records
			]
		}

    @router.get("/registry/frame/{frame_id}", summary="Get a specific record by frame_id")
    async def registry_frame(frame_id: str):
        """Get a specific record by frame_id"""
        try:
            parsed_id = uuid.UUID(frame_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="'frame_id' must be a valid UUID")

        record = frame_registry.get_record(parsed_id)
        if record is None:
            raise HTTPException(status_code=404, detail="frame_id not found")

        return {
            "frame_id": str(record.frame_id),
            "stream_id": record.stream_id,
            "rtsp_url": record.rtsp_url,
            "segment_path": record.segment_path,
            "pts_seconds": record.pts_seconds,
            "created_ts": record.created_ts,
        }

    return router
