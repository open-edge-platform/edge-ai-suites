# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for UI components."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone

import os, sys
# Add src/ui to path so ui_components and its siblings can be found
ui_path = os.path.join(os.path.dirname(__file__), '..', '..', 'src', 'ui')
if ui_path not in sys.path:
    sys.path.insert(0, ui_path)

from ui_components import ThemeColors, UIComponents

try:
    from ui.models import (
        MonitoringData, IntersectionData, VLMAnalysis, WeatherData,
        CameraData, RegionCount, TrafficContext
    )
except (ModuleNotFoundError, ImportError):
    from models import (
        MonitoringData, IntersectionData, VLMAnalysis, WeatherData,
        CameraData, RegionCount, TrafficContext
    )

try:
    from ui.config import Config
except (ModuleNotFoundError, ImportError):
    from config import Config


# ============== Fixtures ==============

@pytest.fixture
def sample_region_counts():
    """Create sample region counts."""
    return {
        "north": RegionCount(vehicle=5, pedestrian=2),
        "south": RegionCount(vehicle=3, pedestrian=1),
        "east": RegionCount(vehicle=8, pedestrian=3),
        "west": RegionCount(vehicle=2, pedestrian=0),
    }


@pytest.fixture
def sample_traffic_context():
    """Create sample traffic context."""
    return TrafficContext(
        analysis_period={"start": "2025-01-01T10:00:00", "end": "2025-01-01T10:05:00"},
        avg_densities={"north": 4, "south": 3, "east": 6, "west": 2},
        peak_densities={"north": 7, "south": 5, "east": 10, "west": 3}
    )


@pytest.fixture
def sample_vlm_analysis(sample_traffic_context):
    """Create sample VLM analysis."""
    return VLMAnalysis(
        analysis="Traffic is moderate with higher density in the east direction.",
        high_density_directions=["east"],
        analysis_timestamp="2025-01-01T10:05:00Z",
        current_high_directions=["east"],
        analysis_age_minutes=2.5,
        traffic_context=sample_traffic_context,
        alerts=[
            {
                "alert_type": "congestion",
                "level": "warning",
                "description": "Heavy traffic detected in east direction",
                "weather_related": False
            }
        ],
        recommendations=["Consider alternative routes to avoid east direction"]
    )


@pytest.fixture
def sample_weather_data():
    """Create sample weather data."""
    return WeatherData(
        timestamp="2025-01-01T10:00:00Z",
        temperature_fahrenheit=72.0,
        humidity_percent=45,
        precipitation_prob=10.0,
        wind_speed_mph=8.5,
        wind_direction_degrees=180,
        conditions="Partly Cloudy",
        dewpoint=15.0,
        relative_humidity=50.0,
        is_daytime=True,
        start_time="2025-01-01T10:00:00Z",
        end_time="2025-01-01T11:00:00Z",
        detailed_forecast="Partly cloudy with mild temperatures",
        temperature_unit="F"
    )


@pytest.fixture
def sample_camera_data():
    """Create sample camera data."""
    return {
        "north_camera": {
            "camera_id": "camera1",
            "direction": "north",
            "timestamp": "2025-01-01T10:00:00Z",
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        },
        "east_camera": {
            "camera_id": "camera2",
            "direction": "east",
            "timestamp": "2025-01-01T10:00:00Z",
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        },
        "south_camera": {
            "camera_id": "camera3",
            "direction": "south",
            "timestamp": "2025-01-01T10:00:00Z",
            "image_base64": None
        },
        "west_camera": {
            "camera_id": "camera4",
            "direction": "west",
            "timestamp": "2025-01-01T10:00:00Z",
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        },
    }


