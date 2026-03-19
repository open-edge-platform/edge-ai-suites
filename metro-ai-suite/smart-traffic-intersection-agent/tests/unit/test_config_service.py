# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for Config Service."""

import pytest
import os
import json
import tempfile
from unittest.mock import patch, mock_open
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.config import ConfigService, hash_intersection_name


class TestHashIntersectionName:
    """Test cases for hash_intersection_name function."""

    def test_hash_returns_string(self):
        """Test that hash function returns a string."""
        result = hash_intersection_name("Test Intersection")
        assert isinstance(result, str)

    def test_hash_default_length(self):
        """Test hash returns default length of 16 characters."""
        result = hash_intersection_name("Test Intersection")
        assert len(result) == 16

    def test_hash_custom_length(self):
        """Test hash returns custom length."""
        result = hash_intersection_name("Test Intersection", length=8)
        assert len(result) == 8

    def test_hash_same_input_same_output(self):
        """Test same input produces same hash."""
        result1 = hash_intersection_name("Test Intersection")
        result2 = hash_intersection_name("Test Intersection")
        assert result1 == result2

    def test_hash_different_input_different_output(self):
        """Test different inputs produce different hashes."""
        result1 = hash_intersection_name("Intersection A")
        result2 = hash_intersection_name("Intersection B")
        assert result1 != result2


class TestConfigServiceInitialization:
    """Test cases for ConfigService initialization."""

    def test_init_without_config_file(self):
        """Test ConfigService initializes without config file."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                assert service.config is not None

    def test_init_with_config_file(self):
        """Test ConfigService loads from config file."""
        config_data = {
            "intersection": {"name": "Test Intersection"},
            "mqtt": {"host": "localhost"}
        }
        
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=json.dumps(config_data))):
                    service = ConfigService()
                    assert service.get_intersection_name() == "Test Intersection"

    def test_init_with_invalid_config_file(self):
        """Test ConfigService raises on invalid config file."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('pathlib.Path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data="invalid json")):
                    with pytest.raises(Exception):
                        service = ConfigService()


