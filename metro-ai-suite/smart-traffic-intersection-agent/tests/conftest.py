# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Shared test fixtures and configuration for pytest."""

import os
import sys
import pytest

# Add src directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set up mock environment variables for testing."""
    monkeypatch.setenv("INTERSECTION_NAME", "Test-Intersection")
    monkeypatch.setenv("INTERSECTION_LATITUDE", "37.7749")
    monkeypatch.setenv("INTERSECTION_LONGITUDE", "-122.4194")
    monkeypatch.setenv("MQTT_HOST", "localhost")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setenv("WEATHER_MOCK", "true")
    monkeypatch.setenv("HIGH_DENSITY_THRESHOLD", "10")
    monkeypatch.setenv("MODERATE_DENSITY_THRESHOLD", "5")


@pytest.fixture
def sample_traffic_data():
    """Sample traffic data for testing."""
    return {
        "intersection_id": "test-intersection-001",
        "timestamp": "2026-01-22T10:00:00Z",
        "directions": {
            "north": {"vehicle_count": 5, "density": "NORMAL"},
            "south": {"vehicle_count": 8, "density": "MODERATE"},
            "east": {"vehicle_count": 12, "density": "HIGH"},
            "west": {"vehicle_count": 3, "density": "NORMAL"}
        },
        "total_vehicles": 28
    }


@pytest.fixture
def sample_weather_data():
    """Sample weather data for testing."""
    return {
        "temperature": 55,
        "short_forecast": "Sunny",
        "conditions": "Cloudy conditions with 5 mph winds from the NW. 10% chance of precipitation.",
        "is_precipitation": False,
        "precipitation": False,
        "wind_speed": "5 mph",
        "wind_direction": "NW"
    }


@pytest.fixture
def sample_vlm_response():
    """Sample VLM analysis response for testing."""
    return {
        "analysis": "Traffic flow is moderate with higher density on the east approach.",
        "alerts": [
            {
                "alert_type": "congestion",
                "level": "warning",
                "description": "East approach experiencing high traffic density",
                "weather_related": False
            }
        ],
        "recommendations": [
            {
                "recommendation": "Consider extending green light duration for east-west traffic"
            }
        ]
    }