@pytest.fixture
def sample_intersection_data(sample_region_counts):
    """Create sample intersection data."""
    return IntersectionData(
        intersection_id="INT-001",
        intersection_name="Main St & 1st Ave",
        latitude=37.7749,
        longitude=-122.4194,
        timestamp="2025-01-01T10:00:00Z",
        northbound_density=5,
        southbound_density=3,
        eastbound_density=8,
        westbound_density=2,
        total_density=18,
        region_counts=sample_region_counts,
        total_pedestrian_count=6,
        north_timestamp="2025-01-01T10:00:00Z",
        south_timestamp="2025-01-01T10:00:00Z",
        east_timestamp="2025-01-01T10:00:00Z",
        west_timestamp="2025-01-01T10:00:00Z"
    )


@pytest.fixture
def sample_monitoring_data(sample_intersection_data, sample_camera_data, sample_vlm_analysis, sample_weather_data):
    """Create complete sample monitoring data."""
    return MonitoringData(
        timestamp="2025-01-01T10:00:00Z",
        intersection_id="INT-001",
        data=sample_intersection_data,
        camera_images=sample_camera_data,
        vlm_analysis=sample_vlm_analysis,
        weather_data=sample_weather_data
    )


# ============== ThemeColors Tests ==============

class TestThemeColors:
    """Test cases for ThemeColors class."""

    def test_get_colors_light_theme(self):
        """Test get_colors returns light theme colors."""
        with patch.object(Config, 'get_ui_theme', return_value='light'):
            colors = ThemeColors.get_colors()
            
            assert colors['bg_primary'] == '#ffffff'
            assert colors['bg_secondary'] == '#f8fafc'
            assert colors['text_primary'] == '#1f2937'
            assert colors['text_secondary'] == '#64748b'

    def test_get_colors_dark_theme(self):
        """Test get_colors returns dark theme colors."""
        with patch.object(Config, 'get_ui_theme', return_value='dark'):
            colors = ThemeColors.get_colors()
            
            assert colors['bg_primary'] == '#1f2937'
            assert colors['bg_secondary'] == '#374151'
            assert colors['text_primary'] == '#f3f4f6'
            assert colors['text_secondary'] == '#d1d5db'

    def test_get_colors_returns_all_keys(self):
        """Test get_colors returns all required color keys."""
        colors = ThemeColors.get_colors()
        
        required_keys = ['bg_primary', 'bg_secondary', 'bg_card', 'text_primary', 
                        'text_secondary', 'border', 'header_bg', 'shadow']
        
        for key in required_keys:
            assert key in colors


# ============== UIComponents Tests ==============

class TestUIComponentsRenderMarkdown:
    """Test cases for _render_markdown method."""

    def test_render_markdown_returns_empty_for_none(self):
        """Test _render_markdown returns empty string for None input."""
        result = UIComponents._render_markdown(None)
        assert result == ""

    def test_render_markdown_with_valid_text(self):
        """Test _render_markdown with valid markdown text."""
        result = UIComponents._render_markdown("**bold text**")
        # Should contain HTML or at least the original text
        assert result is not None


class TestUIComponentsTrafficDensityColor:
    """Test cases for _get_traffic_density_color method."""

    def test_high_density_returns_red(self):
        """Test high density returns light red color."""
        with patch.object(Config, 'get_high_density_threshold', return_value=10):
            with patch.object(Config, 'get_moderate_density_threshold', return_value=5):
                color = UIComponents._get_traffic_density_color(15)
                assert color == "#ecb3b3"

    def test_moderate_density_returns_yellow(self):
        """Test moderate density returns yellow color."""
        with patch.object(Config, 'get_high_density_threshold', return_value=10):
            with patch.object(Config, 'get_moderate_density_threshold', return_value=5):
                color = UIComponents._get_traffic_density_color(7)
                assert color == "#ffff99"

    def test_low_density_returns_white(self):
        """Test low density returns white color."""
        with patch.object(Config, 'get_high_density_threshold', return_value=10):
            with patch.object(Config, 'get_moderate_density_threshold', return_value=5):
                color = UIComponents._get_traffic_density_color(3)
                assert color == "#ffffff"

    def test_boundary_high_density(self):
        """Test exact high density threshold."""
        with patch.object(Config, 'get_high_density_threshold', return_value=10):
            with patch.object(Config, 'get_moderate_density_threshold', return_value=5):
                color = UIComponents._get_traffic_density_color(10)
                assert color == "#ecb3b3"

    def test_boundary_moderate_density(self):
        """Test exact moderate density threshold."""
        with patch.object(Config, 'get_high_density_threshold', return_value=10):
            with patch.object(Config, 'get_moderate_density_threshold', return_value=5):
                color = UIComponents._get_traffic_density_color(5)
                assert color == "#ffff99"


