# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""UI component tests aligned with the current src/ui implementation."""

import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
from unittest.mock import patch

import pytest


# Ensure ui_components imports `models` and `config` from src/ui.
UI_SRC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "src", "ui")
if UI_SRC_PATH not in sys.path:
    sys.path.insert(0, UI_SRC_PATH)

# Avoid conflicts with top-level src/models when tests run in a shared session.
for module_name in ("models", "config"):
    if module_name in sys.modules:
        del sys.modules[module_name]

from config import Config
from models import (
    IntersectionData,
    MonitoringData,
    RegionCount,
    TrafficContext,
    VLMAnalysis,
    WeatherData,
)
from ui_components import ThemeColors, UIComponents


@pytest.fixture
def sample_region_counts():
    return {
        "north": RegionCount(vehicle=5, pedestrian=2),
        "south": RegionCount(vehicle=3, pedestrian=1),
        "east": RegionCount(vehicle=8, pedestrian=3),
        "west": RegionCount(vehicle=2, pedestrian=0),
    }


@pytest.fixture
def sample_intersection_data(sample_region_counts):
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
        west_timestamp="2025-01-01T10:00:00Z",
    )


@pytest.fixture
def sample_traffic_context():
    return TrafficContext(
        analysis_period={"start": "2025-01-01T10:00:00", "end": "2025-01-01T10:05:00"},
        avg_densities={"north": 4, "south": 3, "east": 6, "west": 2},
        peak_densities={"north": 7, "south": 5, "east": 10, "west": 3},
    )


@pytest.fixture
def sample_vlm_analysis(sample_traffic_context):
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
                "weather_related": False,
            }
        ],
        recommendations=["Consider alternative routes to avoid east direction"],
    )


@pytest.fixture
def sample_weather_data():
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
        temperature_unit="F",
    )


