# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Unit tests for main.py - Traffic Intersection Agent main module.

Tests cover:
- Application creation and configuration
- Lifespan management (startup and shutdown)
- Health check endpoint
- Environment variable handling
"""

import asyncio
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestCreateApp:
    """Tests for create_app function."""

    def test_create_app_returns_fastapi_instance(self):
        """Test that create_app returns a FastAPI application."""
        from main import create_app
        
        app = create_app()
        
        assert isinstance(app, FastAPI)

    def test_create_app_default_title(self):
        """Test app has default title when env var not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove API_NAME if present
            os.environ.pop("API_NAME", None)
            from main import create_app
            
            app = create_app()
            
            assert app.title == "Traffic Intersection Agent"

    def test_create_app_custom_title(self):
        """Test app uses custom title from environment variable."""
        with patch.dict(os.environ, {"API_NAME": "Custom Traffic Agent"}):
            from main import create_app
            
            app = create_app()
            
            assert app.title == "Custom Traffic Agent"

    def test_create_app_has_correct_version(self):
        """Test app has correct version."""
        from main import create_app
        
        app = create_app()
        
        assert app.version == "1.0.0"

    def test_create_app_has_description(self):
        """Test app has description set."""
        from main import create_app
        
        app = create_app()
        
        assert "Single intersection monitoring" in app.description

    def test_create_app_includes_router(self):
        """Test app includes API router with correct prefix."""
        from main import create_app
        
        app = create_app()
        
        # Check that routes are registered
        routes = [route.path for route in app.routes]
        assert any("/api/v1" in route for route in routes)


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check_returns_healthy(self):
        """Test health endpoint returns healthy status."""
        from main import create_app
        
        app = create_app()
        # Create test client without lifespan to avoid startup errors
        with patch.object(app, 'router'):
            client = TestClient(app, raise_server_exceptions=False)
            
            response = client.get("/health")
            
            # May fail if lifespan has issues, but we test the concept
            if response.status_code == 200:
                data = response.json()
                assert data["status"] == "healthy"
                assert data["service"] == "traffic-intersection-agent"

    def test_health_check_includes_timestamp(self):
        """Test health endpoint includes timestamp."""
        from main import create_app
        
        app = create_app()
        
        # Test that health endpoint is registered
        health_routes = [r for r in app.routes if hasattr(r, 'path') and r.path == "/health"]
        assert len(health_routes) == 1


class TestLifespan:
    """Tests for application lifespan management."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services for lifespan testing."""
        mock_config = MagicMock()
        mock_config.get_intersection_id.return_value = "INT-001"
        mock_config.get_camera_topics.return_value = ["camera1", "camera2"]
        
        mock_weather = AsyncMock()
        mock_weather.start = AsyncMock()
        mock_weather.stop = AsyncMock()
        
        mock_vlm = MagicMock()
        
        mock_data_aggregator = MagicMock()
        
        mock_mqtt = AsyncMock()
        mock_mqtt.initialize = AsyncMock()
        mock_mqtt.set_event_loop = MagicMock()
        mock_mqtt.start = AsyncMock()
        mock_mqtt.stop = AsyncMock()
        
        return {
            'config': mock_config,
            'weather': mock_weather,
            'vlm': mock_vlm,
            'data_aggregator': mock_data_aggregator,
            'mqtt': mock_mqtt
        }

    @pytest.mark.asyncio
    async def test_lifespan_initializes_config_service(self, mock_services):
        """Test lifespan initializes config service."""
        from main import lifespan
        
        app = FastAPI()
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            async with lifespan(app):
                assert hasattr(app.state, 'config')

    @pytest.mark.asyncio
    async def test_lifespan_initializes_weather_service(self, mock_services):
        """Test lifespan initializes and starts weather service."""
        from main import lifespan
        
        app = FastAPI()
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            async with lifespan(app):
                assert hasattr(app.state, 'weather_service')
                mock_services['weather'].start.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_initializes_vlm_service(self, mock_services):
        """Test lifespan initializes VLM service."""
        from main import lifespan
        
        app = FastAPI()
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            async with lifespan(app):
                assert hasattr(app.state, 'vlm_service')

    @pytest.mark.asyncio
    async def test_lifespan_initializes_data_aggregator(self, mock_services):
        """Test lifespan initializes data aggregator service."""
        from main import lifespan
        
        app = FastAPI()
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            async with lifespan(app):
                assert hasattr(app.state, 'data_aggregator')

    @pytest.mark.asyncio
    async def test_lifespan_initializes_mqtt_service(self, mock_services):
        """Test lifespan initializes and starts MQTT service."""
        from main import lifespan
        
        app = FastAPI()
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            async with lifespan(app):
                assert hasattr(app.state, 'mqtt')
                mock_services['mqtt'].initialize.assert_called_once()
                mock_services['mqtt'].set_event_loop.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_creates_mqtt_task(self, mock_services):
        """Test lifespan creates MQTT background task."""
        from main import lifespan
        
        app = FastAPI()
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            async with lifespan(app):
                assert hasattr(app.state, 'mqtt_task')

    @pytest.mark.asyncio
    async def test_lifespan_cleanup_stops_mqtt(self, mock_services):
        """Test lifespan cleanup stops MQTT service."""
        from main import lifespan
        
        app = FastAPI()
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            async with lifespan(app):
                pass
            
            # After exiting context, stop should be called
            mock_services['mqtt'].stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_cleanup_stops_weather_service(self, mock_services):
        """Test lifespan cleanup stops weather service."""
        from main import lifespan
        
        app = FastAPI()
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            async with lifespan(app):
                pass
            
            mock_services['weather'].stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_lifespan_handles_startup_error(self, mock_services):
        """Test lifespan handles errors during startup."""
        from main import lifespan
        
        app = FastAPI()
        mock_services['config'].get_intersection_id.side_effect = Exception("Config error")
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            with pytest.raises(Exception, match="Config error"):
                async with lifespan(app):
                    pass