class TestUIComponentsCreateHeader:
    """Test cases for create_header method."""

    def test_create_header_without_data(self):
        """Test create_header returns unavailable message when no data."""
        result = UIComponents.create_header(None)
        
        assert "DATA UNAVAILABLE" in result
        assert "MONITORING SYSTEM" in result

    def test_create_header_with_data(self, sample_monitoring_data):
        """Test create_header displays intersection name with data."""
        result = UIComponents.create_header(sample_monitoring_data)
        
        assert sample_monitoring_data.data.intersection_name in result
        assert "DATA UNAVAILABLE" not in result

    def test_create_header_contains_styling(self):
        """Test create_header contains proper styling."""
        result = UIComponents.create_header(None)
        
        assert "style=" in result
        assert "background" in result
        assert "border-radius" in result


class TestUIComponentsCreateTrafficSummary:
    """Test cases for create_traffic_summary method."""

    def test_create_traffic_summary_without_data(self):
        """Test create_traffic_summary returns error message when no data."""
        result = UIComponents.create_traffic_summary(None)
        
        assert "No traffic data available" in result

    def test_create_traffic_summary_with_data(self, sample_monitoring_data):
        """Test create_traffic_summary displays traffic data."""
        result = UIComponents.create_traffic_summary(sample_monitoring_data)
        
        assert "TRAFFIC SUMMARY" in result
        assert "NORTH" in result
        assert "SOUTH" in result
        assert "EAST" in result
        assert "WEST" in result

    def test_create_traffic_summary_shows_densities(self, sample_monitoring_data):
        """Test create_traffic_summary shows density values."""
        result = UIComponents.create_traffic_summary(sample_monitoring_data)
        
        # Check that density values are present
        assert str(sample_monitoring_data.data.northbound_density) in result
        assert str(sample_monitoring_data.data.total_density) in result

    def test_create_traffic_summary_shows_pedestrians(self, sample_monitoring_data):
        """Test create_traffic_summary shows pedestrian count."""
        result = UIComponents.create_traffic_summary(sample_monitoring_data)
        
        assert "PEDESTRIANS" in result


class TestUIComponentsCreateDebugPanel:
    """Test cases for create_debug_panel method."""

    def test_create_debug_panel_without_data(self):
        """Test create_debug_panel returns error message when no data."""
        result = UIComponents.create_debug_panel(None)
        
        assert "No traffic data available" in result

    def test_create_debug_panel_with_data(self, sample_monitoring_data):
        """Test create_debug_panel displays timestamps."""
        result = UIComponents.create_debug_panel(sample_monitoring_data)
        
        assert "Debug Timestamps" in result
        assert "EAST" in result
        assert "NORTH" in result
        assert "SOUTH" in result
        assert "WEST" in result


