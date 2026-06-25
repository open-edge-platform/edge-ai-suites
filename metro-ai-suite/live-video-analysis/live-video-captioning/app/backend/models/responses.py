# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Optional, List, Literal
from pydantic import BaseModel


class RunInfo(BaseModel):
    runId: str
    pipelineId: str
    peerId: str
    mqttTopic: str
    status: str = "running"
    modelName: Optional[str] = None
    pipelineName: Optional[str] = None
    runName: Optional[str] = None
    prompt: Optional[str] = None
    maxTokens: Optional[int] = None
    rtspUrl: Optional[str] = None
    frameRate: Optional[int] = None
    chunkSize: Optional[int] = None
    frameWidth: Optional[int] = None
    frameHeight: Optional[int] = None


class ModelList(BaseModel):
    models: list[str]


class PipelineInfo(BaseModel):
    pipeline_name: str
    pipeline_display_name: Optional[str] = None
    pipeline_type: Literal["detection", "non-detection"]
    pipeline_default: bool = False


class PipelineInfoList(BaseModel):
    pipelines: List[PipelineInfo]


class CameraDevice(BaseModel):
    device_path: str
    device_name: Optional[str] = None
    pixel_formats: List[str]
    usable_formats: List[str]
    has_usable_format: bool


class CameraDeviceList(BaseModel):
    cameras: List[CameraDevice]
