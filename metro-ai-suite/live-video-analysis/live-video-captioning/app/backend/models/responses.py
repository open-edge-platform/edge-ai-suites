# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Optional, List, Literal
from pydantic import BaseModel


class RunInfo(BaseModel):
    runId: str
    pipelineId: str
    peerId: str
    mqttTopic: str
    modelName: Optional[str] = None
    pipelineName: Optional[str] = None
    runName: Optional[str] = None
    prompt: Optional[str] = None
    maxTokens: Optional[int] = None
    rtspUrl: Optional[str] = None


class ModelList(BaseModel):
    models: list[str]


class PipelineInfo(BaseModel):
    pipeline_name: str
    pipeline_type: Literal["detection", "non-detection"]


class PipelineInfoList(BaseModel):
    pipelines: List[PipelineInfo]