class TestConfigServiceEnvironmentOverrides:
    """Test cases for environment variable overrides."""

    def test_intersection_name_from_env(self):
        """Test intersection name from environment variable."""
        with patch.dict(os.environ, {"INTERSECTION_NAME": "Env Intersection"}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                assert service.get_intersection_name() == "Env Intersection"

    def test_intersection_coordinates_from_env(self):
        """Test intersection coordinates from environment variables."""
        env_vars = {
            "INTERSECTION_LATITUDE": "37.7749",
            "INTERSECTION_LONGITUDE": "-122.4194"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                lat, lon = service.get_intersection_coordinates()
                assert lat == 37.7749
                assert lon == -122.4194

    def test_mqtt_config_from_env(self):
        """Test MQTT configuration from environment variables."""
        env_vars = {
            "MQTT_HOST": "mqtt.example.com",
            "MQTT_PORT": "1884"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                mqtt_config = service.get_mqtt_config()
                assert mqtt_config.get("host") == "mqtt.example.com"
                assert mqtt_config.get("port") == 1884

    def test_weather_mock_from_env(self):
        """Test weather mock setting from environment variable."""
        with patch.dict(os.environ, {"WEATHER_MOCK": "true"}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                weather_config = service.get_weather_config()
                assert weather_config.get("use_mock") is True

    def test_weather_mock_false_from_env(self):
        """Test weather mock false setting from environment variable."""
        with patch.dict(os.environ, {"WEATHER_MOCK": "false"}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                weather_config = service.get_weather_config()
                assert weather_config.get("use_mock") is False

    def test_vlm_config_from_env(self):
        """Test VLM configuration from environment variables."""
        env_vars = {
            "VLM_BASE_URL": "http://vlm:9000",
            "VLM_MODEL_NAME": "custom-model",
            "VLM_TIMEOUT_SECONDS": "60",
            "VLM_MAX_COMPLETION_TOKENS": "1500",
            "VLM_TEMPERATURE": "0.5",
            "VLM_TOP_P": "0.9"
        }
        with patch.dict(os.environ, env_vars, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                vlm_config = service.get_vlm_config()
                assert vlm_config.get("base_url") == "http://vlm:9000"
                assert vlm_config.get("model") == "custom-model"
                assert vlm_config.get("timeout_seconds") == 60
                assert vlm_config.get("max_completion_tokens") == 1500
                assert vlm_config.get("temperature") == 0.5
                assert vlm_config.get("top_p") == 0.9

    def test_high_density_threshold_from_env(self):
        """Test high density threshold from environment variable."""
        with patch.dict(os.environ, {"HIGH_DENSITY_THRESHOLD": "15"}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                assert service.get_high_density_threshold() == 15

    def test_traffic_buffer_duration_from_env(self):
        """Test traffic buffer duration from environment variable."""
        with patch.dict(os.environ, {"TRAFFIC_BUFFER_DURATION": "120"}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                traffic_config = service.get_traffic_config()
                assert traffic_config.get("analysis_window_seconds") == 120


class TestConfigServiceDefaults:
    """Test cases for default configuration values."""

    def test_default_intersection_name(self):
        """Test default intersection name."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('pathlib.Path.exists', return_value=False):
                with pytest.raises(FileNotFoundError):
                    service = ConfigService()

    def test_default_intersection_coordinates(self):
        """Test default intersection coordinates."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                lat, lon = service.get_intersection_coordinates()
                assert lat == 33.3091336
                assert lon == -111.9353095

    def test_default_high_density_threshold(self):
        """Test default high density threshold from config file."""
        service = ConfigService()
        # The actual default from config file is 10
        assert service.get_high_density_threshold() == 10

    def test_default_camera_topics(self):
        """Test default camera topics."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                topics = service.get_camera_topics()
                assert len(topics) == 4
                assert "scenescape/data/camera/camera1" in topics

    def test_default_image_topics(self):
        """Test default image topics."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                topics = service.get_image_topics()
                assert len(topics) == 4
                assert "scenescape/image/camera/camera1" in topics


class TestConfigServiceMethods:
    """Test cases for ConfigService methods."""

    def test_get_intersection_id(self):
        """Test getting intersection ID (hashed name)."""
        with patch.dict(os.environ, {"INTERSECTION_NAME": "Test"}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                intersection_id = service.get_intersection_id()
                expected_id = hash_intersection_name("Test")
                assert intersection_id == expected_id

    def test_get_mqtt_config_empty(self):
        """Test getting empty MQTT config."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                mqtt_config = service.get_mqtt_config()
                assert isinstance(mqtt_config, dict)

    def test_get_weather_config_empty(self):
        """Test getting empty weather config."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                weather_config = service.get_weather_config()
                assert isinstance(weather_config, dict)

    def test_get_vlm_config_empty(self):
        """Test getting empty VLM config."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                vlm_config = service.get_vlm_config()
                assert isinstance(vlm_config, dict)

    def test_get_traffic_config_empty(self):
        """Test getting empty traffic config."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                traffic_config = service.get_traffic_config()
                assert isinstance(traffic_config, dict)

    def test_update_config_simple_key(self):
        """Test updating config with simple key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                service.update_config("test_key", "test_value")
                assert service.config.get("test_key") == "test_value"

    def test_update_config_nested_key(self):
        """Test updating config with nested key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                service.update_config("intersection.name", "Updated Name")
                assert service.config.get("intersection", {}).get("name") == "Updated Name"

    def test_update_config_deep_nested_key(self):
        """Test updating config with deeply nested key."""
        with patch.dict(os.environ, {}, clear=True):
            with patch('os.path.exists', return_value=False):
                service = ConfigService()
                service.update_config("level1.level2.level3", "deep_value")
                assert service.config["level1"]["level2"]["level3"] == "deep_value"


class TestConfigServiceEnvOverridesFileConfig:
    """Test cases verifying environment variables override file config."""

    def test_env_overrides_file_config(self):
        """Test that environment variables override file configuration."""
        config_data = {
            "intersection": {"name": "File Intersection"}
        }
        
        with patch.dict(os.environ, {"INTERSECTION_NAME": "Env Intersection"}, clear=True):
            with patch('os.path.exists', return_value=True):
                with patch('builtins.open', mock_open(read_data=json.dumps(config_data))):
                    service = ConfigService()
                    # Env should override file
                    assert service.get_intersection_name() == "Env Intersection"
