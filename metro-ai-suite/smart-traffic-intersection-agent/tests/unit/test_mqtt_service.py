# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for MQTT Service."""

import pytest
import asyncio
import json
import os
import sys
from unittest.mock import Mock, patch, AsyncMock, MagicMock, PropertyMock
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from services.mqtt_service import MQTTService
from services.config import ConfigService
from services.data_aggregator import DataAggregatorService
from services.vlm_service import VLMService
from models import CameraDataMessage, CameraImage


class TestMQTTServiceInitialization:
    """Test cases for MQTTService initialization."""

    def test_init_with_default_config(self):
        """Test MQTTService initializes with default configuration."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = ["scenescape/data/camera/camera1"]
        mock_config.get_image_topics.return_value = ["scenescape/image/camera/camera1"]
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        assert service.host == "localhost"
        assert service.port == 1883
        assert service.use_tls is False
        assert service.connected is False
        assert service.client is None
        assert service.rate_limit_seconds == 10.0

    def test_init_with_custom_config(self):
        """Test MQTTService initializes with custom configuration."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {
            "host": "mqtt.example.com",
            "port": 8883,
            "use_tls": True,
            "ca_cert_path": "/path/to/cert.pem",
            "cert_required": True,
            "verify_hostname": True,
            "username": "testuser",
            "password": "testpass",
            "rate_limit_seconds": 5.0
        }
        mock_config.get_camera_topics.return_value = ["scenescape/data/camera/camera1"]
        mock_config.get_image_topics.return_value = ["scenescape/image/camera/camera1"]
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        assert service.host == "mqtt.example.com"
        assert service.port == 8883
        assert service.use_tls is True
        assert service.ca_cert_path == "/path/to/cert.pem"
        assert service.cert_required is True
        assert service.verify_hostname is True
        assert service.username == "testuser"
        assert service.password == "testpass"
        assert service.rate_limit_seconds == 5.0

    def test_init_sets_camera_topics(self):
        """Test MQTTService sets camera topics from config."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = [
            "scenescape/data/camera/camera1",
            "scenescape/data/camera/camera2"
        ]
        mock_config.get_image_topics.return_value = [
            "scenescape/image/camera/camera1",
            "scenescape/image/camera/camera2"
        ]
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        assert len(service.camera_topics) == 2
        assert len(service.image_topics) == 2


class TestMQTTServiceDirectionMapping:
    """Test cases for direction mapping."""

    def test_direction_mapping_exists(self):
        """Test that direction mapping is defined."""
        assert MQTTService.direction_mapping == {
            '1': 'south',
            '2': 'west',
            '3': 'north',
            '4': 'east',
        }

    def test_direction_mapping_all_cameras(self):
        """Test direction mapping for all camera numbers."""
        assert MQTTService.direction_mapping.get('1') == 'south'
        assert MQTTService.direction_mapping.get('2') == 'west'
        assert MQTTService.direction_mapping.get('3') == 'north'
        assert MQTTService.direction_mapping.get('4') == 'east'


class TestMQTTServiceInitialize:
    """Test cases for MQTTService initialize method."""

    @pytest.mark.asyncio
    async def test_initialize_creates_client(self):
        """Test initialize creates MQTT client."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        with patch('services.mqtt_service.mqtt.Client') as mock_mqtt_client:
            mock_client_instance = Mock()
            mock_mqtt_client.return_value = mock_client_instance
            
            await service.initialize()
            
            mock_mqtt_client.assert_called_once()
            assert service.client == mock_client_instance

    @pytest.mark.asyncio
    async def test_initialize_sets_callbacks(self):
        """Test initialize sets MQTT callbacks."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        with patch('services.mqtt_service.mqtt.Client') as mock_mqtt_client:
            mock_client_instance = Mock()
            mock_mqtt_client.return_value = mock_client_instance
            
            await service.initialize()
            
            assert mock_client_instance.on_connect == service._on_connect
            assert mock_client_instance.on_disconnect == service._on_disconnect
            assert mock_client_instance.on_message == service._on_message

    @pytest.mark.asyncio
    async def test_initialize_with_authentication(self):
        """Test initialize configures username/password authentication."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {
            "username": "testuser",
            "password": "testpass"
        }
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        with patch('services.mqtt_service.mqtt.Client') as mock_mqtt_client:
            mock_client_instance = Mock()
            mock_mqtt_client.return_value = mock_client_instance
            
            await service.initialize()
            
            mock_client_instance.username_pw_set.assert_called_once_with("testuser", "testpass")


