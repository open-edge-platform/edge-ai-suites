# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from enum import Enum

class AlertLevel(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"  
    CRITICAL = "critical"


class AlertType(Enum):
    """Types of traffic alerts."""
    CONGESTION = "congestion"
    WEATHER_RELATED = "weather_related"
    ROAD_CONDITION = "road_condition"
    ACCIDENT = "accident"
    MAINTENANCE = "maintenance"
    NORMAL = "normal"

class WeatherType(Enum):
    """Types of weather conditions."""
    CLEAR = "clear"

class TrafficState(Enum):
    """Traffic state enumeration."""
    NORMAL = "normal"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"