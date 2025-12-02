# tests/test_server.py

import json
import sys
import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import unittest.mock
from unittest.mock import MagicMock, AsyncMock, patch, mock_open
import io
import base64
from PIL import Image
import tempfile

# Add the src directory to Python path
src_path = Path(__file__).parent.parent / "src" / "feature-matching"
sys.path.insert(0, str(src_path))

# Set up environment variables to avoid connection issues
os.environ.setdefault('MILVUS_ENDPOINT', 'http://localhost:19530')
os.environ.setdefault('MILVUS_TOKEN', 'test_token')
os.environ.setdefault('COLLECTION_NAME', 'test_collection')
os.environ.setdefault('MODEL_DIM', '512')
os.environ.setdefault('MQTT_BROKER', 'localhost')
os.environ.setdefault('MQTT_PORT', '1883')
os.environ.setdefault('MQTT_TOPIC', 'test_topic')
os.environ.setdefault('CONFIDENCE_THRESHOLD', '0.4')

# Import dependencies first
import encoder
import milvus_utils
import schemas

# Mock the Milvus and MQTT clients before importing server to avoid connection errors
mock_milvus_client_instance = unittest.mock.MagicMock()
mock_mqtt_client_instance = unittest.mock.MagicMock()

with unittest.mock.patch('milvus_utils.get_milvus_client', return_value=mock_milvus_client_instance), \
     unittest.mock.patch('paho.mqtt.client.Client', return_value=mock_mqtt_client_instance), \
     unittest.mock.patch('milvus_utils.create_collection'):
    import server


@pytest.fixture
def client():
    """FastAPI test client fixture"""
    return TestClient(server.app)


@pytest.fixture
def mock_image():
    """Create a mock image for testing"""
    img = Image.new('RGB', (100, 100), color='red')
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='JPEG')
    img_bytes.seek(0)
    return img_bytes.getvalue()


@pytest.fixture
def mock_base64_image():
    """Create a base64 encoded image for testing"""
    img = Image.new('RGB', (224, 224), color='blue')
    buffered = io.BytesIO()
    img.save(buffered, format='JPEG')
    buffered.seek(0)
    return base64.b64encode(buffered.read()).decode('utf-8')


class TestHealthEndpoint:
    """Tests for the health check endpoint"""
    
    def test_health_endpoint_success(self, client):
        """Test health endpoint returns correct status"""
        resp = client.get('/healthz')
        assert resp.status_code == 200
        data = resp.json()
        assert data == {'status': 'ok'}
    
    def test_health_endpoint_method_not_allowed(self, client):
        """Test health endpoint with wrong HTTP method"""
        resp = client.post('/healthz')
        assert resp.status_code == 405  # Method Not Allowed


