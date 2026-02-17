# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for VLM Service."""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta
import json
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.vlm_service import VLMService
from services.config import ConfigService
from services.weather_service import WeatherService
from models.weather import WeatherData
from models.traffic import TrafficSnapshot, CameraImage
from models.vlm import VLMAnalysisData, VLMAlert
from models.enums import AlertLevel, AlertType, WeatherType


class TestVLMServiceInitialization:
    """Test cases for VLMService initialization."""

    def test_init_with_default_config(self):
        """Test VLMService initializes with default configuration."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        assert service.base_url == "http://vlm-service:8080"
        assert service.model == "gpt-4-vision-preview"
        assert service.timeout == 300
        assert service.max_tokens == 2000
        assert service.temperature == 0.1
        assert service.top_p == 0.1
        assert service.weather_data is None
        assert service._last_analysis is None

    def test_init_with_custom_config(self):
        """Test VLMService initializes with custom configuration."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {
            "base_url": "http://custom-vlm:9000",
            "model": "custom-model",
            "timeout_seconds": 60,
            "max_completion_tokens": 1000,
            "temperature": 0.5,
            "top_p": 0.9
        }
        mock_config.get_high_density_threshold.return_value = 15
        
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        assert service.base_url == "http://custom-vlm:9000"
        assert service.model == "custom-model"
        assert service.timeout == 60
        assert service.max_tokens == 1000
        assert service.temperature == 0.5
        assert service.top_p == 0.9


class TestVLMServiceHelpers:
    """Test cases for VLMService helper methods."""

    def test_get_vlm_semaphore(self):
        """Test getting the VLM semaphore."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        semaphore = service.get_vlm_semaphore()
        assert isinstance(semaphore, asyncio.Semaphore)

    def test_get_weather_details_with_cached_data(self):
        """Test getting weather details when cached data exists."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        mock_weather_data = WeatherData(
            name="Current Hour",
            temperature=72,
            temperature_unit="F",
            detailed_forecast="Clear conditions",
            fetched_at=datetime.now(timezone.utc)
        )
        service.weather_data = mock_weather_data
        
        result = service.get_weather_details()
        assert result == mock_weather_data

    def test_get_weather_details_without_cached_data(self):
        """Test getting weather details when no cached data exists."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        default_weather = WeatherData(
            name="Default",
            temperature=55,
            temperature_unit="F",
            detailed_forecast="Default weather",
            fetched_at=datetime.now(timezone.utc)
        )
        mock_weather.get_default_weather.return_value = default_weather
        
        service = VLMService(mock_config, mock_weather)
        
        result = service.get_weather_details()
        assert result == default_weather
        mock_weather.get_default_weather.assert_called_once()

    def test_clear_cache(self):
        """Test clearing the analysis cache."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        service._analysis_cache["test-intersection"] = Mock()
        
        service.clear_cache()
        
        assert len(service._analysis_cache) == 0

    def test_get_service_status_not_busy(self):
        """Test getting service status when not busy."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        status = service.get_service_status()
        
        assert status["is_busy"] is False
        assert status["has_cached_analysis"] is False
        assert status["last_analysis_timestamp"] is None
        assert status["analysis_cache_size"] == 0


class TestVLMServicePromptBuilding:
    """Test cases for prompt building functionality."""

    def test_create_structured_prompt_basic(self):
        """Test creating structured prompt with basic traffic data."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_config.get_intersection_name.return_value = "Test Intersection"
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 5, "south": 3, "east": 8, "west": 2},
            total_count=18
        )
        
        prompt = service._create_structured_prompt(traffic_snapshot, None)
        
        assert "Test Intersection" in prompt or "intersection" in prompt.lower()
        assert "18" in prompt  # total count
        assert "north" in prompt.lower()
        assert "JSON" in prompt

    def test_create_structured_prompt_with_weather(self):
        """Test creating structured prompt with weather context."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_config.get_intersection_name.return_value = "Test Intersection"
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 5, "south": 3, "east": 8, "west": 2},
            total_count=18
        )
        
        weather_data = WeatherData(
            name="Current Hour",
            temperature=72,
            temperature_unit="F",
            detailed_forecast="Sunny with clear skies",
            fetched_at=datetime.now(timezone.utc)
        )
        
        prompt = service._create_structured_prompt(traffic_snapshot, weather_data)
        
        assert "72" in prompt
        assert "Sunny" in prompt or "clear" in prompt.lower()

    def test_build_vlm_request_with_images(self):
        """Test building VLM request with camera images."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        camera_images = [
            CameraImage(camera_id="cam-1", direction="north", image_base64="base64data1"),
            CameraImage(camera_id="cam-2", direction="south", image_base64="base64data2"),
        ]
        
        request = service._build_vlm_request("Test prompt", camera_images)
        
        assert request["model"] == "gpt-4-vision-preview"
        assert "messages" in request
        assert len(request["messages"]) == 1
        assert request["messages"][0]["role"] == "user"
        # Content should have text + 2 images
        content = request["messages"][0]["content"]
        assert len(content) == 3  # 1 text + 2 images

    def test_build_vlm_request_limits_to_four_images(self):
        """Test VLM request limits to 4 images maximum."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        camera_images = [
            CameraImage(camera_id=f"cam-{i}", direction=f"dir-{i}", image_base64=f"data{i}")
            for i in range(6)  # 6 images
        ]
        
        request = service._build_vlm_request("Test prompt", camera_images)
        
        content = request["messages"][0]["content"]
        # Should have 1 text + 4 images max
        assert len(content) == 5


class TestVLMServiceResponseParsing:
    """Test cases for VLM response parsing."""

    def test_extract_json_from_markdown_code_block(self):
        """Test extracting JSON from markdown code blocks."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        response = '''Here is the analysis:
