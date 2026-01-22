# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
from .enums import AlertLevel, AlertType


@dataclass
class VLMAlert:
    """Individual alert from VLM analysis."""
    alert_type: AlertType
    level: AlertLevel
    description: str
    weather_related: bool = False


@dataclass
class VLMAnalysisData:
    """VLM analysis results with structured traffic and alert data."""
    traffic_summary: str                     # General traffic conditions summary
    alerts: List[VLMAlert]                  # Structured alerts list
    recommendations: List[str] = None        # Traffic management recommendations
    analysis_timestamp: Optional[datetime] = None