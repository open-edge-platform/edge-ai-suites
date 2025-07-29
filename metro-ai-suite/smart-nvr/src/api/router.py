# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from api.endpoints.frigate_api import FrigateService
from api.endpoints.summarization_api import SummarizationService
from service.vms_service import VmsService
from service import redis_store

router = APIRouter()
frigate_service = FrigateService()
summarization_service = SummarizationService()
vms_service = VmsService(frigate_service, summarization_service)


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


@router.post("/rules/")
async def add_rule(rule: Rule, request: Request):
    success = await redis_store.add_rule(request, rule.id, rule.dict())
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