class TestSearchEndpoint:
    """Tests for the search endpoint"""
    
    def test_search_endpoint_missing_files(self, client):
        """Test search endpoint without files"""
        resp = client.post('/search/')
        assert resp.status_code == 422  # FastAPI returns 422 for missing required fields
    
    @patch('httpx.AsyncClient')
    def test_search_endpoint_with_running_pipeline(self, mock_httpx, client, mock_image):
        """Test search when pipeline is already running"""
        # Mock pipeline status response
        mock_status_response = MagicMock()
        mock_status_response.json.return_value = [
            {
                "id": "pipeline123",
                "state": "RUNNING"
            }
        ]
        mock_status_response.raise_for_status = MagicMock()
        
        # Mock pipeline details response
        mock_details_response = MagicMock()
        mock_details_response.json.return_value = {
            "request": {
                "pipeline": {
                    "version": "search_image"
                }
            }
        }
        mock_details_response.raise_for_status = MagicMock()
        
        # Mock second pipeline response
        mock_second_response = MagicMock()
        mock_second_response.json.return_value = json.dumps({
            "metadata": {
                "objects": [
                    {
                        "tensors": [
                            {
                                "layer_name": "prob",
                                "data": [0.1] * 512
                            }
                        ]
                    }
                ]
            }
        })
        mock_second_response.raise_for_status = MagicMock()
        
        # Configure the mock client
        mock_client_instance = AsyncMock()
        mock_client_instance.get.side_effect = [mock_status_response, mock_details_response]
        mock_client_instance.post.return_value = mock_second_response
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        # Mock milvus search results
        with patch.object(server, 'get_search_results') as mock_search:
            mock_search.return_value = [
                {"filename": "test.jpg", "label": "person", "timestamp": 123456}
            ]
            
            resp = client.post('/search/', files={"images": ("test.jpg", mock_image, "image/jpeg")})
            
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
    
    @patch('httpx.AsyncClient')
    def test_search_endpoint_start_new_pipeline(self, mock_httpx, client, mock_image):
        """Test search when no pipeline is running and needs to start new one"""
        # Mock empty pipeline status
        mock_status_response = MagicMock()
        mock_status_response.json.return_value = []
        mock_status_response.raise_for_status = MagicMock()
        
        # Mock pipeline creation response
        mock_create_response = MagicMock()
        mock_create_response.text = '"pipeline456"'
        mock_create_response.raise_for_status = MagicMock()
        
        # Mock second pipeline response
        mock_second_response = MagicMock()
        mock_second_response.json.return_value = json.dumps({
            "metadata": {
                "objects": [
                    {
                        "tensors": [
                            {
                                "layer_name": "prob",
                                "data": [0.2] * 512
                            }
                        ]
                    }
                ]
            }
        })
        mock_second_response.raise_for_status = MagicMock()
        
        # Configure mock client
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_status_response
        mock_client_instance.post.side_effect = [mock_create_response, mock_second_response]
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        with patch.object(server, 'get_search_results') as mock_search:
            mock_search.return_value = []
            
            resp = client.post('/search/', files={"images": ("test.jpg", mock_image, "image/jpeg")})
            
            assert resp.status_code == 200
    
    @patch('httpx.AsyncClient')
    def test_search_endpoint_pipeline_error(self, mock_httpx, client, mock_image):
        """Test search when pipeline request fails"""
        import httpx
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.side_effect = httpx.RequestError("Connection failed")
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        # Mock successful pipeline creation
        mock_create_response = MagicMock()
        mock_create_response.text = '"pipeline789"'
        mock_create_response.raise_for_status = MagicMock()
        
        mock_second_response = MagicMock()
        mock_second_response.json.return_value = json.dumps({
            "metadata": {
                "objects": [
                    {
                        "tensors": [
                            {
                                "layer_name": "prob",
                                "data": [0.3] * 512
                            }
                        ]
                    }
                ]
            }
        })
        mock_second_response.raise_for_status = MagicMock()
        
        # Reconfigure for post requests
        mock_client_instance.post.side_effect = [mock_create_response, mock_second_response]
        
        with patch.object(server, 'get_search_results') as mock_search:
            mock_search.return_value = []
            
            resp = client.post('/search/', files={"images": ("test.jpg", mock_image, "image/jpeg")})
            
            # Should still process despite initial error
            assert resp.status_code == 200
    
    @patch('httpx.AsyncClient')
    def test_search_endpoint_second_pipeline_error(self, mock_httpx, client, mock_image):
        """Test search when second pipeline request fails"""
        import httpx
        
        # Mock successful first calls
        mock_status_response = MagicMock()
        mock_status_response.json.return_value = []
        mock_status_response.raise_for_status = MagicMock()
        
        mock_create_response = MagicMock()
        mock_create_response.text = '"pipeline999"'
        mock_create_response.raise_for_status = MagicMock()
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_status_response
        mock_client_instance.post.side_effect = [
            mock_create_response,
            httpx.RequestError("Second pipeline failed")
        ]
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        resp = client.post('/search/', files={"images": ("test.jpg", mock_image, "image/jpeg")})
        
        assert resp.status_code == 200
        assert "error" in resp.json()
    
    @patch('httpx.AsyncClient')
    def test_search_endpoint_search_failure(self, mock_httpx, client, mock_image):
        """Test search when milvus search fails"""
        # Setup successful pipeline mocks
        mock_status_response = MagicMock()
        mock_status_response.json.return_value = []
        mock_status_response.raise_for_status = MagicMock()
        
        mock_create_response = MagicMock()
        mock_create_response.text = '"pipeline111"'
        mock_create_response.raise_for_status = MagicMock()
        
        mock_second_response = MagicMock()
        mock_second_response.json.return_value = json.dumps({
            "metadata": {
                "objects": [
                    {
                        "tensors": [
                            {
                                "layer_name": "prob",
                                "data": [0.4] * 512
                            }
                        ]
                    }
                ]
            }
        })
        mock_second_response.raise_for_status = MagicMock()
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get.return_value = mock_status_response
        mock_client_instance.post.side_effect = [mock_create_response, mock_second_response]
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        # Make search fail
        with patch.object(server, 'get_search_results') as mock_search:
            mock_search.side_effect = Exception("Milvus connection error")
            
            resp = client.post('/search/', files={"images": ("test.jpg", mock_image, "image/jpeg")})
            
            assert resp.status_code == 200
            assert "error" in resp.json()
            assert resp.json()["error"] == "Search failed"