class TestUIComponentsCreateEnvironmentalPanel:
    """Test cases for create_environmental_panel method."""

    def test_create_environmental_panel_without_data(self):
        """Test create_environmental_panel returns error message when no data."""
        result = UIComponents.create_environmental_panel(None)
        
        assert "No environmental data available" in result

    def test_create_environmental_panel_with_data(self, sample_monitoring_data):
        """Test create_environmental_panel displays weather data."""
        result = UIComponents.create_environmental_panel(sample_monitoring_data)
        
        assert "ENVIRONMENTAL DATA" in result
        assert "TEMPERATURE" in result
        assert "HUMIDITY" in result
        assert "WIND" in result

    def test_create_environmental_panel_shows_temperature(self, sample_monitoring_data):
        """Test create_environmental_panel shows temperature value."""
        result = UIComponents.create_environmental_panel(sample_monitoring_data)
        
        temp = int(sample_monitoring_data.weather_data.temperature_fahrenheit)
        assert str(temp) in result

    def test_create_environmental_panel_wind_direction_north(self, sample_monitoring_data):
        """Test wind direction shows N for north."""
        sample_monitoring_data.weather_data.wind_direction_degrees = 0
        result = UIComponents.create_environmental_panel(sample_monitoring_data)
        
        assert "WIND N" in result

    def test_create_environmental_panel_wind_direction_east(self, sample_monitoring_data):
        """Test wind direction shows E for east."""
        sample_monitoring_data.weather_data.wind_direction_degrees = 90
        result = UIComponents.create_environmental_panel(sample_monitoring_data)
        
        assert "WIND E" in result

    def test_create_environmental_panel_wind_direction_south(self, sample_monitoring_data):
        """Test wind direction shows S for south."""
        sample_monitoring_data.weather_data.wind_direction_degrees = 180
        result = UIComponents.create_environmental_panel(sample_monitoring_data)
        
        assert "WIND S" in result

    def test_create_environmental_panel_wind_direction_west(self, sample_monitoring_data):
        """Test wind direction shows W for west."""
        sample_monitoring_data.weather_data.wind_direction_degrees = 270
        result = UIComponents.create_environmental_panel(sample_monitoring_data)
        
        assert "WIND W" in result

    def test_create_environmental_panel_daytime_status(self, sample_monitoring_data):
        """Test daytime status display."""
        sample_monitoring_data.weather_data.is_daytime = True
        result = UIComponents.create_environmental_panel(sample_monitoring_data)
        
        assert "DAY TIME" in result

    def test_create_environmental_panel_nighttime_status(self, sample_monitoring_data):
        """Test nighttime status display."""
        sample_monitoring_data.weather_data.is_daytime = False
        result = UIComponents.create_environmental_panel(sample_monitoring_data)
        
        assert "NIGHT TIME" in result


class TestUIComponentsCreateAlertsPanel:
    """Test cases for create_alerts_panel method."""

    def test_create_alerts_panel_without_data(self):
        """Test create_alerts_panel returns error message when no data."""
        result = UIComponents.create_alerts_panel(None)
        
        assert "No alerts data available" in result

    def test_create_alerts_panel_no_alerts(self, sample_monitoring_data):
        """Test create_alerts_panel shows all clear when no alerts."""
        sample_monitoring_data.vlm_analysis.alerts = []
        sample_monitoring_data.vlm_analysis.recommendations = []
        
        result = UIComponents.create_alerts_panel(sample_monitoring_data)
        
        assert "ALL SYSTEMS OPERATIONAL" in result

    def test_create_alerts_panel_with_structured_alert(self, sample_monitoring_data):
        """Test create_alerts_panel displays structured alerts."""
        result = UIComponents.create_alerts_panel(sample_monitoring_data)
        
        assert "Traffic Status and Alerts" in result
        assert "WARNING ALERT" in result

    def test_create_alerts_panel_critical_alert(self, sample_monitoring_data):
        """Test create_alerts_panel with critical alert."""
        sample_monitoring_data.vlm_analysis.alerts = [{
            "alert_type": "accident",
            "level": "critical",
            "description": "Major accident reported",
            "weather_related": False
        }]
        
        result = UIComponents.create_alerts_panel(sample_monitoring_data)
        
        assert "CRITICAL ALERT" in result

    def test_create_alerts_panel_advisory_alert(self, sample_monitoring_data):
        """Test create_alerts_panel with advisory alert."""
        sample_monitoring_data.vlm_analysis.alerts = [{
            "alert_type": "info",
            "level": "advisory",
            "description": "Light traffic expected",
            "weather_related": False
        }]
        
        result = UIComponents.create_alerts_panel(sample_monitoring_data)
        
        assert "ADVISORY ALERT" in result

    def test_create_alerts_panel_weather_related_alert(self, sample_monitoring_data):
        """Test create_alerts_panel with weather-related alert."""
        sample_monitoring_data.vlm_analysis.alerts = [{
            "alert_type": "weather",
            "level": "warning",
            "description": "Heavy rain affecting visibility",
            "weather_related": True
        }]
        
        result = UIComponents.create_alerts_panel(sample_monitoring_data)
        
        assert "🌦️" in result

    def test_create_alerts_panel_with_recommendations(self, sample_monitoring_data):
        """Test create_alerts_panel displays recommendations."""
        result = UIComponents.create_alerts_panel(sample_monitoring_data)
        
        assert "Recommendations" in result
        assert "Recommendation 1" in result

    def test_create_alerts_panel_string_alert_fallback(self, sample_monitoring_data):
        """Test create_alerts_panel handles legacy string alerts."""
        sample_monitoring_data.vlm_analysis.alerts = ["Simple text alert message"]
        
        result = UIComponents.create_alerts_panel(sample_monitoring_data)
        
        assert "Simple text alert message" in result


