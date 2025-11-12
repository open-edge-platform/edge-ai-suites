
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
# --- Camera Watcher API (moved to end for formatting) ---

from typing import List, Dict
from service.directory_watcher import set_camera_watcher_mapping, get_enabled_cameras
from service.directory_watcher import upload_videos_to_dataprep
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from pydantic import BaseModel
from api.endpoints.frigate_api import FrigateService
from api.endpoints.summarization_api import SummarizationService
from service.vms_service import VmsService
from service import redis_store
import requests

class CameraWatcherRequest(BaseModel):
    cameras: List[Dict[str, bool]]

router = APIRouter()
frigate_service = FrigateService()
summarization_service = SummarizationService()
vms_service = VmsService(frigate_service, summarization_service)
try:  # Keep backward compatibility if VSS_SEARCH_URL still defined elsewhere
    from config import VSS_SEARCH_URL  # type: ignore
except Exception:
    # Fallback: derive from VIDEO_UPLOAD_ENDPOINT if present
    VSS_SEARCH_URL = settings.VIDEO_UPLOAD_ENDPOINT or ""

@router.get("/health", summary="Health check for NVR Event Router service")
async def health_check():
    """
    Basic health check endpoint for Docker Compose or monitoring.
    Returns 200 OK if service is running.
    """
    return {"status": "healthy", "service": "nvr-event-router"}

@router.get("/cameras", summary="Get list of camera names")
async def get_cameras():
    return frigate_service.get_camera_names()


@router.get("/events", summary="Get list of events for a specific camera")
async def get_camera_events(camera: str):
    return await frigate_service.get_camera_events(camera)

@router.get("/summary/{camera_name}", summary="Stream video using clip.mp4 API")
async def summarize_video(
    camera_name: str, start_time: float, end_time: float, download: bool = False
):
    return await vms_service.summarize(camera_name, start_time, end_time)


@router.get(
    "/search-embeddings/{camera_name}", summary="Stream video using clip.mp4 API"
)
async def search_video_embeddings(
    camera_name: str, start_time: float, end_time: float, download: bool = False
):
    return await vms_service.search_embeddings(camera_name, start_time, end_time)


@router.get("/summary-status/{summary_id}", summary="Get the summary using id")
async def get_summary(summary_id: str):
    return vms_service.summary(summary_id)


from service.redis_store import (
    get_rules,
    get_summary_ids,
    get_summary_result,
    get_search_results_by_rule,
)


@router.get("/rules/responses/")
async def get_all_rule_summaries(request: Request):
    rules = await get_rules(request)
    output = {}

    for rule in rules:
        rule_id = rule["id"]

        # Skip rules where the action contains "search"
        if "search" in rule.get("action", "").lower():
            continue

        summary_ids = await get_summary_ids(request, rule_id)
        summaries = {}

        for sid in summary_ids:
            result = vms_service.summary(sid)
            summaries[sid] = result or "Pending"

        output[rule_id] = summaries

    return output


@router.get("/rules/search-responses/")
async def get_search_responses(request: Request):
    """
    Fetch search responses for all rules with action 'search'.
    """
    output = {}

    try:
        rules = await get_rules(request)  # Fetch all rules

        for rule in rules:
            if rule.get("action") == "add to search":
                rule_id = rule["id"]
                results = await get_search_results_by_rule(rule_id, request)
                output[rule_id] = results or [{"status": "Pending"}]

        return output

    except Exception as e:
        return {"error": str(e)}


class Rule(BaseModel):
    id: str
    label: str
    action: str
    camera: str | None = None
    source: str | None = None
    count: int | None = None


@router.post("/rules/")
async def add_rule(rule: Rule, request: Request):
    success = await redis_store.add_rule(
        request,
        rule.id,
        rule.dict(exclude_none=True),
    )
    if not success:
        raise HTTPException(status_code=400, detail="Rule ID already exists")
    return {"message": "Rule added", "rule": rule}


@router.get("/rules/")
async def list_rules(request: Request):
    return await redis_store.get_rules(request)


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: str, request: Request):
    rule = await redis_store.get_rule(request, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str, request: Request):
    deleted = await redis_store.delete_rule(request, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"message": f"Rule {rule_id} deleted"}

@router.post("/watchers/enable", summary="Enable/disable directory watcher for cameras")
async def set_camera_watchers(
    req: CameraWatcherRequest = Body(...),
    request: Request = None
):
    # Step 1: Check if Video Search Service is reachable
    try:
        health_url = f"{VSS_SEARCH_URL}/manager/search/watched"
        response = requests.get(health_url, timeout=5)
        if response.status_code != 200:
            raise Exception(f"Unexpected status: {response.status_code}")
    except Exception as e:
        # Log and return error
        error_msg = f"Video search service is unreachable, please check and try again."
        raise HTTPException(status_code=503, detail=error_msg)

    # Step 2: Proceed with watcher setup if service reachable
    mapping = {k: v for d in req.cameras for k, v in d.items()}
    debounce_time = 5  # You can make this configurable if needed

    updated = await set_camera_watcher_mapping(
        mapping,
        debounce_time,
        upload_videos_to_dataprep,
        request
    )

    return {
        "mapping": updated,
        "enabled": [k for k, v in updated.items() if v],
        "disabled": [k for k, v in updated.items() if not v],
    }

@router.get("/watchers/mapping", summary="Get current camera watcher enable/disable mapping")
async def get_camera_watcher_mapping(request: Request = None):
    """Return merged camera watcher mapping.

    Priority order:
      1. In-memory runtime mapping (reflects changes since process start)
      2. Persisted Redis mapping (authoritative across restarts)

    If Redis is unavailable, fall back to in-memory only.
    """
    runtime_mapping = get_enabled_cameras() or {}
    merged = runtime_mapping
    try:
        from service.redis_store import load_camera_watcher_mapping
        persisted = await load_camera_watcher_mapping(request)
        if persisted:
            # Merge so that any runtime changes override persisted values
            merged = {**persisted, **runtime_mapping}
    except Exception as e:
        # Include error info but still return something useful
        return {"mapping": merged, "warning": f"Redis load failed: {e}"}
    return {"mapping": merged}


@router.get("/watchers/enable", summary="Alias to fetch current watcher mapping (GET)")
async def get_camera_watcher_mapping_alias(request: Request = None):
    """Provide a GET alias on /watchers/enable so users who query that endpoint directly
    (expecting state) receive the same response as /watchers/mapping.
    """
    return await get_camera_watcher_mapping(request)