class TestClearEndpoint:
    """Tests for the clear endpoint"""
    
    @patch('os.listdir')
    @patch('os.remove')
    def test_clear_endpoint_success(self, mock_remove, mock_listdir, client):
        """Test successful clear operation"""
        mock_listdir.return_value = ['file1.jpg', 'file2.jpg']
        
        with patch.object(server, 'create_collection') as mock_create:
            resp = client.post('/clear/')
            
            assert resp.status_code == 200
            assert resp.json() == {"message": "Success"}
            mock_create.assert_called_once()
            assert mock_remove.call_count == 2
    
    @patch('os.listdir')
    @patch('os.remove')
    def test_clear_endpoint_empty_directory(self, mock_remove, mock_listdir, client):
        """Test clear when static directory is empty"""
        mock_listdir.return_value = []
        
        with patch.object(server, 'create_collection') as mock_create:
            resp = client.post('/clear/')
            
            assert resp.status_code == 200
            assert mock_remove.call_count == 0
    
    @patch('os.listdir')
    def test_clear_endpoint_collection_error(self, mock_listdir, client):
        """Test clear when collection creation fails"""
        mock_listdir.return_value = []
        
        with patch.object(server, 'create_collection') as mock_create:
            mock_create.side_effect = Exception("Milvus error")
            
            # Should raise exception
            with pytest.raises(Exception):
                resp = client.post('/clear/')


class TestGetImageEndpoint:
    """Tests for the static file serving endpoint"""
    
    def test_get_image_file_exists(self, client, tmp_path):
        """Test serving existing static file"""
        # Create a temporary file
        static_dir = tmp_path / "static"
        static_dir.mkdir()
        test_file = static_dir / "test_image.jpg"
        test_file.write_text("fake image content")
        
        with patch('os.path.exists', return_value=True), \
             patch('os.path.abspath', return_value=str(static_dir)), \
             patch('fastapi.responses.FileResponse') as mock_file_response:
            
            mock_file_response.return_value = MagicMock()
            resp = client.get('/static/test_image.jpg')
            
            # FileResponse is created directly, so we check the path
            assert resp.status_code == 200
    
    def test_get_image_file_not_found(self, client):
        """Test serving non-existent file"""
        with patch('os.path.exists', return_value=False), \
             patch('os.path.abspath', return_value='/fake/path/static'):
            resp = client.get('/static/nonexistent.jpg')
            
            assert resp.status_code == 404
            assert resp.json() == {"message": "File not found"}
    
    def test_get_image_path_traversal_attempt(self, client):
        """Test that path traversal attacks are prevented"""
        with patch('os.path.abspath', side_effect=lambda x: '/fake/path/static' if 'static' in x else '/fake/path'), \
             patch('os.path.normpath', side_effect=lambda x: x):
            
            # Attempt path traversal
            resp = client.get('/static/../../../etc/passwd')
            
            # Should return 404 or handle safely
            assert resp.status_code in [404, 400]


