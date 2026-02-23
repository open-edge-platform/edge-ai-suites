# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Weather Service."""

import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime, timedelta, timezone
import json
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.weather_service import WeatherService
from services.config import ConfigService
from models.weather import WeatherData
from models.enums import WeatherType


class TestWeatherServiceInitialization:
    """Test cases for WeatherService initialization."""

    def test_init_with_default_config(self):
        """Test WeatherService initializes with default configuration."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        assert service.api_base_url == "https://api.weather.gov"
        assert service.use_mock is False
        assert service._cached_weather is None
        assert service._running is False

    def test_init_with_custom_config(self):
        """Test WeatherService initializes with custom configuration."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {
            "api_base_url": "https://custom.api.url",
            "cache_duration_minutes": 30,
            "update_interval_minutes": 15,
            "use_mock": True
        }
        
        service = WeatherService(mock_config)
        
        assert service.api_base_url == "https://custom.api.url"
        assert service.cache_duration == timedelta(minutes=30)
        assert service.update_interval == timedelta(minutes=15)
        assert service.use_mock is True

    def test_init_with_mock_mode_enabled(self):
        """Test WeatherService initializes with mock mode."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"use_mock": True}
        
        service = WeatherService(mock_config)
        
        assert service.use_mock is True


class TestWeatherServiceCaching:
    """Test cases for WeatherService caching functionality."""

    def test_cache_valid_within_duration(self):
        """Test cache is valid when within cache duration."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"cache_duration_minutes": 15}
        
        service = WeatherService(mock_config)
        service._cached_weather = Mock()
        service._cache_timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        
        assert service._is_cache_valid() is True

    def test_cache_invalid_after_expiry(self):
        """Test cache is invalid after cache duration expires."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"cache_duration_minutes": 15}
        
        service = WeatherService(mock_config)
        service._cached_weather = Mock()
        service._cache_timestamp = datetime.now(timezone.utc) - timedelta(minutes=20)
        
        assert service._is_cache_valid() is False

    def test_cache_invalid_when_empty(self):
        """Test cache is invalid when no cached data exists."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        assert service._is_cache_valid() is False

    def test_cache_invalid_when_no_timestamp(self):
        """Test cache is invalid when timestamp is missing."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        service._cached_weather = Mock()
        service._cache_timestamp = None
        
        assert service._is_cache_valid() is False


class TestWeatherServiceProcessing:
    """Test cases for weather data processing."""

    def test_process_weather_data_basic(self):
        """Test processing basic weather forecast data."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "name": "This Afternoon",
            "temperature": 75,
            "temperatureUnit": "F",
            "shortForecast": "Sunny",
            "detailedForecast": "Sunny with clear skies.",
            "windSpeed": "10 mph",
            "windDirection": "NW",
            "probabilityOfPrecipitation": {"value": 5},
            "isDaytime": True,
            "startTime": "2026-01-22T12:00:00-08:00",
            "endTime": "2026-01-22T13:00:00-08:00"
        }
        
        result = service._process_weather_data(forecast_period)
        
        assert result.temperature == 75
        assert result.temperature_unit == "F"
        assert result.short_forecast == "Sunny"
        assert result.wind_speed == "10 mph"
        assert result.wind_direction == "NW"
        assert result.precipitation_prob == 5.0
        assert result.is_precipitation is False  # 5% < 30%
        assert result.is_mock is False

    def test_process_weather_data_high_precipitation(self):
        """Test processing weather data with high precipitation probability."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 55,
            "temperatureUnit": "F",
            "shortForecast": "Rainy",
            "detailedForecast": "Rain expected throughout the day.",
            "windSpeed": "15 mph",
            "windDirection": "S",
            "probabilityOfPrecipitation": {"value": 80}
        }
        
        result = service._process_weather_data(forecast_period)
        
        assert result.is_precipitation is True  # 80% > 30%
        assert result.precipitation_prob == 80.0

    def test_process_weather_data_empty_detailed_forecast(self):
        """Test processing when detailed forecast is empty."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 65,
            "temperatureUnit": "F",
            "shortForecast": "Cloudy",
            "detailedForecast": "",
            "windSpeed": "5 mph",
            "windDirection": "E",
            "probabilityOfPrecipitation": {"value": 20}
        }
        
        result = service._process_weather_data(forecast_period)
        
        # Should construct detailed forecast from available data
        assert "Cloudy" in result.detailed_forecast
        assert "5 mph" in result.detailed_forecast
        assert "E" in result.detailed_forecast
        assert "20%" in result.detailed_forecast

    def test_process_weather_data_missing_precipitation(self):
        """Test processing when precipitation data is missing."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 70,
            "temperatureUnit": "F",
            "shortForecast": "Clear",
            "windSpeed": "3 mph",
            "windDirection": "N"
        }
        
        result = service._process_weather_data(forecast_period)
        
        assert result.precipitation_prob == 0.0
        assert result.is_precipitation is False

    def test_process_weather_data_wind_info_format(self):
        """Test wind_info field is formatted correctly."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 68,
            "temperatureUnit": "F",
            "shortForecast": "Partly Cloudy",
            "windSpeed": "12 mph",
            "windDirection": "SW",
            "probabilityOfPrecipitation": {"value": 0}
        }
        
        result = service._process_weather_data(forecast_period)
        
        assert result.wind_info == "12mph/SW"


