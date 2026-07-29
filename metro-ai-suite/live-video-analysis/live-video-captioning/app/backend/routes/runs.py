# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from ..models import RunInfo, StartRunRequest
from ..services import PipelineServer

router = APIRouter(prefix="/api", tags=["captions"])
logger = logging.getLogger("app.runs")
pipeline_server = PipelineServer()

@router.post("/generate_captions_alerts")
async def start_run(req: StartRunRequest) -> RunInfo:
    """Start a new video captioning run and generate captions and alerts."""
    return await pipeline_server.start_run(req)


@router.get("/generate_captions_alerts")
async def list_runs() -> list[RunInfo]:
    """List all active captioning runs."""
    return pipeline_server.list_runs()


@router.get("/generate_captions_alerts/metadata-stream")
async def multiplexed_metadata_stream() -> StreamingResponse:
    """Multiplexed SSE stream that provides captions and alerts metadata for all active runs."""
    logger.info("Multiplexed metadata stream requested")
    return pipeline_server.metadata_stream()



@router.get("/generate_captions_alerts/{run_id}/stream-ready")
async def stream_ready(run_id: str) -> dict[str, object]:
    """Report whether the WebRTC stream for a run is publishing yet.

    The DL Streamer pipeline needs a few seconds after start before it begins
    publishing frames to mediamtx. The UI polls this endpoint and only loads the
    video iframe once frames are flowing, avoiding mediamtx's "stream not
    found, retrying" page.

    This endpoint is the backend half of a two-stage readiness gate: the
    backend answers "is the pipeline alive and producing?", mediamtx answers
    "can the browser watch it yet?" (the UI confirms the latter with a WHEP
    probe before loading the iframe).

    Readiness is derived from the pipeline server alone: the run is ready when
    its instance is ``RUNNING`` and reports a positive ``avg_fps`` — frames
    moving through the pipeline are being published to mediamtx by the WebRTC
    sink. This deliberately avoids the mediamtx control API, so mediamtx can
    run with its API disabled. The pipeline state also lets the UI fail fast
    when the instance leaves the ``RUNNING``/``QUEUED`` states (or vanishes)
    instead of staying stuck on "Connecting…".
    """
    return await pipeline_server.stream_ready(run_id)

@router.get("/generate_captions_alerts/{run_id}")
async def get_run(run_id: str) -> RunInfo:
    """Get details of a specific captioning run."""
    return pipeline_server.get_run(run_id)

@router.delete("/generate_captions_alerts/{run_id}")
async def stop_run(run_id: str) -> dict[str, str]:
    """Stop a running captioning pipeline."""
    return await pipeline_server.stop_run(run_id)