class TestMQTTServiceCallbacks:
    """Test cases for MQTT callbacks."""

    def test_on_connect_success(self):
        """Test on_connect callback with successful connection."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = ["scenescape/data/camera/camera1"]
        mock_config.get_image_topics.return_value = ["scenescape/image/camera/camera1"]
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        mock_client = Mock()
        service._on_connect(mock_client, None, None, 0)
        
        assert service.connected is True
        mock_client.subscribe.assert_called()

    def test_on_connect_failure(self):
        """Test on_connect callback with failed connection."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        mock_client = Mock()
        service._on_connect(mock_client, None, None, 1)  # rc=1 means failure
        
        assert service.connected is False

    def test_on_disconnect_unexpected(self):
        """Test on_disconnect callback with unexpected disconnection."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = True
        
        service._on_disconnect(None, None, 1)  # rc != 0 means unexpected
        
        assert service.connected is False

    def test_on_disconnect_expected(self):
        """Test on_disconnect callback with expected disconnection."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = True
        
        service._on_disconnect(None, None, 0)  # rc = 0 means expected
        
        assert service.connected is False


class TestMQTTServiceOnMessage:
    """Test cases for MQTT message handling."""

    def test_on_message_skips_when_vlm_busy(self):
        """Test on_message skips processing when VLM is busy."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        # Create a mock semaphore that is locked
        mock_semaphore = Mock()
        mock_semaphore.locked.return_value = True
        mock_vlm_service.get_vlm_semaphore.return_value = mock_semaphore
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        mock_msg = Mock()
        mock_msg.topic = "scenescape/data/camera/camera1"
        mock_msg.payload = json.dumps({"test": "data"}).encode()
        
        # Should return early without processing
        service._on_message(None, None, mock_msg)
        
        mock_vlm_service.get_vlm_semaphore.assert_called_once()

    def test_on_message_invalid_json(self):
        """Test on_message handles invalid JSON gracefully."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        mock_semaphore = Mock()
        mock_semaphore.locked.return_value = False
        mock_vlm_service.get_vlm_semaphore.return_value = mock_semaphore
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        mock_msg = Mock()
        mock_msg.topic = "scenescape/data/camera/camera1"
        mock_msg.payload = b"invalid json{"
        
        # Should not raise exception
        service._on_message(None, None, mock_msg)

    def test_on_message_camera_data_rate_limited(self):
        """Test on_message applies rate limiting for camera data."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {"rate_limit_seconds": 10.0}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        mock_semaphore = Mock()
        mock_semaphore.locked.return_value = False
        mock_vlm_service.get_vlm_semaphore.return_value = mock_semaphore
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        # Set last processed time to recent
        service.last_processed_time["data_1"] = datetime.now(timezone.utc).timestamp()
        
        mock_msg = Mock()
        mock_msg.topic = "scenescape/data/camera/camera1"
        mock_msg.payload = json.dumps({"test": "data"}).encode()
        
        # Should skip due to rate limiting
        service._on_message(None, None, mock_msg)

    def test_on_message_ignores_unrecognized_topic(self):
        """Test on_message ignores unrecognized topics."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        mock_semaphore = Mock()
        mock_semaphore.locked.return_value = False
        mock_vlm_service.get_vlm_semaphore.return_value = mock_semaphore
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        mock_msg = Mock()
        mock_msg.topic = "some/other/topic"
        mock_msg.payload = json.dumps({"test": "data"}).encode()
        
        # Should not raise exception
        service._on_message(None, None, mock_msg)


class TestMQTTServiceStartStop:
    """Test cases for start and stop methods."""

    @pytest.mark.asyncio
    async def test_stop_sets_shutdown_event(self):
        """Test stop method sets shutdown event."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.client = Mock()
        
        await service.stop()
        
        assert service.shutdown_event.is_set()
        service.client.loop_stop.assert_called_once()
        service.client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_handles_no_client(self):
        """Test stop method handles case when client is None."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.client = None
        
        # Should not raise exception
        await service.stop()
        
        assert service.shutdown_event.is_set()


