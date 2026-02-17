# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for API routes."""

import pytest
import os
import sys
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from api.routes import router, get_data_aggregator, get_weather_service
from models.traffic import IntersectionData, TrafficIntersectionAgentResponse
from models.vlm import VLMAnalysisData, VLMAlert
from models.weather import WeatherData
from models.enums import AlertLevel, AlertType


# ============== Fixtures ==============

@pytest.fixture
def sample_intersection_data():
    """Create sample intersection data."""
    return IntersectionData(
        intersection_id="INT-001",
        intersection_name="Main St & 1st Ave",
        latitude=37.7749,
        longitude=-122.4194,
        timestamp=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        north_camera=5,
        south_camera=3,
        east_camera=8,
        west_camera=2,
        total_density=18,
        intersection_status="MODERATE",
        north_pedestrian=2,
        south_pedestrian=1,
        east_pedestrian=3,
        west_pedestrian=0,
        total_pedestrian_count=6,
        north_timestamp=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        south_timestamp=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        east_timestamp=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        west_timestamp=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_vlm_analysis():
    """Create sample VLM analysis data."""
    return VLMAnalysisData(
        traffic_summary="Moderate traffic with higher density in east direction.",
        alerts=[
            VLMAlert(
                alert_type=AlertType.CONGESTION,
                level=AlertLevel.WARNING,
                description="Heavy traffic detected in east direction",
                weather_related=False
            )
        ],
        recommendations=["Consider alternative routes to avoid east direction"],
        analysis_timestamp=datetime(2025, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
    )


@pytest.fixture
def sample_weather_data():
    """Create sample weather data."""
    return WeatherData(
        name="Current Hour",
        temperature=72,
        temperature_unit="F",
        detailed_forecast="Partly cloudy with mild temperatures",
        fetched_at=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        is_precipitation=False,
        is_mock=False,
        wind_speed="8 mph",
        wind_direction="S",
        short_forecast="Partly Cloudy",
        wind_info="8mph/S",
        precipitation_prob=10.0,
        dewpoint=15.0,
        relative_humidity=45.0,
        is_daytime=True
    )


@pytest.fixture
def sample_traffic_response(sample_intersection_data, sample_vlm_analysis, sample_weather_data):
    """Create sample traffic intelligence response."""
    return TrafficIntersectionAgentResponse(
        timestamp="2025-01-01T10:00:00Z",
        intersection_id="INT-001",
        data=sample_intersection_data,
        camera_images={
            "north_camera": {"camera_id": "cam1", "direction": "north", "image_base64": "base64data"},
            "east_camera": {"camera_id": "cam2", "direction": "east", "image_base64": "base64data"}
        },
        weather_data=sample_weather_data,
        vlm_analysis=sample_vlm_analysis,
        response_age=2.5
    )


@pytest.fixture
def mock_data_aggregator():
    """Create mock data aggregator service."""
    return Mock()


@pytest.fixture
def mock_weather_service():
    """Create mock weather service."""
    return Mock()


@pytest.fixture
def app(mock_data_aggregator, mock_weather_service):
    """Create FastAPI test app with router."""
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    
    # Set up app state with mocked services
    app.state.data_aggregator = mock_data_aggregator
    app.state.weather_service = mock_weather_service
    
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


# ============== Dependency Tests ==============

class TestDependencies:
    """Test cases for dependency injection functions."""

    def test_get_data_aggregator(self, app):
        """Test get_data_aggregator returns data aggregator from app state."""
        mock_request = Mock()
        mock_request.app = app
        
        result = get_data_aggregator(mock_request)
        
        assert result == app.state.data_aggregator

    def test_get_weather_service(self, app):
        """Test get_weather_service returns weather service from app state."""
        mock_request = Mock()
        mock_request.app = app
        
        result = get_weather_service(mock_request)
        
        assert result == app.state.weather_service


# ============== GET /traffic/current Tests ==============

class TestGetCurrentTrafficIntelligence:
    """Test cases for GET /traffic/current endpoint."""

    def test_get_current_traffic_success(
        self, client, mock_data_aggregator, mock_weather_service, 
        sample_traffic_response, sample_weather_data
    ):
        """Test successful retrieval of current traffic data."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["intersection_id"] == "INT-001"
        assert data["timestamp"] == "2025-01-01T10:00:00Z"
        assert "data" in data
        assert "weather_data" in data
        assert "vlm_analysis" in data
        assert "camera_images" in data

    def test_get_current_traffic_includes_intersection_data(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response includes correct intersection data."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert data["data"]["intersection_name"] == "Main St & 1st Ave"
        assert data["data"]["total_density"] == 18
        assert data["data"]["north_camera"] == 5
        assert data["data"]["east_camera"] == 8
        assert data["data"]["total_pedestrian_count"] == 6

    def test_get_current_traffic_includes_vlm_analysis(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response includes VLM analysis with alerts."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert "vlm_analysis" in data
        assert data["vlm_analysis"]["traffic_summary"] == "Moderate traffic with higher density in east direction."
        assert len(data["vlm_analysis"]["alerts"]) == 1
        assert data["vlm_analysis"]["alerts"][0]["level"] == "warning"
        assert data["vlm_analysis"]["alerts"][0]["alert_type"] == "congestion"

    def test_get_current_traffic_without_images(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response excludes camera images when images=false."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current?images=false")
        data = response.json()
        
        assert "camera_images" not in data

    def test_get_current_traffic_with_images_default(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response includes camera images by default."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert "camera_images" in data
        assert "north_camera" in data["camera_images"]

    def test_get_current_traffic_no_data_available(
        self, client, mock_data_aggregator, mock_weather_service
    ):
        """Test 404 response when no traffic data available."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=None
        )
        
        response = client.get("/api/v1/traffic/current")
        
        assert response.status_code == 404
        assert response.json()["detail"] == "No traffic data available"

    def test_get_current_traffic_internal_error(
        self, client, mock_data_aggregator, mock_weather_service
    ):
        """Test 500 response on internal server error."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        
        response = client.get("/api/v1/traffic/current")
        
        assert response.status_code == 500
        assert response.json()["detail"] == "Internal server error"

    def test_get_current_traffic_includes_weather_data(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response includes weather data."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert "weather_data" in data
        assert data["weather_data"]["temperature"] == 72
        assert data["weather_data"]["short_forecast"] == "Partly Cloudy"

    def test_get_current_traffic_includes_response_age(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response includes response age."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert data["response_age"] == 2.5


class TestGetCurrentTrafficEdgeCases:
    """Test edge cases for traffic endpoint."""

    def test_get_current_traffic_empty_alerts(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response with empty alerts list."""
        sample_traffic_response.vlm_analysis.alerts = []
        
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert data["vlm_analysis"]["alerts"] == []

    def test_get_current_traffic_no_recommendations(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response with no recommendations."""
        sample_traffic_response.vlm_analysis.recommendations = None
        
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert data["vlm_analysis"]["recommendations"] == []

    def test_get_current_traffic_null_analysis_timestamp(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response with null analysis timestamp."""
        sample_traffic_response.vlm_analysis.analysis_timestamp = None
        
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert data["vlm_analysis"]["analysis_timestamp"] is None

    def test_get_current_traffic_null_response_age(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response with null response age."""
        sample_traffic_response.response_age = None
        
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert data["response_age"] is None

    def test_get_current_traffic_multiple_alerts(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response with multiple alerts."""
        sample_traffic_response.vlm_analysis.alerts = [
            VLMAlert(
                alert_type=AlertType.CONGESTION,
                level=AlertLevel.WARNING,
                description="Heavy traffic in east",
                weather_related=False
            ),
            VLMAlert(
                alert_type=AlertType.WEATHER_RELATED,
                level=AlertLevel.INFO,
                description="Rain expected",
                weather_related=True
            ),
            VLMAlert(
                alert_type=AlertType.ACCIDENT,
                level=AlertLevel.CRITICAL,
                description="Accident reported",
                weather_related=False
            )
        ]
        
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        assert len(data["vlm_analysis"]["alerts"]) == 3
        assert data["vlm_analysis"]["alerts"][0]["level"] == "warning"
        assert data["vlm_analysis"]["alerts"][1]["level"] == "info"
        assert data["vlm_analysis"]["alerts"][2]["level"] == "critical"


class TestGetCurrentTrafficDataValidation:
    """Test data validation in responses."""

    def test_response_contains_all_directional_data(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test response contains all directional traffic data."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        # Check all directional camera counts
        assert "north_camera" in data["data"]
        assert "south_camera" in data["data"]
        assert "east_camera" in data["data"]
        assert "west_camera" in data["data"]
        
        # Check all directional pedestrian counts
        assert "north_pedestrian" in data["data"]
        assert "south_pedestrian" in data["data"]
        assert "east_pedestrian" in data["data"]
        assert "west_pedestrian" in data["data"]
        
        # Check all directional timestamps
        assert "north_timestamp" in data["data"]
        assert "south_timestamp" in data["data"]
        assert "east_timestamp" in data["data"]
        assert "west_timestamp" in data["data"]

    def test_response_alert_structure(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test alert objects have correct structure."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        alert = data["vlm_analysis"]["alerts"][0]
        
        assert "alert_type" in alert
        assert "level" in alert
        assert "description" in alert
        assert "weather_related" in alert

    def test_response_timestamp_format(
        self, client, mock_data_aggregator, mock_weather_service,
        sample_traffic_response, sample_weather_data
    ):
        """Test timestamps are in ISO format."""
        mock_data_aggregator.get_current_traffic_intelligence = AsyncMock(
            return_value=sample_traffic_response
        )
        mock_weather_service.get_current_weather = AsyncMock(
            return_value=sample_weather_data
        )
        
        response = client.get("/api/v1/traffic/current")
        data = response.json()
        
        # Verify timestamp can be parsed as ISO format
        from datetime import datetime
        try:
            datetime.fromisoformat(data["data"]["timestamp"].replace('Z', '+00:00'))
        except ValueError:
            pytest.fail("Timestamp is not in valid ISO format")