class TestWeatherServiceMockData:
    """Test cases for mock weather data functionality."""

    def test_get_default_weather(self):
        """Test getting default weather when no data is available."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        result = service.get_default_weather()
        
        assert result.name == "Unknown"
        assert result.temperature == 72
        assert result.temperature_unit == "F"
        assert result.is_mock is True
        assert "unavailable" in result.detailed_forecast.lower()

    def test_load_mock_weather_file_not_found(self):
        """Test loading mock weather when file doesn't exist."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        service.mock_data_file = "/nonexistent/path/weather.json"
        
        result = service._load_mock_weather_from_file()
        
        # Should return default weather
        assert result.is_mock is True
        assert result.temperature == 72

    @patch('builtins.open')
    @patch('os.path.exists')
    def test_load_mock_weather_from_valid_file(self, mock_exists, mock_open):
        """Test loading mock weather from a valid JSON file."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        mock_exists.return_value = True
        mock_weather_data = {
            "clear": {
                "name": "Mock Clear",
                "temperature": 65,
                "temperature_unit": "F",
                "detailed_forecast": "Clear and sunny",
                "is_precipitation": False,
                "wind_speed": "5 mph",
                "wind_direction": "N"
            }
        }
        mock_open.return_value.__enter__ = Mock(return_value=Mock(
            read=Mock(return_value=json.dumps(mock_weather_data))
        ))
        mock_open.return_value.__exit__ = Mock(return_value=False)
        
        with patch('json.load', return_value=mock_weather_data):
            service = WeatherService(mock_config)
            result = service._load_mock_weather_from_file(WeatherType.CLEAR)
        
        assert result.is_mock is True
        assert result.temperature == 65
        assert result.name == "Mock Clear"


class TestWeatherServiceAsync:
    """Test cases for async weather service operations."""

    @pytest.mark.asyncio
    async def test_get_current_weather_returns_cached(self):
        """Test get_current_weather returns cached data when valid."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"cache_duration_minutes": 15}
        
        service = WeatherService(mock_config)
        
        # Set up valid cached data
        cached_weather = WeatherData(
            name="Cached",
            temperature=70,
            temperature_unit="F",
            detailed_forecast="Cached weather",
            fetched_at=datetime.now(timezone.utc),
            is_mock=False
        )
        service._cached_weather = cached_weather
        service._cache_timestamp = datetime.now(timezone.utc) - timedelta(minutes=5)
        
        result = await service.get_current_weather(force_refresh=False)
        
        assert result.name == "Cached"
        assert result.is_cached is True

    @pytest.mark.asyncio
    async def test_get_current_weather_force_refresh_with_mock(self):
        """Test get_current_weather with force_refresh in mock mode."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"use_mock": True}
        
        service = WeatherService(mock_config)
        
        with patch.object(service, '_load_mock_weather_from_file') as mock_load:
            mock_load.return_value = WeatherData(
                name="Mock",
                temperature=72,
                temperature_unit="F",
                detailed_forecast="Mock weather",
                fetched_at=datetime.now(timezone.utc),
                is_mock=True
            )
            
            result = await service.get_current_weather(force_refresh=True)
            
            mock_load.assert_called_once()
            assert result.is_mock is True

    @pytest.mark.asyncio
    async def test_start_service(self):
        """Test starting the weather service."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"use_mock": True}
        mock_config.get_intersection_coordinates.return_value = (37.7749, -122.4194)
        
        service = WeatherService(mock_config)
        
        with patch.object(service, 'get_current_weather', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = Mock()
            
            # Start service
            await service.start()
            
            assert service._running is True
            mock_get.assert_called_once_with(force_refresh=True)
            
            # Clean up
            await service.stop()

    @pytest.mark.asyncio
    async def test_stop_service(self):
        """Test stopping the weather service."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"use_mock": True}
        
        service = WeatherService(mock_config)
        service._running = True
        service._update_task = asyncio.create_task(asyncio.sleep(100))
        
        await service.stop()
        
        assert service._running is False

    @pytest.mark.asyncio
    async def test_start_service_already_running(self):
        """Test starting service when already running does nothing."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        service._running = True
        
        await service.start()
        
        # Should still be running, no error thrown
        assert service._running is True


class TestWeatherServiceDescription:
    """Test cases for weather description methods."""

    def test_get_current_weather_description_with_cache(self):
        """Test getting weather description when cached data exists."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        service._cached_weather = WeatherData(
            name="Test",
            temperature=75,
            temperature_unit="F",
            detailed_forecast="Sunny and warm with light winds.",
            fetched_at=datetime.now(timezone.utc)
        )
        
        result = service.get_current_weather_description()
        
        assert result == "Sunny and warm with light winds."

    def test_get_current_weather_description_without_cache(self):
        """Test getting weather description when no cached data."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        service._cached_weather = None
        
        result = service.get_current_weather_description()
        
        assert result == "Unknown weather conditions"


class TestWeatherServiceEdgeCases:
    """Test cases for edge cases and error handling."""

    def test_process_weather_data_none_precipitation_value(self):
        """Test processing when precipitation value is None."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 60,
            "temperatureUnit": "F",
            "shortForecast": "Overcast",
            "windSpeed": "8 mph",
            "windDirection": "W",
            "probabilityOfPrecipitation": {"value": None}
        }
        
        result = service._process_weather_data(forecast_period)
        
        assert result.precipitation_prob == 0.0
        assert result.is_precipitation is False

    def test_process_weather_data_string_precipitation(self):
        """Test processing when precipitation is not a dict."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 60,
            "temperatureUnit": "F",
            "shortForecast": "Clear",
            "windSpeed": "5 mph",
            "windDirection": "N",
            "probabilityOfPrecipitation": "10%"  # String instead of dict
        }
        
        result = service._process_weather_data(forecast_period)
        
        # Should handle gracefully and return 0
        assert result.precipitation_prob == 0.0

    def test_process_weather_data_with_humidity_and_dewpoint(self):
        """Test processing weather data with humidity and dewpoint."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 70,
            "temperatureUnit": "F",
            "shortForecast": "Humid",
            "windSpeed": "3 mph",
            "windDirection": "SE",
            "probabilityOfPrecipitation": {"value": 15},
            "dewpoint": {"value": 18.5},
            "relativeHumidity": {"value": 75}
        }
        
        result = service._process_weather_data(forecast_period)
        
        assert result.dewpoint == 18.5
        assert result.relative_humidity == 75

    def test_cache_boundary_exactly_at_expiry(self):
        """Test cache validity at exact expiry boundary."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"cache_duration_minutes": 15}
        
        service = WeatherService(mock_config)
        service._cached_weather = Mock()
        # Set timestamp to exactly 15 minutes ago
        service._cache_timestamp = datetime.now(timezone.utc) - timedelta(minutes=15)
        
        # Cache should be invalid at exactly the boundary
        assert service._is_cache_valid() is False


