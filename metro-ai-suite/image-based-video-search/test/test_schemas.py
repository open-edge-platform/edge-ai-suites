# tests/test_schemas.py

import os
import sys
from pathlib import Path
import pytest
import unittest.mock
from marshmallow import ValidationError

# Add the src directory to Python path
src_path = Path(__file__).parent.parent / "src"
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

# Import the schemas module directly to avoid loading the server module
import importlib.util
schemas_spec = importlib.util.spec_from_file_location("schemas", src_path / "feature-matching" / "schemas.py")
schemas = importlib.util.module_from_spec(schemas_spec)
schemas_spec.loader.exec_module(schemas)


class TestTensorSchema:
    """Test cases for TensorSchema"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.schema = schemas.TensorSchema()
    
    def test_tensor_schema_valid_complete_data(self):
        """Test TensorSchema with all valid fields"""
        valid_data = {
            "data": [1.0, 2.5, 3.7, 4.2],
            "layer_name": "conv1",
            "dims": [1, 3, 224, 224],
            "model_name": "resnet50",
            "name": "feature_tensor",
            "precision": "FP32",
            "layout": "NCHW",
            "label_id": 5,
            "confidence": 0.85
        }
        
        result = self.schema.load(valid_data)
        assert result == valid_data
    
    def test_tensor_schema_minimal_data(self):
        """Test TensorSchema with minimal data (all fields are optional)"""
        minimal_data = {}
        result = self.schema.load(minimal_data)
        assert result == minimal_data
    
    def test_tensor_schema_partial_data(self):
        """Test TensorSchema with partial data"""
        partial_data = {
            "data": [1.0, 2.0, 3.0],
            "layer_name": "prob",
            "confidence": 0.92
        }
        
        result = self.schema.load(partial_data)
        assert result == partial_data
    
    def test_tensor_schema_invalid_data_types(self):
        """Test TensorSchema with invalid data types"""
        # Invalid data field (should be list of floats)
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load({"data": "invalid_string"})
        assert "data" in str(exc_info.value)
        
        # Invalid dims field (should be list of ints) - test with non-numeric values
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load({"dims": ["invalid", "string"]})
        assert "dims" in str(exc_info.value)
        
        # Invalid confidence field (should be float) - test with non-numeric string
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load({"confidence": "high"})
        assert "confidence" in str(exc_info.value)
        
        # Invalid label_id field (should be int) - test with non-numeric string
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load({"label_id": "invalid_id"})
        assert "label_id" in str(exc_info.value)
    
    def test_tensor_schema_empty_lists(self):
        """Test TensorSchema with empty lists"""
        data_with_empty_lists = {
            "data": [],
            "dims": []
        }
        
        result = self.schema.load(data_with_empty_lists)
        assert result == data_with_empty_lists
    
    def test_tensor_schema_dump(self):
        """Test TensorSchema dump (serialization)"""
        data = {
            "data": [1.0, 2.0, 3.0],
            "layer_name": "conv2d",
            "confidence": 0.95
        }
        
        dumped = self.schema.dump(data)
        assert dumped == data
    
    def test_tensor_schema_type_coercion(self):
        """Test TensorSchema automatic type coercion behavior"""
        # Marshmallow automatically converts compatible types
        data_with_coercible_types = {
            "dims": [1.0, 2.0, 3.0],  # floats -> ints
            "label_id": 5.0,  # float -> int
            "confidence": "0.95"  # string -> float (if valid number)
        }
        
        result = self.schema.load(data_with_coercible_types)
        
        # Verify the types were coerced
        assert result["dims"] == [1, 2, 3]
        assert result["label_id"] == 5
        assert result["confidence"] == 0.95


class TestMetadataSchema:
    """Test cases for MetadataSchema"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.schema = schemas.MetadataSchema()
    
    def test_metadata_schema_valid_minimal_data(self):
        """Test MetadataSchema with minimal required data"""
        minimal_data = {
            "time": 1633536000
        }
        
        result = self.schema.load(minimal_data)
        assert result == minimal_data
    
    def test_metadata_schema_valid_complete_data(self):
        """Test MetadataSchema with all fields"""
        complete_data = {
            "time": 1633536000,
            "objects": [{"detection": {"label": "person", "confidence": 0.9}}],
            "caps": "video/x-raw",
            "frame_id": 123,
            "width": 1920,
            "height": 1080,
            "encoding_level": 3,
            "pipeline": {"name": "object_detection", "version": "1.0"},
            "encoding_type": "h264",
            "img_format": "BGR",
            "gva_meta": [{"key": "value"}],
            "img_handle": "frame_123",
            "channels": 3,
            "resolution": {"width": 1920, "height": 1080},
            "tags": {"source": "camera1"},
            "timestamp": 1633536000
        }
        
        result = self.schema.load(complete_data)
        assert result == complete_data
    
    def test_metadata_schema_missing_required_time(self):
        """Test MetadataSchema without required 'time' field"""
        data_without_time = {
            "frame_id": 123,
            "width": 1920
        }
        
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load(data_without_time)
        assert "time" in str(exc_info.value)
    
    def test_metadata_schema_invalid_types(self):
        """Test MetadataSchema with invalid field types"""
        # Invalid time (should be int) - test with non-numeric string
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load({"time": "invalid_time"})
        assert "time" in str(exc_info.value)
        
        # Invalid width (should be int) - test with non-numeric string
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load({"time": 1633536000, "width": "invalid_width"})
        assert "width" in str(exc_info.value)
        
        # Invalid objects (should be list)
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load({"time": 1633536000, "objects": "invalid"})
        assert "objects" in str(exc_info.value)
    
    def test_metadata_schema_empty_objects_list(self):
        """Test MetadataSchema with empty objects list"""
        data_with_empty_objects = {
            "time": 1633536000,
            "objects": []
        }
        
        result = self.schema.load(data_with_empty_objects)
        assert result == data_with_empty_objects
    
    def test_metadata_schema_complex_objects(self):
        """Test MetadataSchema with complex objects"""
        data_with_complex_objects = {
            "time": 1633536000,
            "objects": [
                {
                    "detection": {
                        "label": "person",
                        "confidence": 0.95,
                        "bbox": [100, 200, 300, 400]
                    },
                    "tensors": [
                        {
                            "data": [1.0, 2.0, 3.0],
                            "layer_name": "prob"
                        }
                    ]
                }
            ]
        }
        
        result = self.schema.load(data_with_complex_objects)
        assert result == data_with_complex_objects


