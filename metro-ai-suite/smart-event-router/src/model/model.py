# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel


class Sampling(BaseModel):
    chunkDuration: int
    samplingFrame: int


class Evam(BaseModel):
    evamPipeline: str


class SummaryPayload(BaseModel):
    videoId: str
    title: str
    sampling: Sampling
    evam: Evam
