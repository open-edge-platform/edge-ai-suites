# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import logging
import re
import uuid
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from ..config import (
    PIPELINE_NAME,
    PIPELINE_SERVER_URL,
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_TOPIC_PREFIX,
    WEBRTC_BITRATE,
)
from ..models import RunInfo, StartRunRequest
from ..models.requests import DEFAULT_PROMPT
from ..services import http_json, get_mqtt_subscriber
from ..state import RUNS

router = APIRouter(prefix="/api", tags=["runs"])
logger = logging.getLogger("app.runs")

@router.post("/runs")
async def start_run(req: StartRunRequest) -> RunInfo:
    """Start a new video captioning run."""
    # Process optional runName - use it for run_id if provided
    run_name = None
    if req.runName and req.runName.strip():
        # Sanitize: replace spaces with underscores, remove special chars
        sanitized = re.sub(r'\s+', '_', req.runName.strip())
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '', sanitized)
        if sanitized:
            run_name = sanitized
            # Check for duplicates and append suffix if needed
            base_name = sanitized
            counter = 1
            while run_name in RUNS:
                run_name = f"{base_name}_{counter}"
                counter += 1

    # Use runName for run_id if provided, otherwise generate UUID
    if run_name:
        run_id = run_name
    else:
        run_id = uuid.uuid4().hex[:10]

    peer_id = f"stream-{run_id[:10] if len(run_id) > 10 else run_id}"
    
    # MQTT topic for this run's metadata
    mqtt_topic = f"{MQTT_TOPIC_PREFIX}"

    pipeline_name = (req.pipelineName or PIPELINE_NAME).strip() or PIPELINE_NAME

    start_url = f"{PIPELINE_SERVER_URL.rstrip('/')}/pipelines/user_defined_pipelines/{pipeline_name}"
    payload = {
        "source": {"uri": req.rtspUrl, "type": "uri"},
        "destination": {
            "frame": {"type": "webrtc", "peer-id": peer_id, "bitrate": WEBRTC_BITRATE},
        },
        "parameters": {
            "captioner-prompt": (req.prompt or "").strip()
            or DEFAULT_PROMPT,
            "captioner_model_name": (req.modelName or "").strip()
            or "OpenGVLab/InternVL2-2B",
            "captioner_max_new_tokens": req.maxNewTokens,
            "detection_model_name": (req.detectionModelName or "").strip()
            or "yolov8s",
            "detection_threshold": req.detectionThreshold,
            "mqtt_publisher": {
                "topic": f"{MQTT_TOPIC_PREFIX}/{run_id}",
                "publish_frame": False,
            },
        },
    }

    raw = http_json("POST", start_url, payload=payload)
    pipeline_id = raw.replace('"', "").strip()
    if not pipeline_id:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Pipeline server returned empty pipeline id",
                "body": raw,
            },
        )

    model_name = (req.modelName or "").strip() or "InternVL2-2B"
    # Use full run_id for custom names, truncated for UUID-based
    final_run_id = run_id if run_name else run_id[:10]
    info = RunInfo(
        runId=final_run_id,
        pipelineId=pipeline_id,
        peerId=peer_id,
        mqttTopic=mqtt_topic,
        modelName=model_name,
        pipelineName=pipeline_name,
        runName=run_name,
        prompt=(req.prompt or "").strip() or DEFAULT_PROMPT,
        maxTokens=req.maxNewTokens,
        rtspUrl=req.rtspUrl,
    )
    RUNS[info.runId] = info
    return info


@router.get("/runs")
async def list_runs() -> list[RunInfo]:
    """List all active runs."""
    return list(RUNS.values())


async def _multiplexed_metadata_generator() -> AsyncGenerator[str, None]:
    """Generator that receives metadata from MQTT and multiplexes into a single SSE stream."""
    message_queue: asyncio.Queue = asyncio.Queue()
    subscribed_runs: set[str] = set()
    
    def on_message(run_id: str, data: dict, received_at: float):
        """Callback for MQTT messages - puts them into the async queue."""
        try:
            asyncio.get_event_loop().call_soon_threadsafe(
                message_queue.put_nowait,
                (run_id, data, received_at)
            )
        except Exception as e:
            logger.error(f"Error queueing MQTT message: {e}")

    try:
        mqtt_subscriber = await get_mqtt_subscriber()
        
        while True:
            try:
                # Update subscriptions based on current active runs
                current_runs = set(RUNS.keys())
                
                # Subscribe to new runs
                new_runs = current_runs - subscribed_runs
                for run_id in new_runs:
                    mqtt_subscriber.subscribe_to_run(run_id, on_message)
                    subscribed_runs.add(run_id)
                    logger.info(f"Subscribed to MQTT topic for run {run_id}")
                
                # Unsubscribe from stopped runs
                stopped_runs = subscribed_runs - current_runs
                for run_id in stopped_runs:
                    mqtt_subscriber.unsubscribe_from_run(run_id)
                    subscribed_runs.discard(run_id)
                    logger.info(f"Unsubscribed from MQTT topic for run {run_id}")
                
                # Process any messages in the queue with a short timeout
                try:
                    run_id, data, received_at = await asyncio.wait_for(
                        message_queue.get(), timeout=1.0
                    )
                    
                    # Wrap the data with runId for client-side demultiplexing
                    envelope = {
                        "runId": run_id,
                        "data": data,
                        "received_at": received_at,
                    }
                    yield f"data: {json.dumps(envelope)}\n\n"
                    
                except asyncio.TimeoutError:
                    # No message received, send heartbeat
                    yield f": heartbeat\n\n"
                    
            except Exception as e:
                logger.error(f"Error in multiplexed metadata generator: {e}")
                yield f": error - {e}\n\n"
                await asyncio.sleep(1)
                
    finally:
        # Cleanup subscriptions when generator is closed
        mqtt_subscriber = await get_mqtt_subscriber()
        for run_id in subscribed_runs:
            mqtt_subscriber.unsubscribe_from_run(run_id)
        logger.info("Cleaned up MQTT subscriptions")


@router.get("/runs/metadata-stream")
async def multiplexed_metadata_stream() -> StreamingResponse:
    """Multiplexed SSE stream that provides metadata for all active runs."""
    logger.info("Multiplexed metadata stream requested")
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Cache-Control",
    }
    return StreamingResponse(
        _multiplexed_metadata_generator(),
        media_type="text/event-stream",
        headers=headers,
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> RunInfo:
    """Get details of a specific run."""
    info = RUNS.get(run_id)
    if not info:
        raise HTTPException(status_code=404, detail={"message": "Run not found"})
    return info


@router.delete("/runs/{run_id}")
async def stop_run(run_id: str) -> dict[str, str]:
    """Stop a running pipeline."""
    info = RUNS.get(run_id)
    if not info:
        raise HTTPException(status_code=404, detail={"message": "Run not found"})
    stop_url = f"{PIPELINE_SERVER_URL.rstrip('/')}/pipelines/{info.pipelineId}"

    # Try to stop pipeline on backend, but always remove from internal list
    # A failure (502) usually means the pipeline is already stopped
    try:
        http_json("DELETE", stop_url)
    except HTTPException:
        # Pipeline may already be stopped or unreachable - continue cleanup
        pass

    RUNS.pop(run_id, None)
    return {"status": "stopped", "runId": run_id}