class TestWeatherServiceFixtures:
    """Test cases using shared fixtures."""
    
    def test_weather_parsing(self, sample_weather_data):
        """Test weather parsing with sample fixture data."""
        # sample_weather_data fixture is automatically injected from conftest.py
        assert sample_weather_data["temperature"] == 55
        assert sample_weather_data["short_forecast"] == "Sunny"
        assert sample_weather_data["is_precipitation"] is False


class TestWeatherServicePeriodicUpdate:
    """Test cases for periodic update loop."""

    @pytest.mark.asyncio
    async def test_periodic_update_loop_runs(self):
        """Test that periodic update loop executes."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {
            "update_interval_minutes": 0.01,  # Very short interval for testing
            "use_mock": True
        }
        
        service = WeatherService(mock_config)
        service._running = True
        
        call_count = 0
        async def mock_get_weather(force_refresh=False):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                service._running = False  # Stop after 2 calls
            return Mock()
        
        with patch.object(service, 'get_current_weather', side_effect=mock_get_weather):
            # Run the loop briefly
            task = asyncio.create_task(service._periodic_update_loop())
            await asyncio.sleep(0.1)
            service._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_periodic_update_loop_handles_error(self):
        """Test periodic update loop handles errors gracefully."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {
            "update_interval_minutes": 0.001
        }
        
        service = WeatherService(mock_config)
        service._running = True
        
        error_count = 0
        async def mock_get_weather_error(force_refresh=False):
            nonlocal error_count
            error_count += 1
            if error_count >= 1:
                service._running = False
            raise Exception("Test error")
        
        with patch.object(service, 'get_current_weather', side_effect=mock_get_weather_error):
            task = asyncio.create_task(service._periodic_update_loop())
            await asyncio.sleep(0.05)
            service._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_periodic_update_loop_cancellation(self):
        """Test periodic update loop handles cancellation."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {
            "update_interval_minutes": 10
        }
        
        service = WeatherService(mock_config)
        service._running = True
        
        task = asyncio.create_task(service._periodic_update_loop())
        await asyncio.sleep(0.01)
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            pass
        
        # Should complete without error
        assert True


class TestWeatherServiceStartStop:
    """Test cases for service start/stop functionality."""

    @pytest.mark.asyncio
    async def test_start_handles_fetch_error(self):
        """Test start handles error when fetching initial weather."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"use_mock": True}
        
        service = WeatherService(mock_config)
        
        with patch.object(service, 'get_current_weather', new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = Exception("Fetch failed")
            
            # Should not raise, just log error
            await service.start()
            
            assert service._running is True
            
            # Cleanup
            await service.stop()

    @pytest.mark.asyncio
    async def test_start_when_initial_weather_is_none(self):
        """Test start handles None response from initial weather fetch."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"use_mock": True}
        
        service = WeatherService(mock_config)
        
        with patch.object(service, 'get_current_weather', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = None
            
            await service.start()
            
            assert service._running is True
            
            await service.stop()

    @pytest.mark.asyncio
    async def test_stop_with_done_task(self):
        """Test stop when update task is already done."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        service._running = True
        
        # Create a task that completes immediately
        async def quick_task():
            pass
        
        service._update_task = asyncio.create_task(quick_task())
        await asyncio.sleep(0.01)  # Let it complete
        
        await service.stop()
        
        assert service._running is False


class TestWeatherServiceFetchData:
    """Test cases for _fetch_weather_data method."""

    @pytest.mark.asyncio
    async def test_fetch_weather_data_success(self):
        """Test successful weather data fetch from API."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        # Mock the requests
        mock_points_response = Mock()
        mock_points_response.json.return_value = {
            "properties": {
                "forecastHourly": "https://api.weather.gov/forecast/hourly"
            }
        }
        mock_points_response.raise_for_status = Mock()
        
        now = datetime.now(timezone.utc)
        mock_forecast_response = Mock()
        mock_forecast_response.json.return_value = {
            "properties": {
                "periods": [{
                    "name": "Current Hour",
                    "temperature": 72,
                    "temperatureUnit": "F",
                    "shortForecast": "Clear",
                    "detailedForecast": "Clear skies",
                    "windSpeed": "5 mph",
                    "windDirection": "N",
                    "probabilityOfPrecipitation": {"value": 0},
                    "startTime": (now - timedelta(hours=1)).isoformat(),
                    "endTime": (now + timedelta(hours=1)).isoformat()
                }]
            }
        }
        mock_forecast_response.raise_for_status = Mock()
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = [mock_points_response, mock_forecast_response]
            
            result = await service._fetch_weather_data(37.7749, -122.4194)
            
            assert result is not None
            assert result.temperature == 72
            assert result.short_forecast == "Clear"

    @pytest.mark.asyncio
    async def test_fetch_weather_data_request_error(self):
        """Test fetch handles request exceptions."""
        import requests
        
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.RequestException("Network error")
            
            with patch.object(service, '_load_mock_weather_from_file') as mock_load:
                mock_load.return_value = WeatherData(
                    name="Mock",
                    temperature=72,
                    temperature_unit="F",
                    detailed_forecast="Mock data",
                    fetched_at=datetime.now(timezone.utc),
                    is_mock=True
                )
                
                result = await service._fetch_weather_data(37.7749, -122.4194)
                
                mock_load.assert_called()
                assert result.is_mock is True

    @pytest.mark.asyncio
    async def test_fetch_weather_data_key_error(self):
        """Test fetch handles missing keys in API response."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        mock_response = Mock()
        mock_response.json.return_value = {"invalid": "data"}  # Missing 'properties'
        mock_response.raise_for_status = Mock()
        
        with patch('requests.get', return_value=mock_response):
            with patch.object(service, '_load_mock_weather_from_file') as mock_load:
                mock_load.return_value = WeatherData(
                    name="Mock",
                    temperature=72,
                    temperature_unit="F",
                    detailed_forecast="Mock data",
                    fetched_at=datetime.now(timezone.utc),
                    is_mock=True
                )
                
                result = await service._fetch_weather_data(37.7749, -122.4194)
                
                mock_load.assert_called()

    @pytest.mark.asyncio
    async def test_fetch_weather_data_general_exception(self):
        """Test fetch handles general exceptions."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = ValueError("Unexpected error")
            
            with patch.object(service, '_load_mock_weather_from_file') as mock_load:
                mock_load.return_value = WeatherData(
                    name="Mock",
                    temperature=72,
                    temperature_unit="F",
                    detailed_forecast="Mock data",
                    fetched_at=datetime.now(timezone.utc),
                    is_mock=True
                )
                
                result = await service._fetch_weather_data(37.7749, -122.4194)
                
                mock_load.assert_called()


class TestWeatherServiceGetCurrentWeather:
    """Test cases for get_current_weather method."""

    @pytest.mark.asyncio
    async def test_get_current_weather_live_api_success(self):
        """Test get_current_weather with live API (non-mock mode)."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"use_mock": False}
        mock_config.get_intersection_coordinates.return_value = (37.7749, -122.4194)
        
        service = WeatherService(mock_config)
        
        mock_weather = WeatherData(
            name="Live",
            temperature=75,
            temperature_unit="F",
            detailed_forecast="Live weather data",
            fetched_at=datetime.now(timezone.utc),
            is_mock=False
        )
        
        with patch.object(service, '_fetch_weather_data', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_weather
            
            result = await service.get_current_weather(force_refresh=True)
            
            assert result.name == "Live"
            assert result.is_mock is False
            mock_fetch.assert_called_once_with(37.7749, -122.4194)

    @pytest.mark.asyncio
    async def test_get_current_weather_live_api_returns_cached_on_failure(self):
        """Test get_current_weather returns cached data when API fails."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {"use_mock": False}
        mock_config.get_intersection_coordinates.return_value = (37.7749, -122.4194)
        
        service = WeatherService(mock_config)
        
        # Set up cached data
        cached_weather = WeatherData(
            name="Cached",
            temperature=70,
            temperature_unit="F",
            detailed_forecast="Cached weather",
            fetched_at=datetime.now(timezone.utc),
            is_mock=False
        )
        service._cached_weather = cached_weather
        
        with patch.object(service, '_fetch_weather_data', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = None  # API fails
            
            result = await service.get_current_weather(force_refresh=True)
            
            assert result.name == "Cached"


class TestWeatherServiceMockDataExtended:
    """Extended test cases for mock weather data functionality."""

    @patch('os.path.exists')
    def test_load_mock_weather_file_parse_error(self, mock_exists):
        """Test loading mock weather when JSON parsing fails."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        mock_exists.return_value = True
        
        with patch('builtins.open', mock_open_json_error()):
            result = service._load_mock_weather_from_file()
            
            # Should return default weather on error
            assert result.is_mock is True
            assert result.name == "Unknown"

    @patch('os.path.exists')
    @patch('builtins.open')
    def test_load_mock_weather_with_string_fetched_at(self, mock_open, mock_exists):
        """Test loading mock weather with string fetched_at timestamp."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        mock_exists.return_value = True
        mock_weather_data = {
            "clear": {
                "name": "Mock Clear",
                "temperature": 65,
                "temperature_unit": "F",
                "detailed_forecast": "Clear and sunny",
                "fetched_at": "2026-01-22T12:00:00Z",
                "is_precipitation": False
            }
        }
        
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_open.return_value = mock_file
        
        with patch('json.load', return_value=mock_weather_data):
            service = WeatherService(mock_config)
            result = service._load_mock_weather_from_file(WeatherType.CLEAR)
            
            assert result.is_mock is True
            assert result.temperature == 65

    @patch('os.path.exists')
    @patch('builtins.open')
    def test_load_mock_weather_with_invalid_fetched_at(self, mock_open, mock_exists):
        """Test loading mock weather with invalid fetched_at timestamp."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        mock_exists.return_value = True
        mock_weather_data = {
            "clear": {
                "name": "Mock Clear",
                "temperature": 65,
                "temperature_unit": "F",
                "detailed_forecast": "Clear",
                "fetched_at": "invalid-date-format",
                "is_precipitation": False
            }
        }
        
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_open.return_value = mock_file
        
        with patch('json.load', return_value=mock_weather_data):
            service = WeatherService(mock_config)
            result = service._load_mock_weather_from_file(WeatherType.CLEAR)
            
            # Should use current time for invalid date
            assert result.is_mock is True
            assert result.fetched_at is not None

    @patch('os.path.exists')
    @patch('builtins.open')
    def test_load_mock_weather_missing_weather_type(self, mock_open, mock_exists):
        """Test loading mock weather when requested type is missing."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        mock_exists.return_value = True
        mock_weather_data = {
            "clear": {
                "name": "Mock Clear",
                "temperature": 65
            }
            # Missing other weather types
        }
        
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_open.return_value = mock_file
        
        with patch('json.load', return_value=mock_weather_data):
            service = WeatherService(mock_config)
            # Request a type that doesn't exist in mock data
            result = service._load_mock_weather_from_file(WeatherType.CLEAR)
            
            assert result.is_mock is True


class TestWeatherServiceProcessingExtended:
    """Extended test cases for weather data processing."""

    def test_process_weather_data_with_defaults(self):
        """Test processing with minimal/missing data uses defaults."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        # Minimal forecast period
        forecast_period = {}
        
        result = service._process_weather_data(forecast_period)
        
        assert result.temperature == 72  # Default
        assert result.temperature_unit == "F"
        assert result.wind_speed == "0 mph"
        assert result.wind_direction == "N"
        assert result.is_mock is False

    def test_process_weather_data_whitespace_only_detailed_forecast(self):
        """Test processing when detailed forecast is whitespace only."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 65,
            "temperatureUnit": "F",
            "shortForecast": "Windy",
            "detailedForecast": "   ",  # Whitespace only
            "windSpeed": "20 mph",
            "windDirection": "W",
            "probabilityOfPrecipitation": {"value": 0}
        }
        
        result = service._process_weather_data(forecast_period)
        
        # Should construct detailed forecast
        assert "Windy" in result.detailed_forecast

    def test_process_weather_data_with_dewpoint_not_dict(self):
        """Test processing when dewpoint is not a dictionary."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 70,
            "temperatureUnit": "F",
            "shortForecast": "Clear",
            "windSpeed": "5 mph",
            "windDirection": "N",
            "dewpoint": 15.5,  # Not a dict
            "relativeHumidity": 60  # Not a dict
        }
        
        result = service._process_weather_data(forecast_period)
        
        assert result.dewpoint is None
        assert result.relative_humidity is None

    def test_process_weather_data_wind_speed_range(self):
        """Test processing wind speed with range format."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 68,
            "temperatureUnit": "F",
            "shortForecast": "Breezy",
            "windSpeed": "10 to 15 mph",  # Range format
            "windDirection": "NE",
            "probabilityOfPrecipitation": {"value": 5}
        }
        
        result = service._process_weather_data(forecast_period)
        
        # Should extract first number from range
        assert "10mph" in result.wind_info

    def test_process_weather_data_no_wind_speed_number(self):
        """Test processing when wind speed has no number."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        forecast_period = {
            "temperature": 70,
            "temperatureUnit": "F",
            "shortForecast": "Calm",
            "windSpeed": "calm",  # No number
            "windDirection": "N"
        }
        
        result = service._process_weather_data(forecast_period)
        
        assert "0mph" in result.wind_info


