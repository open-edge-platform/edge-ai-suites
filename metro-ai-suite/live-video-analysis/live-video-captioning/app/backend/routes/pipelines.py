# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter
from ..models import PipelineInfo, PipelineInfoList
from ..services import discover_pipelines_remote

router = APIRouter(prefix="/api", tags=["pipelines"])


@router.get("/pipelines", response_model=PipelineInfoList)
async def list_pipelines() -> PipelineInfoList:
    """List available pipelines from the pipeline server, classified and filtered."""
    items = discover_pipelines_remote()  # List[Dict[str, str]]
    return PipelineInfoList(pipelines=[PipelineInfo(**it) for it in items])