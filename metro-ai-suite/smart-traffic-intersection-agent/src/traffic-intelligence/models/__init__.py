"""Data models for traffic intelligence service."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any
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

@dataclass
class WeatherData:
    """Weather information for traffic analysis."""
    name: str                    # Current weather period name (e.g., "This Afternoon")
    temperature: int             # Temperature value
    temperature_unit: str        # Temperature unit (F/C)
    detailed_forecast: str       # Detailed weather description
    fetched_at: datetime         # When weather data was retrieved
    is_precipitation: bool = False  # Whether there's rain/snow
    is_mock: bool = False           # Whether this is mock data
    wind_speed: str = "0 mph"        # Wind speed (e.g., "5 mph", "0 to 5 mph")
    wind_direction: str = "N"        # Wind direction (e.g., "NE", "SW")
    short_forecast: str = "Clear"    # Short weather description (e.g., "Sunny")
    wind_info: str = "0mph/N"        # Combined wind speed and direction (e.g., "3mph/W")
    precipitation_prob: float = 0.0  # Precipitation probability percentage (0-100)
    dewpoint: Optional[float] = None  # Dewpoint in Celsius
    relative_humidity: Optional[float] = None  # Relative humidity percentage (0-100)
    is_daytime: Optional[bool] = None  # Whether it's daytime
    start_time: Optional[str] = None   # Start time of the forecast period
    end_time: Optional[str] = None     # End time of the forecast period
    is_cached: bool = False          # Whether this data was served from cache
    weather_type: WeatherType = WeatherType.CLEAR  # Type of weather condition


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
class TrafficIntelligenceResponse:
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


class TrafficState(Enum):
    """Traffic state enumeration."""
    NORMAL = "normal"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


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