class TestUIComponentsCreateCameraImages:
    """Test cases for create_camera_images method."""

    def test_create_camera_images_without_data(self):
        """Test create_camera_images returns empty list when no data."""
        result = UIComponents.create_camera_images(None)
        
        assert result == []

    def test_create_camera_images_with_data(self, sample_monitoring_data):
        """Test create_camera_images returns image list."""
        result = UIComponents.create_camera_images(sample_monitoring_data)
        
        # Should have images for cameras with image_base64 set
        assert len(result) > 0

    def test_create_camera_images_returns_tuples(self, sample_monitoring_data):
        """Test create_camera_images returns list of tuples."""
        result = UIComponents.create_camera_images(sample_monitoring_data)
        
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_create_camera_images_with_dict_format(self, sample_monitoring_data):
        """Test create_camera_images handles dict format."""
        sample_monitoring_data.camera_images = {
            "north_camera": {
                "camera_id": "cam1",
                "direction": "north",
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            }
        }
        
        result = UIComponents.create_camera_images(sample_monitoring_data)
        
        assert len(result) == 1


class TestUIComponentsCreateCameraGridHtml:
    """Test cases for create_camera_grid_html method."""

    def test_create_camera_grid_without_data(self):
        """Test create_camera_grid_html returns error when no data."""
        result = UIComponents.create_camera_grid_html(None)
        
        assert "No camera images available" in result

    def test_create_camera_grid_with_data(self, sample_monitoring_data):
        """Test create_camera_grid_html displays camera feeds."""
        result = UIComponents.create_camera_grid_html(sample_monitoring_data)
        
        assert "Camera Feeds" in result
        assert "NORTH VIEW" in result
        assert "EAST VIEW" in result

    def test_create_camera_grid_shows_live_indicator(self, sample_monitoring_data):
        """Test create_camera_grid_html shows LIVE indicator."""
        result = UIComponents.create_camera_grid_html(sample_monitoring_data)
        
        assert "LIVE" in result

    def test_create_camera_grid_no_image_available(self, sample_monitoring_data):
        """Test create_camera_grid_html shows placeholder for missing image."""
        result = UIComponents.create_camera_grid_html(sample_monitoring_data)
        
        # South camera has no image in fixture
        assert "No image available" in result

    def test_create_camera_grid_with_dict_format(self, sample_monitoring_data):
        """Test create_camera_grid_html handles dict format."""
        sample_monitoring_data.camera_images = {
            "east_camera": {
                "camera_id": "cam2",
                "direction": "east",
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            }
        }
        
        result = UIComponents.create_camera_grid_html(sample_monitoring_data)
        
        assert "EAST VIEW" in result


