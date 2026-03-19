# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Data Aggregator Service."""

import pytest
import os
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.data_aggregator import DataAggregatorService
from models import (
    CameraDataMessage, CameraImage, TrafficSnapshot, IntersectionData,
    WeatherData, VLMAnalysisData, VLMAlert
)


@pytest.fixture
def mock_config_service():
    """Create a mock ConfigService."""
    config = MagicMock()
    config.get_intersection_id.return_value = "test-intersection-id"
    config.get_intersection_name.return_value = "Test Intersection"
    config.get_intersection_coordinates.return_value = (33.3091336, -111.9353095)
    config.get_high_density_threshold.return_value = 5
    config.get_traffic_config.return_value = {"analysis_window_seconds": 30}
    return config


@pytest.fixture
def mock_vlm_service():
    """Create a mock VLMService."""
    vlm = MagicMock()
    vlm.analyze_traffic_non_blocking = AsyncMock()
    vlm.get_weather_details.return_value = WeatherData(
        name="Clear",
        temperature=72,
        temperature_unit="F",
        detailed_forecast="Sunny skies",
        fetched_at=datetime.now(timezone.utc),
        is_precipitation=False,
        is_mock=False
    )
    return vlm


@pytest.fixture
def data_aggregator(mock_config_service, mock_vlm_service):
    """Create DataAggregatorService instance with mocked dependencies."""
    return DataAggregatorService(mock_config_service, mock_vlm_service)


@pytest.fixture
def sample_camera_image():
    """Create a sample CameraImage."""
    return CameraImage(
        camera_id="camera1",
        direction="north",
        image_base64="base64encodedimage",
        timestamp=datetime.now(timezone.utc),
        image_size_bytes=1024
    )


