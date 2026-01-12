# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from .enums import WeatherType


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