class TestMQTTServiceHelpers:
    """Test cases for helper methods."""

    def test_is_connected_returns_false_initially(self):
        """Test is_connected returns False initially."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        assert service.is_connected() is False

    def test_is_connected_returns_true_when_connected(self):
        """Test is_connected returns True when connected."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = True
        
        assert service.is_connected() is True

    def test_set_event_loop(self):
        """Test set_event_loop sets the loop reference."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        mock_loop = Mock()
        service.set_event_loop(mock_loop)
        
        assert service.loop == mock_loop

    def test_get_connection_status(self):
        """Test get_connection_status returns correct status."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {
            "host": "mqtt.example.com",
            "port": 8883,
            "use_tls": True,
            "username": "testuser"
        }
        mock_config.get_camera_topics.return_value = ["scenescape/data/camera/camera1"]
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = True
        service.last_processed_time = {"data_1": 12345.0}
        
        status = service.get_connection_status()
        
        assert status["connected"] is True
        assert status["host"] == "mqtt.example.com"
        assert status["port"] == 8883
        assert status["use_tls"] is True
        assert status["has_authentication"] is True
        assert status["subscribed_topics"] == ["scenescape/data/camera/camera1"]
        assert "data_1" in status["cameras_being_tracked"]


class TestMQTTServiceSendGetimageCommands:
    """Test cases for send_getimage_commands method."""

    @pytest.mark.asyncio
    async def test_send_getimage_commands_not_connected(self):
        """Test send_getimage_commands returns False when not connected."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = False
        
        result = await service.send_getimage_commands()
        
        assert result is False

    @pytest.mark.asyncio
    async def test_send_getimage_commands_all_cameras(self):
        """Test send_getimage_commands sends to all cameras."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = True
        
        mock_client = Mock()
        mock_publish_result = Mock()
        mock_publish_result.rc = 0  # MQTT_ERR_SUCCESS
        mock_client.publish.return_value = mock_publish_result
        service.client = mock_client
        
        result = await service.send_getimage_commands()
        
        assert result is True
        assert mock_client.publish.call_count == 4  # 4 cameras

    @pytest.mark.asyncio
    async def test_send_getimage_commands_single_camera(self):
        """Test send_getimage_commands sends to single camera."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = True
        
        mock_client = Mock()
        mock_publish_result = Mock()
        mock_publish_result.rc = 0
        mock_client.publish.return_value = mock_publish_result
        service.client = mock_client
        
        result = await service.send_getimage_commands(camera_number="2")
        
        assert result is True
        mock_client.publish.assert_called_once_with("scenescape/cmd/camera/camera2", "getimage")


class TestMQTTServiceProcessCameraImage:
    """Test cases for _process_camera_image_message method."""

    @pytest.mark.asyncio
    async def test_process_camera_image_success(self):
        """Test successful camera image processing."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_data_aggregator.process_camera_image = AsyncMock()
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        payload = {
            "id": "camera1",
            "image": "base64encodedimagedata",
            "timestamp": "2025-01-01T12:00:00"
        }
        
        await service._process_camera_image_message(
            camera_number="1",
            payload=payload,
            topic="scenescape/image/camera/camera1"
        )
        
        mock_data_aggregator.process_camera_image.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_camera_image_no_image_data(self):
        """Test camera image processing with missing image data."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_data_aggregator.process_camera_image = AsyncMock()
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        payload = {
            "id": "camera1",
            # No image data
        }
        
        await service._process_camera_image_message(
            camera_number="1",
            payload=payload,
            topic="scenescape/image/camera/camera1"
        )
        
        # Should not call process_camera_image
        mock_data_aggregator.process_camera_image.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_camera_image_direction_mapping(self):
        """Test camera image uses correct direction mapping."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_data_aggregator.process_camera_image = AsyncMock()
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        payload = {
            "id": "camera3",
            "image": "base64data"
        }
        
        await service._process_camera_image_message(
            camera_number="3",
            payload=payload,
            topic="scenescape/image/camera/camera3"
        )
        
        # Verify the CameraImage was created with correct direction
        call_args = mock_data_aggregator.process_camera_image.call_args
        camera_image = call_args[0][0]
        assert camera_image.direction == "north"


