"""
Data classes for the RSU Monitoring System
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class RegionCount:
    """Count data for a specific region"""
    vehicle: int
    pedestrian: int


@dataclass
class TrafficContext:
    """Traffic analysis context information"""
    analysis_period: Dict[str, str]
    avg_densities: Dict[str, int]
    peak_densities: Dict[str, int]


@dataclass
class VLMAnalysis:
    """Vehicle Learning Model analysis data"""
    analysis: str
    high_density_directions: List[str]
    analysis_timestamp: str
    current_high_directions: List[str]
    analysis_age_minutes: float
    traffic_context: TrafficContext
    alerts: List[str]  # Can contain strings or structured alert objects
    recommendations: Optional[List[str]] = None


@dataclass
class WeatherData:
    """Weather information"""
    timestamp: str
    temperature_fahrenheit: float
    humidity_percent: int
    precipitation_prob: float
    wind_speed_mph: float
    wind_direction_degrees: int
    conditions: str
    # New hourly forecast fields
    dewpoint: Optional[float] = None                  # Dewpoint in Celsius
    relative_humidity: Optional[float] = None         # Relative humidity percentage from API
    is_daytime: Optional[bool] = None                 # Whether it's daytime
    start_time: Optional[str] = None                  # Start time of the forecast period
    end_time: Optional[str] = None                    # End time of the forecast period
    detailed_forecast: Optional[str] = None           # Detailed forecast description
    temperature_unit: str = "F"                       # Temperature unit


@dataclass
class CameraData:
    """Camera feed information"""
    camera_id: str
    direction: str
    timestamp: str
    image_base64: Optional[str] = None


@dataclass
class IntersectionData:
    """Main intersection traffic data"""
    intersection_id: str
    intersection_name: str
    latitude: float
    longitude: float
    timestamp: str
    northbound_density: int
    southbound_density: int
    eastbound_density: int
    westbound_density: int
    total_density: int
    region_counts: Dict[str, RegionCount]
    total_pedestrian_count: Optional[int] = None  # Direct from API
    north_timestamp: Optional[str] = None
    south_timestamp: Optional[str] = None
    east_timestamp: Optional[str] = None
    west_timestamp: Optional[str] = None


@dataclass
class MonitoringData:
    """Complete monitoring system data"""
    timestamp: str
    intersection_id: str
    data: IntersectionData
    camera_images: Dict[str, CameraData]
    vlm_analysis: VLMAnalysis
    weather_data: WeatherData
    
    def get_total_vehicles(self) -> int:
        """Get total vehicle count across all regions"""
        return sum(region.vehicle for region in self.data.region_counts.values())
    
    def get_total_pedestrians(self) -> int:
        """Get total pedestrian count - prefer API count if available, otherwise sum regions"""
        if self.data.total_pedestrian_count is not None:
            return self.data.total_pedestrian_count
        return sum(region.pedestrian for region in self.data.region_counts.values())
    
    def get_traffic_status(self) -> str:
        """Get overall traffic status based on density"""
        max_density = max(
            self.data.northbound_density,
            self.data.southbound_density,
            self.data.eastbound_density,
            self.data.westbound_density
        )
        
        if max_density >= 5:
            return "HEAVY"
        elif max_density >= 3:
            return "MODERATE"
        else:
            return "LIGHT"
    
    def get_busy_directions(self) -> List[str]:
        """Get directions with high traffic density (>= 3)"""
        directions = []
        if self.data.northbound_density >= 3:
            directions.append("Northbound")
        if self.data.southbound_density >= 3:
            directions.append("Southbound")
        if self.data.eastbound_density >= 3:
            directions.append("Eastbound")
        if self.data.westbound_density >= 3:
            directions.append("Westbound")
        return directions