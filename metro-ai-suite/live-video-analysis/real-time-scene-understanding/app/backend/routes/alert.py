# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from fastapi.responses import Response


def build_alert_router(alert_index, get_alert_s3_client, settings) -> APIRouter:
    """Builds an alert management router for the FastAPI application"""
    router = APIRouter(prefix="/api", tags=["alert"])

    @router.get("/streams/{stream_id}/alerts", summary="List alerts for a specific stream")
    async def list_alerts(
        stream_id: str,
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ):
        """List alerts for a specific stream"""
        records, total = alert_index.list(stream_id, limit=limit, offset=offset)
        return {
            "total": total,
            "alerts": [
                {
                    "frame_id": r.get("frame_id", ""),
                    "trigger_caption": r.get("trigger_caption", ""),
                    "confirmed": r.get("confirmed", False),
                    "thumbnail_url": (
                        f"/api/streams/{stream_id}/alerts/{r.get('frame_id', '')}/thumbnail"
                        if r.get("thumbnail_object_key") else ""
                    ),
                    "uploaded_at": r.get("uploaded_at", ""),
                }
                for r in records
            ],
        }

    @router.get("/streams/{stream_id}/alerts/{frame_id}", summary="Get details of a specific alert")
    async def alert_detail(stream_id: str, frame_id: str):
        """Get details of a specific alert"""
        record = alert_index.get(stream_id, frame_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {
            "stream_id": record.get("stream_id", stream_id),
            "frame_id": record.get("frame_id", ""),
            "trigger_caption": record.get("trigger_caption", ""),
            "confirmed": record.get("confirmed", False),
            "thumbnail_url": (
                f"/api/streams/{stream_id}/alerts/{frame_id}/thumbnail"
                if record.get("thumbnail_object_key") else ""
            ),
            "confirmed": record.get("confirmed", False),
            "description": record.get("description", ""),
            "metrics": record.get("metrics", {}),
            "model": record.get("model", ""),
            "device": record.get("device", ""),
            "uploaded_at": record.get("uploaded_at", ""),
            "video_url": f"/api/streams/{stream_id}/alerts/{frame_id}/video",
        }

    @router.get("/streams/{stream_id}/alerts/{frame_id}/thumbnail", summary="Get the thumbnail image of a specific alert")
    async def alert_thumbnail(stream_id: str, frame_id: str):
        """Get the thumbnail image of a specific alert"""
        record = alert_index.get(stream_id, frame_id)
        if record is None or not record.get("thumbnail_object_key"):
            raise HTTPException(status_code=404, detail="Alert thumbnail not found")

        client = get_alert_s3_client()
        response = client.get_object(Bucket=settings.SEAWEEDFS_BUCKET, Key=record["thumbnail_object_key"])
        return Response(content=response["Body"].read(), media_type="image/jpeg")

    @router.get("/streams/{stream_id}/alerts/{frame_id}/video", summary="Get the video of a specific alert")
    async def alert_video(stream_id: str, frame_id: str):
        """Get the video of a specific alert"""
        record = alert_index.get(stream_id, frame_id)
        if record is None or not record.get("video_object_key"):
            raise HTTPException(status_code=404, detail="Alert video not found")

        client = get_alert_s3_client()
        response = client.get_object(Bucket=settings.SEAWEEDFS_BUCKET, Key=record["video_object_key"])
        return Response(content=response["Body"].read(), media_type="video/mp4")

    return router