class TestMQTTServiceProcessCameraData:
    """Test cases for _process_camera_data_message method."""

    @pytest.mark.asyncio
    async def test_process_camera_data_success(self):
        """Test successful camera data processing."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        mock_config.get_intersection_id.return_value = "intersection-123"
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_data_aggregator.process_camera_data = AsyncMock()
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = True
        
        mock_client = Mock()
        mock_publish_result = Mock()
        mock_publish_result.rc = 0
        mock_client.publish.return_value = mock_publish_result
        service.client = mock_client
        
        payload = {
            "id": "camera1",
            "objects": {
                "vehicle": [{"id": 1}, {"id": 2}],
                "pedestrian": [{"id": 3}]
            },
            "timestamp": "2025-01-01T12:00:00"
        }
        
        await service._process_camera_data_message(
            camera_number="1",
            payload=payload,
            topic="scenescape/data/camera/camera1"
        )
        
        mock_data_aggregator.process_camera_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_camera_data_extracts_counts(self):
        """Test camera data extracts vehicle and pedestrian counts."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        mock_config.get_intersection_id.return_value = "intersection-123"
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_data_aggregator.process_camera_data = AsyncMock()
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = True
        
        mock_client = Mock()
        mock_publish_result = Mock()
        mock_publish_result.rc = 0
        mock_client.publish.return_value = mock_publish_result
        service.client = mock_client
        
        payload = {
            "id": "camera2",
            "objects": {
                "vehicle": [{"id": 1}, {"id": 2}, {"id": 3}],
                "pedestrian": [{"id": 4}, {"id": 5}]
            }
        }
        
        await service._process_camera_data_message(
            camera_number="2",
            payload=payload,
            topic="scenescape/data/camera/camera2"
        )
        
        call_args = mock_data_aggregator.process_camera_data.call_args
        camera_message = call_args[0][0]
        assert camera_message.vehicle_count == 3
        assert camera_message.pedestrian_count == 2
        assert camera_message.direction == "west"

    @pytest.mark.asyncio
    async def test_process_camera_data_empty_objects(self):
        """Test camera data handles empty objects."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {}
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        mock_config.get_intersection_id.return_value = "intersection-123"
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_data_aggregator.process_camera_data = AsyncMock()
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        service.connected = True
        
        mock_client = Mock()
        mock_publish_result = Mock()
        mock_publish_result.rc = 0
        mock_client.publish.return_value = mock_publish_result
        service.client = mock_client
        
        payload = {
            "id": "camera4",
            "objects": {}
        }
        
        await service._process_camera_data_message(
            camera_number="4",
            payload=payload,
            topic="scenescape/data/camera/camera4"
        )
        
        call_args = mock_data_aggregator.process_camera_data.call_args
        camera_message = call_args[0][0]
        assert camera_message.vehicle_count == 0
        assert camera_message.pedestrian_count == 0


class TestMQTTServiceTLSConfiguration:
    """Test cases for TLS configuration."""

    @pytest.mark.asyncio
    async def test_initialize_with_tls_cert_required(self):
        """Test initialize configures TLS with certificate verification."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {
            "use_tls": True,
            "cert_required": True,
            "verify_hostname": False,
            "ca_cert_path": "/path/to/ca.pem"
        }
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        with patch('services.mqtt_service.mqtt.Client') as mock_mqtt_client, \
             patch('os.path.exists', return_value=True), \
             patch('ssl.CERT_REQUIRED'), \
             patch('ssl.PROTOCOL_TLS'):
            mock_client_instance = Mock()
            mock_mqtt_client.return_value = mock_client_instance
            
            await service.initialize()
            
            mock_client_instance.tls_set.assert_called_once()
            mock_client_instance.tls_insecure_set.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_initialize_with_tls_missing_cert(self):
        """Test initialize raises error when cert file is missing."""
        mock_config = Mock(spec=ConfigService)
        mock_config.get_mqtt_config.return_value = {
            "use_tls": True,
            "cert_required": True,
            "ca_cert_path": "/nonexistent/ca.pem"
        }
        mock_config.get_camera_topics.return_value = []
        mock_config.get_image_topics.return_value = []
        
        mock_data_aggregator = Mock(spec=DataAggregatorService)
        mock_vlm_service = Mock(spec=VLMService)
        
        service = MQTTService(mock_config, mock_data_aggregator, mock_vlm_service)
        
        with patch('services.mqtt_service.mqtt.Client') as mock_mqtt_client, \
             patch('os.path.exists', return_value=False):
            mock_client_instance = Mock()
            mock_mqtt_client.return_value = mock_client_instance
            
            with pytest.raises(FileNotFoundError):
                await service.initialize()