class TestWeatherServiceFetchDataExtended:
    """Extended test cases for weather data fetching."""

    @pytest.mark.asyncio
    async def test_fetch_weather_data_finds_current_period(self):
        """Test that fetch finds the correct current time period."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_weather_config.return_value = {}
        
        service = WeatherService(mock_config)
        
        now = datetime.now(timezone.utc)
        
        mock_points_response = Mock()
        mock_points_response.json.return_value = {
            "properties": {
                "forecastHourly": "https://api.weather.gov/forecast"
            }
        }
        mock_points_response.raise_for_status = Mock()
        
        # Create periods where the second one matches current time
        mock_forecast_response = Mock()
        mock_forecast_response.json.return_value = {
            "properties": {
                "periods": [
                    {
                        "name": "Previous Hour",
                        "temperature": 70,
                        "temperatureUnit": "F",
                        "shortForecast": "Old",
                        "windSpeed": "5 mph",
                        "windDirection": "N",
                        "startTime": (now - timedelta(hours=2)).isoformat(),
                        "endTime": (now - timedelta(hours=1)).isoformat()
                    },
                    {
                        "name": "Current Hour",
                        "temperature": 75,
                        "temperatureUnit": "F",
                        "shortForecast": "Current",
                        "windSpeed": "10 mph",
                        "windDirection": "S",
                        "startTime": (now - timedelta(minutes=30)).isoformat(),
                        "endTime": (now + timedelta(minutes=30)).isoformat()
                    }
                ]
            }
        }
        mock_forecast_response.raise_for_status = Mock()
        
        with patch('requests.get') as mock_get:
            mock_get.side_effect = [mock_points_response, mock_forecast_response]
            
            result = await service._fetch_weather_data(37.7749, -122.4194)
            
            # Should find the current period
            assert result.temperature == 75
            assert result.short_forecast == "Current"


# Helper function for mock JSON error
def mock_open_json_error():
    """Create a mock that raises JSON decode error."""
    mock = MagicMock()
    mock.__enter__ = Mock(return_value=mock)
    mock.__exit__ = Mock(return_value=False)
    mock.read = Mock(side_effect=json.JSONDecodeError("Error", "doc", 0))
    return Mock(return_value=mock)
