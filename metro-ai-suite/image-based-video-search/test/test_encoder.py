# tests/test_encoder.py

import os
import sys
from pathlib import Path
import pytest
import unittest.mock
import base64
import io
from PIL import Image
import tempfile

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

# Import the encoder module directly to avoid loading the server module
import importlib.util
encoder_spec = importlib.util.spec_from_file_location("encoder", src_path / "feature-matching" / "encoder.py")
encoder = importlib.util.module_from_spec(encoder_spec)
encoder_spec.loader.exec_module(encoder)


class TestBase64ImageProcessor:
    """Test cases for Base64ImageProcessor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.processor = encoder.Base64ImageProcessor()
        self.custom_processor = encoder.Base64ImageProcessor(size=(128, 128))
    
    def create_test_image(self, size=(100, 100), mode="RGB", color=(255, 0, 0)):
        """Helper method to create a test image"""
        return Image.new(mode, size, color)
    
    def test_processor_initialization_default_size(self):
        """Test Base64ImageProcessor initialization with default size"""
        processor = encoder.Base64ImageProcessor()
        assert processor.size == (224, 224)
    
    def test_processor_initialization_custom_size(self):
        """Test Base64ImageProcessor initialization with custom size"""
        custom_size = (128, 256)
        processor = encoder.Base64ImageProcessor(size=custom_size)
        assert processor.size == custom_size
    
    def test_process_image_to_base64_basic(self):
        """Test basic image processing to base64"""
        # Create a simple test image
        test_image = self.create_test_image(size=(100, 100), color=(255, 0, 0))
        
        # Process the image
        result = self.processor.process_image_to_base64(test_image)
        
        # Verify the result is a string
        assert isinstance(result, str)
        
        # Verify it's valid base64
        try:
            decoded = base64.b64decode(result)
            assert len(decoded) > 0
        except Exception:
            pytest.fail("Result is not valid base64")
    
    def test_process_image_to_base64_with_custom_size(self):
        """Test image processing with custom processor size"""
        test_image = self.create_test_image(size=(200, 200), color=(0, 255, 0))
        
        # Process with custom processor
        result = self.custom_processor.process_image_to_base64(test_image)
        
        # Verify the result is a string
        assert isinstance(result, str)
        
        # Decode the base64 and verify it's a valid image
        decoded = base64.b64decode(result)
        processed_image = Image.open(io.BytesIO(decoded))
        
        # Verify the image has been resized to the custom size
        assert processed_image.size == (128, 128)
    
    def test_process_image_rgb_conversion(self):
        """Test that images are converted to RGB mode"""
        # Create a grayscale image
        grayscale_image = self.create_test_image(size=(50, 50), mode="L", color=128)
        
        # Process the image
        result = self.processor.process_image_to_base64(grayscale_image)
        
        # Decode and verify the result is RGB
        decoded = base64.b64decode(result)
        processed_image = Image.open(io.BytesIO(decoded))
        
        assert processed_image.mode == "RGB"
        assert processed_image.size == (224, 224)
    
    def test_process_image_rgba_conversion(self):
        """Test that RGBA images are converted to RGB"""
        # Create an RGBA image with transparency
        rgba_image = self.create_test_image(size=(75, 75), mode="RGBA", color=(255, 0, 0, 128))
        
        # Process the image
        result = self.processor.process_image_to_base64(rgba_image)
        
        # Decode and verify the result is RGB
        decoded = base64.b64decode(result)
        processed_image = Image.open(io.BytesIO(decoded))
        
        assert processed_image.mode == "RGB"
        assert processed_image.size == (224, 224)
    
    def test_process_image_resize_functionality(self):
        """Test that images are properly resized"""
        # Test with various input sizes
        test_sizes = [(50, 50), (100, 200), (300, 100), (500, 500)]
        
        for input_size in test_sizes:
            test_image = self.create_test_image(size=input_size, color=(0, 0, 255))
            result = self.processor.process_image_to_base64(test_image)
            
            # Decode and verify size
            decoded = base64.b64decode(result)
            processed_image = Image.open(io.BytesIO(decoded))
            
            assert processed_image.size == (224, 224), f"Failed for input size {input_size}"
    
    def test_process_image_format_output(self):
        """Test that output format is JPEG"""
        test_image = self.create_test_image(size=(100, 100), color=(255, 255, 0))
        result = self.processor.process_image_to_base64(test_image)
        
        # Decode and verify format
        decoded = base64.b64decode(result)
        processed_image = Image.open(io.BytesIO(decoded))
        
        assert processed_image.format == "JPEG"
    
    def test_process_image_deterministic_output(self):
        """Test that the same image produces the same base64 output"""
        test_image = self.create_test_image(size=(100, 100), color=(128, 128, 128))
        
        # Process the same image multiple times
        result1 = self.processor.process_image_to_base64(test_image)
        result2 = self.processor.process_image_to_base64(test_image)
        
        # Results should be identical for the same input
        assert result1 == result2
    
    def test_process_image_different_inputs_different_outputs(self):
        """Test that different images produce different base64 outputs"""
        image1 = self.create_test_image(size=(100, 100), color=(255, 0, 0))
        image2 = self.create_test_image(size=(100, 100), color=(0, 255, 0))
        
        result1 = self.processor.process_image_to_base64(image1)
        result2 = self.processor.process_image_to_base64(image2)
        
        # Different images should produce different outputs
        assert result1 != result2
    
    def test_process_image_with_real_image_file(self):
        """Test processing with a real image file"""
        # Create a temporary image file
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_file:
            temp_image = self.create_test_image(size=(150, 150), color=(100, 150, 200))
            temp_image.save(temp_file.name, "PNG")
            temp_file_path = temp_file.name
        
        try:
            # Load the image from file
            loaded_image = Image.open(temp_file_path)
            
            # Process it
            result = self.processor.process_image_to_base64(loaded_image)
            
            # Verify the result
            assert isinstance(result, str)
            assert len(result) > 0
            
            # Verify it can be decoded back to an image
            decoded = base64.b64decode(result)
            processed_image = Image.open(io.BytesIO(decoded))
            assert processed_image.size == (224, 224)
            assert processed_image.mode == "RGB"
            
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
    
    def test_process_image_lanczos_resampling(self):
        """Test that LANCZOS resampling is used (this is more of a behavior test)"""
        # Create a detailed test image with patterns
        test_image = Image.new("RGB", (100, 100))
        # Create a checkerboard pattern
        for x in range(100):
            for y in range(100):
                if (x // 10 + y // 10) % 2:
                    test_image.putpixel((x, y), (255, 255, 255))
                else:
                    test_image.putpixel((x, y), (0, 0, 0))
        
        # Process the image
        result = self.processor.process_image_to_base64(test_image)
        
        # Verify the result is valid
        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        processed_image = Image.open(io.BytesIO(decoded))
        assert processed_image.size == (224, 224)
    
    def test_process_image_preserves_aspect_ratio_behavior(self):
        """Test the behavior of resize (note: PIL resize doesn't preserve aspect ratio by default)"""
        # Create a rectangular image
        rectangular_image = self.create_test_image(size=(100, 200), color=(255, 128, 0))
        
        # Process it
        result = self.processor.process_image_to_base64(rectangular_image)
        
        # Decode and verify
        decoded = base64.b64decode(result)
        processed_image = Image.open(io.BytesIO(decoded))
        
        # The image should be exactly the target size (aspect ratio not preserved)
        assert processed_image.size == (224, 224)
    
    def test_process_image_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Test with very small image
        tiny_image = self.create_test_image(size=(1, 1), color=(255, 255, 255))
        result = self.processor.process_image_to_base64(tiny_image)
        assert isinstance(result, str)
        
        # Test with square image matching target size
        exact_size_image = self.create_test_image(size=(224, 224), color=(128, 64, 192))
        result = self.processor.process_image_to_base64(exact_size_image)
        assert isinstance(result, str)
        
        # Verify the exact size image
        decoded = base64.b64decode(result)
        processed_image = Image.open(io.BytesIO(decoded))
        assert processed_image.size == (224, 224)
    
    def test_process_image_invalid_input(self):
        """Test error handling for invalid inputs"""
        # Test with None input
        with pytest.raises(AttributeError):
            self.processor.process_image_to_base64(None)
        
        # Test with non-PIL Image object
        with pytest.raises(AttributeError):
            self.processor.process_image_to_base64("not_an_image")
    
    def test_multiple_processors_independence(self):
        """Test that multiple processor instances work independently"""
        processor1 = encoder.Base64ImageProcessor(size=(64, 64))
        processor2 = encoder.Base64ImageProcessor(size=(128, 128))
        
        test_image = self.create_test_image(size=(100, 100), color=(200, 100, 50))
        
        result1 = processor1.process_image_to_base64(test_image)
        result2 = processor2.process_image_to_base64(test_image)
        
        # Results should be different due to different target sizes
        assert result1 != result2
        
        # Verify the actual sizes
        decoded1 = base64.b64decode(result1)
        decoded2 = base64.b64decode(result2)
        
        image1 = Image.open(io.BytesIO(decoded1))
        image2 = Image.open(io.BytesIO(decoded2))
        
        assert image1.size == (64, 64)
        assert image2.size == (128, 128)


class TestBase64ImageProcessorIntegration:
    """Integration tests for Base64ImageProcessor"""
    
    def test_base64_roundtrip_consistency(self):
        """Test that the base64 encoding/decoding roundtrip works correctly"""
        processor = encoder.Base64ImageProcessor(size=(100, 100))
        
        # Create a test image with known properties
        original_image = Image.new("RGB", (50, 50), (123, 234, 45))
        
        # Process to base64
        base64_string = processor.process_image_to_base64(original_image)
        
        # Decode back to image
        decoded_bytes = base64.b64decode(base64_string)
        decoded_image = Image.open(io.BytesIO(decoded_bytes))
        
        # Verify properties
        assert decoded_image.mode == "RGB"
        assert decoded_image.size == (100, 100)
        assert decoded_image.format == "JPEG"
    
    def test_processor_with_various_color_modes(self):
        """Test processor with different PIL image color modes"""
        processor = encoder.Base64ImageProcessor()
        
        # Test different color modes
        modes_and_colors = [
            ("RGB", (255, 128, 64)),
            ("L", 128),  # Grayscale
            ("RGBA", (255, 128, 64, 200)),
            ("P", 5),  # Palette mode
        ]
        
        for mode, color in modes_and_colors:
            if mode == "P":
                # Palette mode requires special handling
                test_image = Image.new("P", (50, 50))
                test_image.putpalette([i % 256 for i in range(768)])  # Simple palette
                test_image.putpixel((25, 25), color)
            else:
                test_image = Image.new(mode, (50, 50), color)
            
            # Process the image
            result = processor.process_image_to_base64(test_image)
            
            # Verify the result
            assert isinstance(result, str)
            
            # Decode and verify it's RGB
            decoded = base64.b64decode(result)
            processed_image = Image.open(io.BytesIO(decoded))
            assert processed_image.mode == "RGB"
            assert processed_image.size == (224, 224)