class TestPayloadSchema:
    """Test cases for PayloadSchema"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.schema = schemas.PayloadSchema()
    
    def test_payload_schema_valid_minimal_data(self):
        """Test PayloadSchema with minimal required data"""
        minimal_data = {
            "metadata": {
                "time": 1633536000
            }
        }
        
        result = self.schema.load(minimal_data)
        assert result == minimal_data
    
    def test_payload_schema_valid_complete_data(self):
        """Test PayloadSchema with metadata and blob"""
        complete_data = {
            "metadata": {
                "time": 1633536000,
                "frame_id": 123,
                "width": 1920,
                "height": 1080,
                "objects": [
                    {
                        "detection": {"label": "car", "confidence": 0.88},
                        "tensors": [{"data": [0.1, 0.2, 0.3], "layer_name": "conv1"}]
                    }
                ]
            },
            "blob": "base64encodedimagedata=="
        }
        
        result = self.schema.load(complete_data)
        assert result == complete_data
    
    def test_payload_schema_missing_required_metadata(self):
        """Test PayloadSchema without required metadata field"""
        data_without_metadata = {
            "blob": "some_blob_data"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load(data_without_metadata)
        assert "metadata" in str(exc_info.value)
    
    def test_payload_schema_invalid_metadata(self):
        """Test PayloadSchema with invalid metadata structure"""
        # Missing required 'time' in metadata
        data_with_invalid_metadata = {
            "metadata": {
                "frame_id": 123
                # Missing required 'time' field
            }
        }
        
        with pytest.raises(ValidationError) as exc_info:
            self.schema.load(data_with_invalid_metadata)
        assert "time" in str(exc_info.value)
    
    def test_payload_schema_blob_optional(self):
        """Test PayloadSchema with metadata only (blob is optional)"""
        data_without_blob = {
            "metadata": {
                "time": 1633536000,
                "frame_id": 456
            }
        }
        
        result = self.schema.load(data_without_blob)
        assert result == data_without_blob
    
    def test_payload_schema_nested_validation(self):
        """Test PayloadSchema with nested schema validation"""
        # Valid nested structure
        valid_nested_data = {
            "metadata": {
                "time": 1633536000,
                "objects": [
                    {
                        "detection": {
                            "label": "person",
                            "confidence": 0.9
                        },
                        "tensors": [
                            {
                                "data": [1.0, 2.0, 3.0],
                                "layer_name": "prob",
                                "confidence": 0.95
                            }
                        ]
                    }
                ]
            },
            "blob": "imagedata"
        }
        
        result = self.schema.load(valid_nested_data)
        assert result == valid_nested_data
    
    def test_payload_schema_dump(self):
        """Test PayloadSchema dump (serialization)"""
        data = {
            "metadata": {
                "time": 1633536000,
                "frame_id": 789
            },
            "blob": "encoded_image"
        }
        
        dumped = self.schema.dump(data)
        assert dumped == data


class TestSchemaIntegration:
    """Integration tests for all schemas working together"""
    
    def test_realistic_payload_example(self):
        """Test with a realistic payload example"""
        realistic_payload = {
            "metadata": {
                "time": 1633536000,
                "frame_id": 42,
                "width": 1920,
                "height": 1080,
                "channels": 3,
                "encoding_type": "h264",
                "objects": [
                    {
                        "detection": {
                            "label": "person",
                            "confidence": 0.95,
                            "bbox": [100, 200, 300, 400]
                        },
                        "tensors": [
                            {
                                "data": [0.1, 0.2, 0.8, 0.9, 0.3],
                                "layer_name": "prob",
                                "dims": [1, 5],
                                "model_name": "object_classifier",
                                "precision": "FP32",
                                "confidence": 0.95
                            },
                            {
                                "data": [1.2, 3.4, 5.6, 7.8],
                                "layer_name": "features",
                                "dims": [1, 4],
                                "model_name": "feature_extractor"
                            }
                        ]
                    },
                    {
                        "detection": {
                            "label": "car",
                            "confidence": 0.88
                        },
                        "tensors": [
                            {
                                "data": [0.2, 0.1, 0.7],
                                "layer_name": "prob",
                                "confidence": 0.88
                            }
                        ]
                    }
                ]
            },
            "blob": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
        }
        
        payload_schema = schemas.PayloadSchema()
        result = payload_schema.load(realistic_payload)
        
        # Verify the structure is preserved
        assert result["metadata"]["time"] == 1633536000
        assert len(result["metadata"]["objects"]) == 2
        assert result["metadata"]["objects"][0]["detection"]["label"] == "person"
        assert len(result["metadata"]["objects"][0]["tensors"]) == 2
        assert result["blob"] == realistic_payload["blob"]
    
    def test_schema_error_handling(self):
        """Test comprehensive error handling across schemas"""
        payload_schema = schemas.PayloadSchema()
        
        # Test multiple validation errors
        invalid_payload = {
            "metadata": {
                "time": "invalid_time",  # Should be int
                "width": "invalid_width",  # Should be int
                "objects": "invalid_objects"  # Should be list
            }
        }
        
        with pytest.raises(ValidationError) as exc_info:
            payload_schema.load(invalid_payload)
        
        error_messages = str(exc_info.value)
        assert "time" in error_messages
        assert "width" in error_messages
        assert "objects" in error_messages