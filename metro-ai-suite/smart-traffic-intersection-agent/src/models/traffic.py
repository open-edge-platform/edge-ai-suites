# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional
from .enums import TrafficState
from .vlm import VLMAnalysisData
from .weather import WeatherData


@dataclass
class CameraImage:
    """Camera image data from MQTT."""
    camera_id: str
    direction: str           # north, south, east, west
    image_base64: str
    timestamp: Optional[datetime] = None
    image_size_bytes: Optional[int] = None


@dataclass
class IntersectionData:
    """Core intersection traffic data structure based on data.json schema."""
    intersection_id: str         # UUID of the intersection
    intersection_name: str       # Human-readable name
    latitude: float              # GPS coordinates
    longitude: float
    timestamp: datetime          # Data timestamp

    # Camera density counts by direction
    north_camera: int = 0
    south_camera: int = 0
    east_camera: int = 0
    west_camera: int = 0
    total_density: int = 0

    # Intersection-level traffic status (HIGH, MODERATE, NORMAL)
    intersection_status: str = "NORMAL"

    # Pedestrian counts by direction
    north_pedestrian: int = 0
    south_pedestrian: int = 0
    east_pedestrian: int = 0
    west_pedestrian: int = 0
    total_pedestrian_count: int = 0

    # Timestamp of each directional count
    north_timestamp: Optional[datetime] = None
    south_timestamp: Optional[datetime] = None
    east_timestamp: Optional[datetime] = None
    west_timestamp: Optional[datetime] = None


@dataclass
class TrafficIntersectionAgentResponse:
    """Complete traffic intelligence response matching data.json structure."""
    timestamp: str               # ISO format timestamp
    intersection_id: str         # UUID of intersection
    data: IntersectionData       # Core intersection data
    camera_images: Dict[str, Dict[str, Any]]  # Camera images by direction
    weather_data: WeatherData    # Weather information
    vlm_analysis: VLMAnalysisData  # VLM analysis with alerts
    response_age: Optional[float] = None


@dataclass
class CameraDataMessage:
    """MQTT camera data message structure."""
    camera_id: str
    intersection_id: str
    direction: str
    vehicle_count: int
    pedestrian_count: int = 0
    timestamp: Optional[datetime] = None
    image_data: Optional[str] = None  # Base64 encoded image

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class TrafficSnapshot:
    """Snapshot of traffic data at a point in time."""
    timestamp: datetime
    intersection_id: str
    directional_counts: Dict[str, int]  # camera direction -> count
    total_count: int
    camera_images: Optional[Dict[str, CameraImage]] = None
    weather_conditions: Optional[WeatherData] = None
    intersection_data: Optional[IntersectionData] = None

    def calculate_total(self) -> int:
        """Calculate total traffic count."""
        return sum(self.directional_counts.values())


@dataclass
class TrafficTrend:
    """Traffic trend analysis over time."""
    intersection_id: str
    current_state: TrafficState
    trend_direction: str  # "increasing", "decreasing", "stable"
    change_percentage: float  # Percentage change from previous period
    peak_time: Optional[datetime] = None
    peak_count: Optional[int] = None
    duration_minutes: int = 0  # How long in current state


# Type aliases for better code readability
CameraTopics = List[str]
DirectionalCounts = Dict[str, int]  # direction -> count
CameraImagesDict = Dict[str, CameraImage]  # direction -> image