class TestMQTTCallbacks:
    """Tests for MQTT callback functions"""
    
    def test_on_connect_callback(self):
        """Test MQTT on_connect callback"""
        mock_client = MagicMock()
        server.on_connect(mock_client, None, None, 0)
        
        mock_client.subscribe.assert_called_once_with(server.MQTT_TOPIC)
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.makedirs')
    def test_on_message_valid_payload(self, mock_makedirs, mock_file):
        """Test MQTT on_message with valid payload"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        
        # Create a valid payload
        img = Image.new('RGB', (100, 100), color='green')
        buffered = io.BytesIO()
        img.save(buffered, format='JPEG')
        buffered.seek(0)
        img_base64 = base64.b64encode(buffered.read()).decode('utf-8')
        
        payload = {
            "metadata": {
                "time": 1234567890,
                "objects": [
                    {
                        "detection": {
                            "label": "person",
                            "confidence": 0.95
                        },
                        "tensors": [
                            {
                                "layer_name": "prob",
                                "data": [0.5] * 512
                            }
                        ]
                    }
                ]
            },
            "blob": img_base64
        }
        
        mock_message.payload.decode.return_value = json.dumps(payload)
        
        with patch.object(server.milvus_client, 'insert') as mock_insert:
            server.on_message(mock_client, None, mock_message)
            
            # Verify insert was called
            mock_insert.assert_called_once()
    
    def test_on_message_low_confidence(self):
        """Test MQTT on_message with low confidence detection"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        
        # Create payload with low confidence
        img = Image.new('RGB', (100, 100), color='blue')
        buffered = io.BytesIO()
        img.save(buffered, format='JPEG')
        buffered.seek(0)
        img_base64 = base64.b64encode(buffered.read()).decode('utf-8')
        
        payload = {
            "metadata": {
                "time": 1234567890,
                "objects": [
                    {
                        "detection": {
                            "label": "car",
                            "confidence": 0.2  # Below threshold
                        },
                        "tensors": [
                            {
                                "layer_name": "prob",
                                "data": [0.3] * 512
                            }
                        ]
                    }
                ]
            },
            "blob": img_base64
        }
        
        mock_message.payload.decode.return_value = json.dumps(payload)
        
        with patch.object(server.milvus_client, 'insert') as mock_insert:
            server.on_message(mock_client, None, mock_message)
            
            # Should not insert due to low confidence
            mock_insert.assert_not_called()
    
    def test_on_message_invalid_payload(self):
        """Test MQTT on_message with invalid payload"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        
        # Invalid payload (missing required fields)
        payload = {"invalid": "data"}
        mock_message.payload.decode.return_value = json.dumps(payload)
        
        # Should handle gracefully without crashing
        server.on_message(mock_client, None, mock_message)
    
    def test_on_message_no_blob(self):
        """Test MQTT on_message without blob field"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        
        payload = {
            "metadata": {
                "time": 1234567890,
                "objects": []
            }
        }
        
        mock_message.payload.decode.return_value = json.dumps(payload)
        
        # Should handle gracefully
        server.on_message(mock_client, None, mock_message)
    
    def test_on_message_non_prob_tensor(self):
        """Test MQTT on_message with tensor that is not 'prob' layer"""
        mock_client = MagicMock()
        mock_message = MagicMock()
        
        img = Image.new('RGB', (100, 100), color='yellow')
        buffered = io.BytesIO()
        img.save(buffered, format='JPEG')
        buffered.seek(0)
        img_base64 = base64.b64encode(buffered.read()).decode('utf-8')
        
        payload = {
            "metadata": {
                "time": 1234567890,
                "objects": [
                    {
                        "detection": {
                            "label": "dog",
                            "confidence": 0.85
                        },
                        "tensors": [
                            {
                                "layer_name": "features",  # Not "prob"
                                "data": [0.6] * 512
                            }
                        ]
                    }
                ]
            },
            "blob": img_base64
        }
        
        mock_message.payload.decode.return_value = json.dumps(payload)
        
        with patch.object(server.milvus_client, 'insert') as mock_insert:
            server.on_message(mock_client, None, mock_message)
            
            # Should not insert non-prob tensors
            mock_insert.assert_not_called()