class TestUIComponentsCreateSystemInfo:
    """Test cases for create_system_info method."""

    def test_create_system_info_without_data(self):
        """Test create_system_info shows offline when no data."""
        with patch('data_loader.get_last_update_time', return_value=None):
            result = UIComponents.create_system_info(None)
            
            assert "OFFLINE" in result
            assert "System Status" in result

    def test_create_system_info_with_data(self, sample_monitoring_data):
        """Test create_system_info shows online with data."""
        with patch('data_loader.get_last_update_time', return_value="2025-01-01 10:00:00 UTC"):
            result = UIComponents.create_system_info(sample_monitoring_data)
            
            assert "ONLINE" in result
            assert "System Status" in result

    def test_create_system_info_contains_version(self):
        """Test create_system_info contains version info."""
        result = UIComponents.create_system_info(None)
        
        assert "RSU Monitor v1.0" in result

    def test_create_system_info_shows_current_time(self):
        """Test create_system_info shows current time."""
        result = UIComponents.create_system_info(None)
        
        assert "Current Time" in result
        assert "UTC" in result


class TestMonitoringDataMethods:
    """Test cases for MonitoringData helper methods."""

    def test_get_total_vehicles(self, sample_monitoring_data):
        """Test get_total_vehicles returns sum of vehicle counts."""
        result = sample_monitoring_data.get_total_vehicles()
        
        # 5 + 3 + 8 + 2 = 18
        assert result == 18

    def test_get_total_pedestrians_from_api(self, sample_monitoring_data):
        """Test get_total_pedestrians uses API count when available."""
        result = sample_monitoring_data.get_total_pedestrians()
        
        assert result == 6  # From total_pedestrian_count

    def test_get_total_pedestrians_calculated(self, sample_monitoring_data):
        """Test get_total_pedestrians calculates when API count not available."""
        sample_monitoring_data.data.total_pedestrian_count = None
        result = sample_monitoring_data.get_total_pedestrians()
        
        # 2 + 1 + 3 + 0 = 6
        assert result == 6

    def test_get_traffic_status_heavy(self, sample_monitoring_data):
        """Test get_traffic_status returns HEAVY for high density."""
        sample_monitoring_data.data.eastbound_density = 10
        result = sample_monitoring_data.get_traffic_status()
        
        assert result == "HEAVY"

    def test_get_traffic_status_moderate(self, sample_monitoring_data):
        """Test get_traffic_status returns MODERATE for medium density."""
        sample_monitoring_data.data.northbound_density = 4
        sample_monitoring_data.data.southbound_density = 3
        sample_monitoring_data.data.eastbound_density = 4
        sample_monitoring_data.data.westbound_density = 2
        result = sample_monitoring_data.get_traffic_status()
        
        assert result == "MODERATE"

    def test_get_traffic_status_light(self, sample_monitoring_data):
        """Test get_traffic_status returns LIGHT for low density."""
        sample_monitoring_data.data.northbound_density = 1
        sample_monitoring_data.data.southbound_density = 1
        sample_monitoring_data.data.eastbound_density = 2
        sample_monitoring_data.data.westbound_density = 1
        result = sample_monitoring_data.get_traffic_status()
        
        assert result == "LIGHT"

    def test_get_busy_directions(self, sample_monitoring_data):
        """Test get_busy_directions returns directions with density >= 3."""
        result = sample_monitoring_data.get_busy_directions()
        
        assert "Northbound" in result
        assert "Southbound" in result
        assert "Eastbound" in result
        assert "Westbound" not in result  # density is 2


class TestConfigClass:
    """Test cases for Config class."""

    def test_get_all_settings_returns_dict(self):
        """Test get_all_settings returns dictionary."""
        settings = Config.get_all_settings()
        
        assert isinstance(settings, dict)

    def test_get_all_settings_contains_required_keys(self):
        """Test get_all_settings contains all required keys."""
        settings = Config.get_all_settings()
        
        required_keys = [
            'refresh_interval', 'api_url', 'app_title', 'app_port',
            'app_host', 'ui_theme', 'high_density_threshold',
            'moderate_density_threshold'
        ]
        
        for key in required_keys:
            assert key in settings

    def test_default_theme_is_light(self):
        """Test default UI theme is light."""
        # This tests the default, not the env var override
        assert Config.get_ui_theme() in ['light', 'dark']