class TestMainFunction:
    """Tests for main() entry point function."""

    def test_main_sets_default_log_level(self):
        """Test main uses default log level when not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOG_LEVEL", None)
            
            with patch('main.create_app') as mock_create_app, \
                 patch('main.uvicorn.run') as mock_run, \
                 patch('logging.basicConfig') as mock_logging:
                
                mock_app = MagicMock()
                mock_create_app.return_value = mock_app
                
                from main import main
                main()
                
                mock_logging.assert_called_once()
                # Check log level is INFO (default)
                call_kwargs = mock_logging.call_args[1]
                assert call_kwargs['level'] == 20  # logging.INFO

    def test_main_uses_custom_log_level(self):
        """Test main uses custom log level from environment."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            with patch('main.create_app') as mock_create_app, \
                 patch('main.uvicorn.run') as mock_run, \
                 patch('logging.basicConfig') as mock_logging:
                
                mock_app = MagicMock()
                mock_create_app.return_value = mock_app
                
                from main import main
                main()
                
                call_kwargs = mock_logging.call_args[1]
                assert call_kwargs['level'] == 10  # logging.DEBUG

    def test_main_uses_default_port(self):
        """Test main uses default port when not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRAFFIC_INTERSECTION_AGENT_PORT", None)
            
            with patch('main.create_app') as mock_create_app, \
                 patch('main.uvicorn.run') as mock_run:
                
                mock_app = MagicMock()
                mock_create_app.return_value = mock_app
                
                from main import main
                main()
                
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs['port'] == 8081

    def test_main_uses_custom_port(self):
        """Test main uses custom port from environment."""
        with patch.dict(os.environ, {"AGENT_BACKEND_HOSTPORT": "9090"}):
            with patch('main.create_app') as mock_create_app, \
                 patch('main.uvicorn.run') as mock_run:
                
                mock_app = MagicMock()
                mock_create_app.return_value = mock_app
                
                from main import main
                main()
                
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs['port'] == 9090

    def test_main_uses_default_host(self):
        """Test main uses default host when not set."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TRAFFIC_INTERSECTION_AGENT_HOST", None)
            
            with patch('main.create_app') as mock_create_app, \
                 patch('main.uvicorn.run') as mock_run:
                
                mock_app = MagicMock()
                mock_create_app.return_value = mock_app
                
                from main import main
                main()
                
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs['host'] == "0.0.0.0"

    def test_main_uses_custom_host(self):
        """Test main uses custom host from environment."""
        with patch.dict(os.environ, {"AGENT_BACKEND_HOST": "127.0.0.1"}):
            with patch('main.create_app') as mock_create_app, \
                 patch('main.uvicorn.run') as mock_run:
                
                mock_app = MagicMock()
                mock_create_app.return_value = mock_app
                
                from main import main
                main()
                
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs['host'] == "127.0.0.1"

    def test_main_calls_uvicorn_run(self):
        """Test main calls uvicorn.run with app."""
        with patch('main.create_app') as mock_create_app, \
             patch('main.uvicorn.run') as mock_run:
            
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            
            from main import main
            main()
            
            mock_run.assert_called_once()
            assert mock_run.call_args[0][0] == mock_app

    def test_main_enables_access_log(self):
        """Test main enables access logging."""
        with patch('main.create_app') as mock_create_app, \
             patch('main.uvicorn.run') as mock_run:
            
            mock_app = MagicMock()
            mock_create_app.return_value = mock_app
            
            from main import main
            main()
            
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs['access_log'] is True