@pytest.fixture
def sample_camera_data():
    """Create a sample CameraDataMessage."""
    return CameraDataMessage(
        camera_id="camera1",
        intersection_id="test-intersection-id",
        direction="north",
        vehicle_count=3,
        pedestrian_count=2,
        timestamp=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_vlm_analysis():
    """Create a sample VLMAnalysisData."""
    return VLMAnalysisData(
        traffic_summary="Normal traffic conditions",
        recommendations=["No action needed"],
        alerts=[],
        analysis_timestamp=datetime.now(timezone.utc)
    )


class TestDataAggregatorInitialization:
    """Test cases for DataAggregatorService initialization."""

    def test_init_creates_empty_data_stores(self, data_aggregator):
        """Test that initialization creates empty data stores."""
        assert data_aggregator.temp_camera_data == {}
        assert data_aggregator.temp_camera_images == {}
        assert data_aggregator.temp_intersection_data is None

    def test_init_creates_empty_vlm_analyzed_stores(self, data_aggregator):
        """Test that initialization creates empty VLM-analyzed stores."""
        assert data_aggregator.vlm_analyzed_camera_images == {}
        assert data_aggregator.vlm_analyzed_intersection_data is None
        assert data_aggregator.vlm_analyzed_weather_data is None

    def test_init_sets_last_analysis_time_to_zero(self, data_aggregator):
        """Test that last analysis time is initialized to zero."""
        assert data_aggregator.last_analysis_time == 0.0

    def test_init_sets_current_vlm_analysis_to_none(self, data_aggregator):
        """Test that current VLM analysis is initialized to None."""
        assert data_aggregator.current_vlm_analysis is None


class TestProcessCameraImage:
    """Test cases for process_camera_image method."""

    @pytest.mark.asyncio
    async def test_process_camera_image_stores_image(self, data_aggregator, sample_camera_image):
        """Test that camera image is stored in temp storage."""
        await data_aggregator.process_camera_image(sample_camera_image)
        
        assert "north" in data_aggregator.temp_camera_images
        assert data_aggregator.temp_camera_images["north"] == sample_camera_image

    @pytest.mark.asyncio
    async def test_process_camera_image_updates_existing(self, data_aggregator, sample_camera_image):
        """Test that new image overwrites existing for same direction."""
        await data_aggregator.process_camera_image(sample_camera_image)
        
        new_image = CameraImage(
            camera_id="camera1",
            direction="north",
            image_base64="newbase64image",
            timestamp=datetime.now(timezone.utc),
            image_size_bytes=2048
        )
        await data_aggregator.process_camera_image(new_image)
        
        assert data_aggregator.temp_camera_images["north"].image_base64 == "newbase64image"

    @pytest.mark.asyncio
    async def test_process_camera_image_multiple_directions(self, data_aggregator):
        """Test processing images from multiple directions."""
        directions = ["north", "south", "east", "west"]
        
        for direction in directions:
            image = CameraImage(
                camera_id=f"camera_{direction}",
                direction=direction,
                image_base64=f"base64_{direction}",
                timestamp=datetime.now(timezone.utc),
                image_size_bytes=1024
            )
            await data_aggregator.process_camera_image(image)
        
        assert len(data_aggregator.temp_camera_images) == 4
        for direction in directions:
            assert direction in data_aggregator.temp_camera_images


class TestProcessCameraData:
    """Test cases for process_camera_data method."""

    @pytest.mark.asyncio
    async def test_process_camera_data_stores_data(self, data_aggregator, sample_camera_data):
        """Test that camera data is stored in temp storage."""
        await data_aggregator.process_camera_data(sample_camera_data)
        
        assert "north" in data_aggregator.temp_camera_data
        assert data_aggregator.temp_camera_data["north"] == sample_camera_data

    @pytest.mark.asyncio
    async def test_process_camera_data_updates_intersection_data(self, data_aggregator, sample_camera_data):
        """Test that intersection data is updated after processing camera data."""
        await data_aggregator.process_camera_data(sample_camera_data)
        
        assert data_aggregator.temp_intersection_data is not None
        assert data_aggregator.temp_intersection_data.north_camera == 3

    @pytest.mark.asyncio
    async def test_process_camera_data_clears_after_all_directions(self, data_aggregator, mock_vlm_service, sample_vlm_analysis):
        """Test that temp data is cleared after all 4 directions are processed."""
        mock_vlm_service.analyze_traffic_non_blocking.return_value = sample_vlm_analysis
        
        directions = ["north", "south", "east", "west"]
        for direction in directions:
            camera_data = CameraDataMessage(
                camera_id=f"camera_{direction}",
                intersection_id="test-intersection-id",
                direction=direction,
                vehicle_count=2,
                pedestrian_count=1
            )
            await data_aggregator.process_camera_data(camera_data)
        
        # After all 4 directions, temp_camera_data should be cleared
        assert data_aggregator.temp_camera_data == {}


class TestUpdateTempIntersectionData:
    """Test cases for _update_temp_intersection_data method."""

    @pytest.mark.asyncio
    async def test_calculates_total_density(self, data_aggregator):
        """Test that total density is calculated correctly."""
        directions_counts = [("north", 3), ("south", 2), ("east", 4), ("west", 1)]
        
        for direction, count in directions_counts:
            camera_data = CameraDataMessage(
                camera_id=f"camera_{direction}",
                intersection_id="test-intersection-id",
                direction=direction,
                vehicle_count=count,
                pedestrian_count=0
            )
            data_aggregator.temp_camera_data[direction] = camera_data
        
        await data_aggregator._update_temp_intersection_data()
        
        assert data_aggregator.temp_intersection_data.total_density == 10

    @pytest.mark.asyncio
    async def test_calculates_intersection_status_high(self, data_aggregator, mock_config_service):
        """Test HIGH status when density exceeds 2/3 of threshold."""
        mock_config_service.get_high_density_threshold.return_value = 6
        
        # Total count of 5 is >= 6 * 2/3 = 4
        camera_data = CameraDataMessage(
            camera_id="camera_north",
            intersection_id="test-intersection-id",
            direction="north",
            vehicle_count=5,
            pedestrian_count=0
        )
        data_aggregator.temp_camera_data["north"] = camera_data
        
        await data_aggregator._update_temp_intersection_data()
        
        assert data_aggregator.temp_intersection_data.intersection_status == "HIGH"

    @pytest.mark.asyncio
    async def test_calculates_intersection_status_moderate(self, data_aggregator, mock_config_service):
        """Test MODERATE status when density is between 1/3 and 2/3 of threshold."""
        mock_config_service.get_high_density_threshold.return_value = 15
        
        # Total count of 6 is >= 15 * 1/3 = 5 but < 15 * 2/3 = 10
        camera_data = CameraDataMessage(
            camera_id="camera_north",
            intersection_id="test-intersection-id",
            direction="north",
            vehicle_count=6,
            pedestrian_count=0
        )
        data_aggregator.temp_camera_data["north"] = camera_data
        
        await data_aggregator._update_temp_intersection_data()
        
        assert data_aggregator.temp_intersection_data.intersection_status == "MODERATE"

    @pytest.mark.asyncio
    async def test_calculates_intersection_status_normal(self, data_aggregator, mock_config_service):
        """Test NORMAL status when density is below 1/3 of threshold."""
        mock_config_service.get_high_density_threshold.return_value = 15
        
        # Total count of 2 is < 15 * 1/3 = 5
        camera_data = CameraDataMessage(
            camera_id="camera_north",
            intersection_id="test-intersection-id",
            direction="north",
            vehicle_count=2,
            pedestrian_count=0
        )
        data_aggregator.temp_camera_data["north"] = camera_data
        
        await data_aggregator._update_temp_intersection_data()
        
        assert data_aggregator.temp_intersection_data.intersection_status == "NORMAL"

    @pytest.mark.asyncio
    async def test_calculates_total_pedestrian_count(self, data_aggregator):
        """Test that total pedestrian count is calculated correctly."""
        directions_peds = [("north", 2), ("south", 3), ("east", 1), ("west", 4)]
        
        for direction, ped_count in directions_peds:
            camera_data = CameraDataMessage(
                camera_id=f"camera_{direction}",
                intersection_id="test-intersection-id",
                direction=direction,
                vehicle_count=0,
                pedestrian_count=ped_count
            )
            data_aggregator.temp_camera_data[direction] = camera_data
        
        await data_aggregator._update_temp_intersection_data()
        
        assert data_aggregator.temp_intersection_data.total_pedestrian_count == 10


class TestCreateTempTrafficSnapshot:
    """Test cases for _create_temp_traffic_snapshot method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_intersection_data(self, data_aggregator):
        """Test returns None when no intersection data available."""
        snapshot = data_aggregator._create_temp_traffic_snapshot()
        assert snapshot is None

    @pytest.mark.asyncio
    async def test_creates_snapshot_with_directional_counts(self, data_aggregator):
        """Test creates snapshot with correct directional counts."""
        # Setup temp data
        for direction, count in [("north", 3), ("south", 2), ("east", 4), ("west", 1)]:
            camera_data = CameraDataMessage(
                camera_id=f"camera_{direction}",
                intersection_id="test-intersection-id",
                direction=direction,
                vehicle_count=count,
                pedestrian_count=0
            )
            data_aggregator.temp_camera_data[direction] = camera_data
        
        await data_aggregator._update_temp_intersection_data()
        snapshot = data_aggregator._create_temp_traffic_snapshot()
        
        assert snapshot is not None
        assert snapshot.directional_counts["north"] == 3
        assert snapshot.directional_counts["south"] == 2
        assert snapshot.directional_counts["east"] == 4
        assert snapshot.directional_counts["west"] == 1
        assert snapshot.total_count == 10


class TestCheckAnalysisTrigger:
    """Test cases for _check_analysis_trigger method."""

    @pytest.mark.asyncio
    async def test_no_trigger_when_no_intersection_data(self, data_aggregator, mock_vlm_service):
        """Test no VLM analysis triggered when no intersection data."""
        await data_aggregator._check_analysis_trigger()
        mock_vlm_service.analyze_traffic_non_blocking.assert_not_called()

    @pytest.mark.asyncio
    async def test_triggers_on_high_traffic(self, data_aggregator, mock_config_service, mock_vlm_service, sample_vlm_analysis):
        """Test VLM analysis triggered when traffic exceeds threshold."""
        mock_config_service.get_high_density_threshold.return_value = 5
        mock_vlm_service.analyze_traffic_non_blocking.return_value = sample_vlm_analysis
        
        # Create high density data
        camera_data = CameraDataMessage(
            camera_id="camera_north",
            intersection_id="test-intersection-id",
            direction="north",
            vehicle_count=10,  # > threshold of 5
            pedestrian_count=0
        )
        data_aggregator.temp_camera_data["north"] = camera_data
        await data_aggregator._update_temp_intersection_data()
        
        await data_aggregator._check_analysis_trigger()
        mock_vlm_service.analyze_traffic_non_blocking.assert_called_once()

    @pytest.mark.asyncio
    async def test_triggers_on_first_analysis(self, data_aggregator, mock_vlm_service, sample_vlm_analysis):
        """Test VLM analysis triggered on first run even with low traffic."""
        mock_vlm_service.analyze_traffic_non_blocking.return_value = sample_vlm_analysis
        
        camera_data = CameraDataMessage(
            camera_id="camera_north",
            intersection_id="test-intersection-id",
            direction="north",
            vehicle_count=1,  # Low traffic
            pedestrian_count=0
        )
        data_aggregator.temp_camera_data["north"] = camera_data
        await data_aggregator._update_temp_intersection_data()
        
        # First analysis (last_analysis_time == 0.0)
        await data_aggregator._check_analysis_trigger()
        mock_vlm_service.analyze_traffic_non_blocking.assert_called_once()


class TestTriggerVLMAnalysis:
    """Test cases for _trigger_vlm_analysis method."""

    @pytest.mark.asyncio
    async def test_saves_vlm_analyzed_data(self, data_aggregator, mock_vlm_service, sample_vlm_analysis):
        """Test that VLM analysis results are saved correctly."""
        mock_vlm_service.analyze_traffic_non_blocking.return_value = sample_vlm_analysis
        
        # Setup temp data
        camera_data = CameraDataMessage(
            camera_id="camera_north",
            intersection_id="test-intersection-id",
            direction="north",
            vehicle_count=5,
            pedestrian_count=2
        )
        data_aggregator.temp_camera_data["north"] = camera_data
        await data_aggregator._update_temp_intersection_data()
        
        await data_aggregator._trigger_vlm_analysis()
        
        assert data_aggregator.current_vlm_analysis == sample_vlm_analysis
        assert data_aggregator.last_analysis_time > 0

    @pytest.mark.asyncio
    async def test_handles_vlm_error_gracefully(self, data_aggregator, mock_vlm_service):
        """Test that VLM analysis errors are handled gracefully."""
        mock_vlm_service.analyze_traffic_non_blocking.side_effect = Exception("VLM Error")
        
        camera_data = CameraDataMessage(
            camera_id="camera_north",
            intersection_id="test-intersection-id",
            direction="north",
            vehicle_count=5,
            pedestrian_count=2
        )
        data_aggregator.temp_camera_data["north"] = camera_data
        await data_aggregator._update_temp_intersection_data()
        
        # Should not raise
        await data_aggregator._trigger_vlm_analysis()
        
        # Analysis should not be saved on error
        assert data_aggregator.current_vlm_analysis is None


class TestGetCurrentTrafficIntelligence:
    """Test cases for get_current_traffic_intelligence method."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_vlm_data(self, data_aggregator):
        """Test returns None when no VLM-analyzed data available."""
        result = await data_aggregator.get_current_traffic_intelligence()
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_response_with_vlm_data(self, data_aggregator, mock_vlm_service, sample_vlm_analysis):
        """Test returns complete response when VLM data available."""
        mock_vlm_service.analyze_traffic_non_blocking.return_value = sample_vlm_analysis
        
        # Setup and trigger analysis
        camera_data = CameraDataMessage(
            camera_id="camera_north",
            intersection_id="test-intersection-id",
            direction="north",
            vehicle_count=5,
            pedestrian_count=2
        )
        data_aggregator.temp_camera_data["north"] = camera_data
        
        camera_image = CameraImage(
            camera_id="camera_north",
            direction="north",
            image_base64="base64data",
            timestamp=datetime.now(timezone.utc),
            image_size_bytes=1024
        )
        data_aggregator.temp_camera_images["north"] = camera_image
        
        await data_aggregator._update_temp_intersection_data()
        await data_aggregator._trigger_vlm_analysis()
        
        result = await data_aggregator.get_current_traffic_intelligence()
        
        assert result is not None
        assert result.intersection_id == "test-intersection-id"
        assert result.vlm_analysis == sample_vlm_analysis


class TestGetDefaultWeather:
    """Test cases for _get_default_weather method."""

    def test_returns_default_weather_data(self, data_aggregator):
        """Test that default weather data is returned correctly."""
        weather = data_aggregator._get_default_weather()
        
        assert weather.name == "Unknown"
        assert weather.temperature == 72
        assert weather.temperature_unit == "F"
        assert weather.detailed_forecast == "Weather data unavailable"
        assert weather.is_mock is True


class TestGetServiceStatus:
    """Test cases for get_service_status method."""

    def test_returns_status_with_no_data(self, data_aggregator):
        """Test service status when no data is available."""
        status = data_aggregator.get_service_status()
        
        assert status["intersection_id"] == "test-intersection-id"
        assert status["intersection_name"] == "Test Intersection"
        assert status["current_traffic_density"] == 0
        assert status["current_pedestrian_count"] == 0
        assert status["analyzed_camera_directions"] == []
        assert status["active_analyzed_cameras"] == 0
        assert status["has_weather_data"] is False
        assert status["has_vlm_analysis"] is False

    @pytest.mark.asyncio
    async def test_returns_status_with_vlm_data(self, data_aggregator, mock_vlm_service, sample_vlm_analysis):
        """Test service status when VLM data is available."""
        mock_vlm_service.analyze_traffic_non_blocking.return_value = sample_vlm_analysis
        
        # Setup and trigger analysis
        camera_data = CameraDataMessage(
            camera_id="camera_north",
            intersection_id="test-intersection-id",
            direction="north",
            vehicle_count=5,
            pedestrian_count=2
        )
        data_aggregator.temp_camera_data["north"] = camera_data
        
        camera_image = CameraImage(
            camera_id="camera_north",
            direction="north",
            image_base64="base64data",
            timestamp=datetime.now(timezone.utc),
            image_size_bytes=1024
        )
        data_aggregator.temp_camera_images["north"] = camera_image
        
        await data_aggregator._update_temp_intersection_data()
        await data_aggregator._trigger_vlm_analysis()
        
        # Verify internal state is correctly set before calling get_service_status
        assert data_aggregator.vlm_analyzed_intersection_data is not None
        assert data_aggregator.vlm_analyzed_intersection_data.total_density == 5
        assert data_aggregator.vlm_analyzed_intersection_data.total_pedestrian_count == 2
        assert "north" in data_aggregator.vlm_analyzed_camera_images
        assert data_aggregator.vlm_analyzed_weather_data is not None
        assert data_aggregator.current_vlm_analysis is not None
        assert data_aggregator.last_analysis_time > 0
