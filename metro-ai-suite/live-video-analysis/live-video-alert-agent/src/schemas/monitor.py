# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Domain schemas for alert configuration and VLM results.
"""

from __future__ import annotations

import re
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class EscalationConfig(BaseModel):
    """Escalation rule: after N consecutive YES detections, fire extra tools."""
    threshold_consecutive: int = Field(
        default=3,
        ge=2,
        description="Number of consecutive YES detections before escalation",
    )
    additional_tools: List[str] = Field(
        default_factory=list,
        description="Extra tool names to invoke on escalation",
    )


class AlertConfig(BaseModel):
    """
    Full configuration for a single named alert.

    Example JSON (resources/alerts.json entry):
    {
        "name": "Fire Detection",
        "prompt": "Is there visible fire or smoke in the image?",
        "enabled": true,
        "tools": ["log_alert", "capture_snapshot"],
        "escalation": {"threshold_consecutive": 3, "additional_tools": ["trigger_webhook"]}
    }
    """

    name: str = Field(..., min_length=1, max_length=64)
    prompt: str = Field(..., min_length=5, max_length=500)
    enabled: bool = True
    # Tool names to invoke when this alert fires (answer == YES).
    tools: List[str] = Field(default_factory=lambda: ["log_alert", "capture_snapshot"])
    # Per-tool argument overrides. Keys are tool names, values are dicts of
    # keyword arguments (supports {{variable}} template placeholders).
    tool_arguments: Dict[str, dict] = Field(default_factory=dict)
    escalation: Optional[EscalationConfig] = None

    @field_validator("name")
    @classmethod
    def name_no_special_chars(cls, v: str) -> str:
        if not re.match(r"^[\w\s\-\.]+$", v):
            raise ValueError("Alert name may only contain letters, digits, spaces, hyphens, dots, and underscores")
        return v


class AgentResult(BaseModel):
    """Structured YES/NO response returned by the VLM for one alert question."""
    answer: Literal["YES", "NO"] = Field(..., description="Exactly YES or NO")
    reason: str = Field(..., description="Brief explanation for the answer")


class AlertRuntimeState(BaseModel):
    """Runtime tracking state for one alert on one stream."""
    last_answer: Literal["YES", "NO"] = "NO"
    consecutive_yes: int = 0
    consecutive_no: int = 0    # tracks consecutive NO answers during an active alert
    last_action_ts: Optional[float] = None   # monotonic time of last tool execution
    last_transition_ts: Optional[float] = None  # monotonic time of last YES→NO or NO→YES