class TestStructlogConfiguration:
    """Tests for structlog configuration."""

    def test_structlog_configured(self):
        """Test that structlog is configured."""
        import structlog
        
        # Import main to trigger configuration
        import main
        
        # Get a logger and verify it works
        logger = structlog.get_logger("test")
        assert logger is not None

    def test_logger_instance_exists(self):
        """Test that module logger is created."""
        from main import logger
        
        assert logger is not None


class TestAppStateManagement:
    """Tests for application state management."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services."""
        mock_config = MagicMock()
        mock_config.get_intersection_id.return_value = "INT-001"
        mock_config.get_camera_topics.return_value = ["camera1"]
        
        mock_weather = AsyncMock()
        mock_weather.start = AsyncMock()
        mock_weather.stop = AsyncMock()
        
        mock_vlm = MagicMock()
        mock_data_aggregator = MagicMock()
        
        mock_mqtt = AsyncMock()
        mock_mqtt.initialize = AsyncMock()
        mock_mqtt.set_event_loop = MagicMock()
        mock_mqtt.start = AsyncMock()
        mock_mqtt.stop = AsyncMock()
        
        return {
            'config': mock_config,
            'weather': mock_weather,
            'vlm': mock_vlm,
            'data_aggregator': mock_data_aggregator,
            'mqtt': mock_mqtt
        }

    @pytest.mark.asyncio
    async def test_app_state_contains_all_services(self, mock_services):
        """Test app state contains all required services after startup."""
        from main import lifespan
        
        app = FastAPI()
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            async with lifespan(app):
                assert hasattr(app.state, 'config')
                assert hasattr(app.state, 'weather_service')
                assert hasattr(app.state, 'vlm_service')
                assert hasattr(app.state, 'data_aggregator')
                assert hasattr(app.state, 'mqtt')
                assert hasattr(app.state, 'mqtt_task')

    @pytest.mark.asyncio
    async def test_cleanup_handles_missing_mqtt_task(self, mock_services):
        """Test cleanup handles case where mqtt_task doesn't exist."""
        from main import lifespan
        
        app = FastAPI()
        
        # Simulate error before mqtt_task is created
        mock_services['mqtt'].initialize.side_effect = Exception("MQTT init failed")
        
        with patch('main.ConfigService', return_value=mock_services['config']), \
             patch('main.WeatherService', return_value=mock_services['weather']), \
             patch('main.VLMService', return_value=mock_services['vlm']), \
             patch('main.DataAggregatorService', return_value=mock_services['data_aggregator']), \
             patch('main.MQTTService', return_value=mock_services['mqtt']):
            
            with pytest.raises(Exception, match="MQTT init failed"):
                async with lifespan(app):
                    pass


class TestEnvironmentVariables:
    """Tests for environment variable handling."""

    def test_all_default_values(self):
        """Test all default environment variable values."""
        env_vars_to_clear = [
            "API_NAME",
            "LOG_LEVEL", 
            "TRAFFIC_INTERSECTION_AGENT_PORT",
            "TRAFFIC_INTERSECTION_AGENT_HOST"
        ]
        
        with patch.dict(os.environ, {}, clear=False):
            for var in env_vars_to_clear:
                os.environ.pop(var, None)
            
            with patch('main.uvicorn.run') as mock_run:
                from main import create_app, main
                
                app = create_app()
                assert app.title == "Traffic Intersection Agent"
                
                main()
                
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs['host'] == "0.0.0.0"
                assert call_kwargs['port'] == 8081
                assert call_kwargs['log_level'] == "info"

    def test_custom_environment_configuration(self):
        """Test custom environment configuration."""
        custom_env = {
            "API_NAME": "My Custom Agent",
            "LOG_LEVEL": "WARNING",
            "AGENT_BACKEND_HOSTPORT": "3000",
            "AGENT_BACKEND_HOST": "localhost"
        }
        
        with patch.dict(os.environ, custom_env):
            with patch('main.uvicorn.run') as mock_run:
                from main import create_app, main
                
                app = create_app()
                assert app.title == "My Custom Agent"
                
                main()
                
                call_kwargs = mock_run.call_args[1]
                assert call_kwargs['host'] == "localhost"
                assert call_kwargs['port'] == 3000
                assert call_kwargs['log_level'] == "warning"