@pytest.fixture
def sample_camera_data_objects():
    return {
        "north_camera": {
            "camera_id": "camera1",
            "direction": "north",
            "timestamp": "2025-01-01T10:00:00Z",
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        },
        "east_camera": {
            "camera_id": "camera2",
            "direction": "east",
            "timestamp": "2025-01-01T10:00:00Z",
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        },
        "south_camera": {
            "camera_id": "camera3",
            "direction": "south",
            "timestamp": "2025-01-01T10:00:00Z",
            "image_base64": None,
        },
        "west_camera": {
            "camera_id": "camera4",
            "direction": "west",
            "timestamp": "2025-01-01T10:00:00Z",
            "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        },
    }


@pytest.fixture
def sample_monitoring_data(
    sample_intersection_data,
    sample_camera_data_objects,
    sample_vlm_analysis,
    sample_weather_data,
):
    return MonitoringData(
        timestamp="2025-01-01T10:00:00Z",
        intersection_id="INT-001",
        data=sample_intersection_data,
        camera_images=sample_camera_data_objects,
        vlm_analysis=sample_vlm_analysis,
        weather_data=sample_weather_data,
    )


class TestThemeColors:
    def test_get_colors_light_theme(self):
        with patch.object(Config, "get_ui_theme", return_value="light"):
            colors = ThemeColors.get_colors()
        assert colors["bg_primary"] == "#ffffff"
        assert colors["text_primary"] == "#1f2937"

    def test_get_colors_dark_theme(self):
        with patch.object(Config, "get_ui_theme", return_value="dark"):
            colors = ThemeColors.get_colors()
        assert colors["bg_primary"] == "#1f2937"
        assert colors["text_primary"] == "#f3f4f6"


class TestUIComponents:
    def test_render_markdown_none(self):
        assert asyncio.run(UIComponents._render_markdown(None)) == ""

    def test_create_debug_panel(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_debug_panel(sample_monitoring_data))
        assert "Debug Timestamps" in result
        assert "EAST" in result
        assert "NORTH" in result



class TestUIComponentsTrafficDensityColor:
    def test_high_density_returns_red(self):
        with patch.object(Config, "get_high_density_threshold", return_value=10), patch.object(
            Config, "get_moderate_density_threshold", return_value=5
        ):
            color = asyncio.run(UIComponents._get_traffic_density_color(15))
            assert color == "#ecb3b3"

    def test_moderate_density_returns_yellow(self):
        with patch.object(Config, "get_high_density_threshold", return_value=10), patch.object(
            Config, "get_moderate_density_threshold", return_value=5
        ):
            color = asyncio.run(UIComponents._get_traffic_density_color(7))
            assert color == "#ffff99"

    def test_low_density_returns_white(self):
        with patch.object(Config, "get_high_density_threshold", return_value=10), patch.object(
            Config, "get_moderate_density_threshold", return_value=5
        ):
            color = asyncio.run(UIComponents._get_traffic_density_color(3))
            assert color == "#ffffff"

    def test_boundary_high_density(self):
        with patch.object(Config, "get_high_density_threshold", return_value=10), patch.object(
            Config, "get_moderate_density_threshold", return_value=5
        ):
            color = asyncio.run(UIComponents._get_traffic_density_color(10))
            assert color == "#ecb3b3"

    def test_boundary_moderate_density(self):
        with patch.object(Config, "get_high_density_threshold", return_value=10), patch.object(
            Config, "get_moderate_density_threshold", return_value=5
        ):
            color = asyncio.run(UIComponents._get_traffic_density_color(5))
            assert color == "#ffff99"


class TestUIComponentsCreateHeader:
    def test_create_header_without_data(self):
        result = asyncio.run(UIComponents.create_header(None))
        assert "DATA UNAVAILABLE" in result
        assert "Smart Traffic Intersection Agent" in result

    def test_create_header_with_data(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_header(sample_monitoring_data))
        assert sample_monitoring_data.data.intersection_name in result
        assert "DATA UNAVAILABLE" not in result

    def test_create_header_contains_styling(self):
        result = asyncio.run(UIComponents.create_header(None))
        assert "style=" in result
        assert "background" in result
        assert "border-radius" in result


class TestUIComponentsCreateTrafficSummary:
    def test_create_traffic_summary_without_data(self):
        result = asyncio.run(UIComponents.create_traffic_summary(None))
        assert "No traffic data available" in result

    def test_create_traffic_summary_with_data(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_traffic_summary(sample_monitoring_data))
        assert "TRAFFIC SUMMARY" in result
        assert "NORTH" in result
        assert "SOUTH" in result
        assert "EAST" in result
        assert "WEST" in result

    def test_create_traffic_summary_shows_densities(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_traffic_summary(sample_monitoring_data))
        assert str(sample_monitoring_data.data.northbound_density) in result
        assert str(sample_monitoring_data.data.total_density) in result

    def test_create_traffic_summary_shows_pedestrians(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_traffic_summary(sample_monitoring_data))
        assert "PEDESTRIANS" in result


class TestUIComponentsCreateEnvironmentalPanel:
    def test_create_environmental_panel_without_data(self):
        result = asyncio.run(UIComponents.create_environmental_panel(None))
        assert "No environmental data available" in result

    def test_create_environmental_panel_with_data(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_environmental_panel(sample_monitoring_data))
        assert "ENVIRONMENTAL DATA" in result
        assert "TEMPERATURE" in result
        assert "HUMIDITY" in result
        assert "WIND" in result

    def test_create_environmental_panel_shows_temperature(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_environmental_panel(sample_monitoring_data))
        temp = int(sample_monitoring_data.weather_data.temperature_fahrenheit)
        assert str(temp) in result

    def test_create_environmental_panel_wind_direction_north(self, sample_monitoring_data):
        sample_monitoring_data.weather_data.wind_direction_degrees = 0
        result = asyncio.run(UIComponents.create_environmental_panel(sample_monitoring_data))
        assert "WIND N" in result

    def test_create_environmental_panel_wind_direction_east(self, sample_monitoring_data):
        sample_monitoring_data.weather_data.wind_direction_degrees = 90
        result = asyncio.run(UIComponents.create_environmental_panel(sample_monitoring_data))
        assert "WIND E" in result

    def test_create_environmental_panel_wind_direction_south(self, sample_monitoring_data):
        sample_monitoring_data.weather_data.wind_direction_degrees = 180
        result = asyncio.run(UIComponents.create_environmental_panel(sample_monitoring_data))
        assert "WIND S" in result

    def test_create_environmental_panel_wind_direction_west(self, sample_monitoring_data):
        sample_monitoring_data.weather_data.wind_direction_degrees = 270
        result = asyncio.run(UIComponents.create_environmental_panel(sample_monitoring_data))
        assert "WIND W" in result

    def test_create_environmental_panel_daytime_status(self, sample_monitoring_data):
        sample_monitoring_data.weather_data.is_daytime = True
        result = asyncio.run(UIComponents.create_environmental_panel(sample_monitoring_data))
        assert "DAY TIME" in result

    def test_create_environmental_panel_nighttime_status(self, sample_monitoring_data):
        sample_monitoring_data.weather_data.is_daytime = False
        result = asyncio.run(UIComponents.create_environmental_panel(sample_monitoring_data))
        assert "NIGHT TIME" in result

class TestUIComponentsCreateCameraImages:
    """Camera image rendering tests aligned to latest UI component behavior."""

    def test_create_camera_images_without_data(self):
        result = asyncio.run(UIComponents.create_camera_images(None))
        assert result == []

    def test_create_camera_images_with_data(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_camera_images(sample_monitoring_data))
        assert len(result) > 0

    def test_create_camera_images_returns_tuples(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_camera_images(sample_monitoring_data))
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_create_camera_images_with_dict_format(self, sample_monitoring_data):
        sample_monitoring_data.camera_images = {
            "north_camera": {
                "camera_id": "cam1",
                "direction": "north",
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            }
        }

        result = asyncio.run(UIComponents.create_camera_images(sample_monitoring_data))
        assert len(result) == 1

    def test_create_camera_images_flags_stale_feed(self, sample_monitoring_data):
        stale_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        sample_monitoring_data.camera_images = {
            "north_camera": {
                "camera_id": "cam1",
                "direction": "north",
                "timestamp": stale_timestamp,
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            }
        }

        with patch.object(Config, "get_camera_stale_threshold_seconds", return_value=30.0):
            result = asyncio.run(UIComponents.create_camera_images(sample_monitoring_data))

        assert len(result) == 1
        _, caption = result[0]
        assert "STALE" in caption

    def test_create_camera_images_fresh_feed_not_flagged(self, sample_monitoring_data):
        fresh_timestamp = datetime.now(timezone.utc).isoformat()
        sample_monitoring_data.camera_images = {
            "north_camera": {
                "camera_id": "cam1",
                "direction": "north",
                "timestamp": fresh_timestamp,
                "image_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
            }
        }

        with patch.object(Config, "get_camera_stale_threshold_seconds", return_value=30.0):
            result = asyncio.run(UIComponents.create_camera_images(sample_monitoring_data))

        assert len(result) == 1
        _, caption = result[0]
        assert "STALE" not in caption


class TestUIComponentsCreateAlertsPanel:
    """Alert panel tests aligned to latest UI component behavior."""

    def test_create_alerts_panel_without_data(self):
        result = asyncio.run(UIComponents.create_alerts_panel(None))
        assert "No alerts data available" in result

    def test_create_alerts_panel_no_alerts(self, sample_monitoring_data):
        sample_monitoring_data.vlm_analysis.alerts = []
        sample_monitoring_data.vlm_analysis.recommendations = []

        result = asyncio.run(UIComponents.create_alerts_panel(sample_monitoring_data))
        assert "ALL SYSTEMS OPERATIONAL" in result

    def test_create_alerts_panel_with_structured_alert(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_alerts_panel(sample_monitoring_data))
        assert "Traffic Status and Alerts" in result
        assert "WARNING ALERT" in result

    def test_create_alerts_panel_critical_alert(self, sample_monitoring_data):
        sample_monitoring_data.vlm_analysis.alerts = [
            {
                "alert_type": "accident",
                "level": "critical",
                "description": "Major accident reported",
                "weather_related": False,
            }
        ]

        result = asyncio.run(UIComponents.create_alerts_panel(sample_monitoring_data))
        assert "CRITICAL ALERT" in result

    def test_create_alerts_panel_advisory_alert(self, sample_monitoring_data):
        sample_monitoring_data.vlm_analysis.alerts = [
            {
                "alert_type": "info",
                "level": "advisory",
                "description": "Light traffic expected",
                "weather_related": False,
            }
        ]

        result = asyncio.run(UIComponents.create_alerts_panel(sample_monitoring_data))
        assert "ADVISORY ALERT" in result

    def test_create_alerts_panel_weather_related_alert(self, sample_monitoring_data):
        sample_monitoring_data.vlm_analysis.alerts = [
            {
                "alert_type": "weather",
                "level": "warning",
                "description": "Heavy rain affecting visibility",
                "weather_related": True,
            }
        ]

        result = asyncio.run(UIComponents.create_alerts_panel(sample_monitoring_data))
        assert "🌦️" in result

    def test_create_alerts_panel_with_recommendations(self, sample_monitoring_data):
        result = asyncio.run(UIComponents.create_alerts_panel(sample_monitoring_data))
        assert "Recommendations" in result
        assert "Recommendation 1" in result

    def test_create_alerts_panel_string_alert_fallback(self, sample_monitoring_data):
        sample_monitoring_data.vlm_analysis.alerts = ["Simple text alert message"]

        result = asyncio.run(UIComponents.create_alerts_panel(sample_monitoring_data))
        assert "Simple text alert message" in result


class TestUIComponentsCreateSystemInfo:
    """System info tests aligned to latest UI component behavior."""

    def test_create_system_info_without_data(self):
        result = UIComponents.build_system_info_html(None)
        assert "OFFLINE" in result
        assert "System Status" in result

    def test_create_system_info_with_data(self, sample_monitoring_data):
        result = UIComponents.build_system_info_html(sample_monitoring_data)
        assert "ONLINE" in result
        assert "System Status" in result

    def test_create_system_info_contains_version(self):
        result = UIComponents.build_system_info_html(None)
        assert "RSU Monitor v1.0" in result

    def test_create_system_info_shows_current_time(self):
        result = UIComponents.build_system_info_html(None)
        assert "Current Time" in result
        assert "UTC" in result

    def test_create_system_info_current_time_is_live(self):
        before = datetime.now(timezone.utc)
        result = UIComponents.build_system_info_html(None)
        after = datetime.now(timezone.utc)

        before_prefix = before.strftime("%Y-%m-%d %H:%M")
        after_prefix = after.strftime("%Y-%m-%d %H:%M")
        assert before_prefix in result or after_prefix in result

    def test_create_system_info_async_wrapper_matches_sync_builder(self, sample_monitoring_data):
        async_result = asyncio.run(UIComponents.create_system_info(sample_monitoring_data))
        assert "ONLINE" in async_result
        assert "Current Time" in async_result


class TestMonitoringDataHelpers:
    def test_get_total_vehicles(self, sample_monitoring_data):
        assert sample_monitoring_data.get_total_vehicles() == 18

    def test_get_total_pedestrians(self, sample_monitoring_data):
        assert sample_monitoring_data.get_total_pedestrians() == 6

    def test_get_traffic_status(self, sample_monitoring_data):
        assert sample_monitoring_data.get_traffic_status() == "HEAVY"

    def test_get_busy_directions(self, sample_monitoring_data):
        directions = sample_monitoring_data.get_busy_directions()
        assert "Northbound" in directions
        assert "Eastbound" in directions
        assert "Westbound" not in directions


class TestConfigClass:
    """Config tests aligned to latest src/ui/config.py behavior."""

    def test_get_all_settings_returns_dict(self):
        settings = Config.get_all_settings()
        assert isinstance(settings, dict)

    def test_get_all_settings_contains_required_keys(self):
        settings = Config.get_all_settings()
        required_keys = [
            'api_url', 'app_title', 'app_port',
            'app_host', 'ui_theme', 'high_density_threshold',
            'moderate_density_threshold'
        ]
        for key in required_keys:
            assert key in settings

    def test_default_theme_is_light_or_dark(self):
        assert Config.get_ui_theme() in ["light", "dark"]
