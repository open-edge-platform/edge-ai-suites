# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from pydantic import BaseModel, Field
from typing import Dict, Literal

class AgentResult(BaseModel):
    """Structured Yes/No response for a single agent question"""
    answer: Literal["YES", "NO"] = Field(..., description="Must be exactly YES or NO")
    reason: str = Field(..., description="Brief explanation for the answer")