```json
{"analysis": "Traffic is moderate", "alerts": [], "recommendations": []}
```
'''
        
        result = service._extract_json_from_response(response)
        
        assert result is not None
        parsed = json.loads(result)
        assert parsed["analysis"] == "Traffic is moderate"

    def test_extract_json_from_plain_response(self):
        """Test extracting JSON from plain response without markdown."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        response = 'Some text {"analysis": "Test", "alerts": []} more text'
        
        result = service._extract_json_from_response(response)
        
        assert result is not None
        parsed = json.loads(result)
        assert parsed["analysis"] == "Test"

    def test_extract_json_returns_none_for_invalid_response(self):
        """Test extraction returns None for invalid JSON response."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        response = "This is just plain text with no JSON"
        
        result = service._extract_json_from_response(response)
        
        assert result is None

    def test_parse_vlm_response_valid_json(self):
        """Test parsing valid VLM JSON response."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 5},
            total_count=5
        )
        
        response_text = '''```json
{
    "analysis": "Traffic flow is normal",
    "alerts": [
        {
            "alert_type": "congestion",
            "level": "info",
            "description": "Light traffic observed",
            "weather_related": false
        }
    ],
    "recommendations": [
        {"recommendation": "No action needed"}
    ]
}
```'''
        
        result = service._parse_vlm_response(response_text, traffic_snapshot, None)
        
        assert isinstance(result, VLMAnalysisData)
        assert result.traffic_summary == "Traffic flow is normal"
        assert len(result.alerts) == 1
        assert result.alerts[0].alert_type == AlertType.CONGESTION
        assert result.alerts[0].level == AlertLevel.INFO
        assert len(result.recommendations) == 1

    def test_parse_vlm_response_with_string_recommendations(self):
        """Test parsing VLM response with string recommendations."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 5},
            total_count=5
        )
        
        response_text = '''```json
{
    "analysis": "Normal traffic",
    "alerts": [],
    "recommendations": ["Monitor traffic", "Check signals"]
}
```'''
        
        result = service._parse_vlm_response(response_text, traffic_snapshot, None)
        
        assert len(result.recommendations) == 2
        assert "Monitor traffic" in result.recommendations

    def test_parse_vlm_response_invalid_json_uses_fallback(self):
        """Test parsing invalid JSON returns fallback analysis."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 5},
            total_count=5
        )
        
        response_text = "This is not valid JSON at all"
        
        result = service._parse_vlm_response(response_text, traffic_snapshot, None)
        
        assert isinstance(result, VLMAnalysisData)
        assert result.traffic_summary is not None


class TestVLMServiceFallbackAnalysis:
    """Test cases for fallback analysis generation."""

    def test_create_fallback_analysis_low_traffic(self):
        """Test fallback analysis for low traffic conditions."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 2, "south": 1},
            total_count=3
        )
        
        result = service._create_fallback_analysis("Test", traffic_snapshot, None)
        
        assert isinstance(result, VLMAnalysisData)
        assert "3" in result.traffic_summary  # Should mention vehicle count
        assert len(result.recommendations) > 0

    def test_create_fallback_analysis_high_traffic(self):
        """Test fallback analysis for high traffic conditions."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 8, "south": 7},
            total_count=15  # Above threshold of 10
        )
        
        result = service._create_fallback_analysis("Test", traffic_snapshot, None)
        
        assert isinstance(result, VLMAnalysisData)
        assert "High traffic" in result.traffic_summary or "15" in result.traffic_summary
        # Should have a congestion alert for high traffic
        congestion_alerts = [a for a in result.alerts if a.alert_type == AlertType.CONGESTION]
        assert len(congestion_alerts) >= 1

    def test_create_fallback_analysis_with_weather(self):
        """Test fallback analysis includes weather alerts."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        mock_weather.get_current_weather_description.return_value = "Rainy conditions"
        
        service = VLMService(mock_config, mock_weather)
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 5},
            total_count=5
        )
        
        weather_data = WeatherData(
            name="Current Hour",
            temperature=55,
            temperature_unit="F",
            detailed_forecast="Rainy conditions",
            fetched_at=datetime.now(timezone.utc),
            weather_type=WeatherType.CLEAR
        )
        
        result = service._create_fallback_analysis("Test", traffic_snapshot, weather_data)
        
        assert isinstance(result, VLMAnalysisData)
        assert result.traffic_summary is not None
        assert result.recommendations is not None
        # Should have weather-related alert
        weather_alerts = [a for a in result.alerts if a.alert_type == AlertType.WEATHER_RELATED]
        assert len(weather_alerts) >= 1


class TestVLMServiceAsync:
    """Test cases for async VLM operations."""

    @pytest.mark.asyncio
    async def test_call_vlm_service_success(self):
        """Test successful VLM service call."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {"base_url": "http://test-vlm:8080"}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"analysis": "Test", "alerts": [], "recommendations": []}'
                }
            }]
        }
        
        # Create a mock for the response context manager
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)
        
        # Create an async context manager for the post response
        mock_post_ctx = MagicMock()
        mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_post_ctx.__aexit__ = AsyncMock(return_value=None)
        
        # Create a mock session with post method
        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_post_ctx)
        
        # Create an async context manager for the session
        mock_session_ctx = MagicMock()
        mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_ctx.__aexit__ = AsyncMock(return_value=None)
        
        with patch('aiohttp.ClientSession', return_value=mock_session_ctx):
            result = await service._call_vlm_service({"test": "data"})
            
            assert result is not None
            assert "analysis" in result

    @pytest.mark.asyncio
    async def test_call_vlm_service_error_status(self):
        """Test VLM service call with error status."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {"base_url": "http://test-vlm:8080"}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value.status = 500
            mock_context.__aenter__.return_value.text = AsyncMock(return_value="Internal Server Error")
            
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__.return_value.post.return_value = mock_context
            mock_session.return_value = mock_session_instance
            
            result = await service._call_vlm_service({"test": "data"})
            
            assert result is None

    @pytest.mark.asyncio
    async def test_call_vlm_service_connection_error(self):
        """Test VLM service call with connection error."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {"base_url": "http://test-vlm:8080"}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        import aiohttp
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session_instance = AsyncMock()
            mock_session_instance.__aenter__.return_value.post.side_effect = aiohttp.ClientConnectorError(
                connection_key=Mock(), os_error=OSError("Connection refused")
            )
            mock_session.return_value = mock_session_instance
            
            result = await service._call_vlm_service({"test": "data"})
            
            assert result is None

    @pytest.mark.asyncio
    async def test_analyze_traffic_non_blocking_when_busy(self):
        """Test non-blocking analysis returns cached result when busy."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        # Set up cached analysis
        cached_analysis = VLMAnalysisData(
            traffic_summary="Cached analysis",
            alerts=[],
            recommendations=["Test recommendation"],
            analysis_timestamp=datetime.now(timezone.utc)
        )
        service._last_analysis = cached_analysis
        service._last_analysis_timestamp = datetime.now(timezone.utc)
        
        # Lock the semaphore to simulate busy state
        await service._vlm_semaphore.acquire()
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 5},
            total_count=5,
            camera_images={}
        )
        
        result = await service.analyze_traffic_non_blocking(traffic_snapshot)
        
        # Should return cached analysis since service is busy
        assert result is not None
        assert result.traffic_summary == "Cached analysis"
        
        # Release the semaphore
        service._vlm_semaphore.release()

    @pytest.mark.asyncio
    async def test_analyze_traffic_non_blocking_no_cache_when_busy(self):
        """Test non-blocking analysis returns None when busy with no cache."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        # Lock the semaphore to simulate busy state (no cached analysis)
        await service._vlm_semaphore.acquire()
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 5},
            total_count=5,
            camera_images={}
        )
        
        result = await service.analyze_traffic_non_blocking(traffic_snapshot)
        
        # Should return None since no cached analysis
        assert result is None
        
        # Release the semaphore
        service._vlm_semaphore.release()


class TestVLMServiceIntegration:
    """Integration-style tests for VLMService."""

    @pytest.mark.asyncio
    async def test_analyze_traffic_with_weather_uses_fallback_on_weather_error(self):
        """Test traffic analysis uses fallback weather on weather fetch error."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_config.get_intersection_name.return_value = "Test Intersection"
        
        mock_weather = Mock(spec=WeatherService)
        mock_weather.get_current_weather = AsyncMock(side_effect=Exception("Weather fetch failed"))
        default_weather = WeatherData(
            name="Default",
            temperature=55,
            temperature_unit="F",
            detailed_forecast="Default weather",
            fetched_at=datetime.now(timezone.utc)
        )
        mock_weather.get_default_weather.return_value = default_weather
        
        service = VLMService(mock_config, mock_weather)
        
        traffic_snapshot = TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id="test-001",
            directional_counts={"north": 5},
            total_count=5,
            camera_images={}
        )
        
        # Mock the VLM call to return None (trigger fallback)
        with patch.object(service, '_call_vlm_service', new_callable=AsyncMock, return_value=None):
            result = await service.analyze_traffic_with_weather(traffic_snapshot, [])
            
            # Should still return a result using fallback
            assert result is not None
            mock_weather.get_default_weather.assert_called()

    def test_service_status_with_cached_analysis(self):
        """Test service status includes cached analysis info."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_vlm_config.return_value = {}
        mock_config.get_high_density_threshold.return_value = 10
        mock_weather = Mock(spec=WeatherService)
        
        service = VLMService(mock_config, mock_weather)
        
        # Set up cached analysis
        service._last_analysis = VLMAnalysisData(
            traffic_summary="Test",
            alerts=[],
            recommendations=[],
            analysis_timestamp=datetime.now(timezone.utc)
        )
        service._last_analysis_timestamp = datetime.utcnow()
        service._analysis_cache["test-001"] = service._last_analysis
        
        status = service.get_service_status()
        
        assert status["has_cached_analysis"] is True
        assert status["last_analysis_timestamp"] is not None
        assert status["analysis_cache_size"] == 1
        assert status["cached_analysis_age_minutes"] is not None
