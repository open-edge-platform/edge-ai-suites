"""
Unit tests for Preprocessor module.

Run with: pytest tests/test_preprocessor.py -v
"""

import pytest
import numpy as np
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from preprocessor import Preprocessor, PreprocessorError


class TestPreprocessorInitialization:
    """Test Preprocessor initialization."""
    
    def test_creates_with_defaults(self):
        """Test default initialization."""
        preprocessor = Preprocessor()
        
        assert preprocessor.crop_top == 0.1
        assert preprocessor.crop_left == 0.3
        assert preprocessor.crop_bottom == 0.56
        assert preprocessor.crop_right == 0.7
        assert preprocessor.image_size == 36
        assert preprocessor.batch_size == 10
        assert len(preprocessor.frame_buffer) == 0
        assert preprocessor.previous_frame is None
    
    def test_creates_with_custom_params(self):
        """Test custom initialization."""
        preprocessor = Preprocessor(
            crop_top=0.2,
            crop_left=0.4,
            image_size=48,
            batch_size=5
        )
        
        assert preprocessor.crop_top == 0.2
        assert preprocessor.crop_left == 0.4
        assert preprocessor.image_size == 48
        assert preprocessor.batch_size == 5


class TestROIExtraction:
    """Test ROI extraction functionality."""
    
    def test_extracts_roi_correctly(self):
        """Test ROI extraction with known dimensions."""
        preprocessor = Preprocessor()
        
        # Create test frame (480x640 RGB)
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        roi = preprocessor._extract_roi(frame)
        
        # Expected ROI size
        # Height: 480 * (0.56 - 0.1) = 220.8 → 221 pixels
        # Width: 640 * (0.7 - 0.3) = 256 pixels
        expected_height = int(480 * (0.56 - 0.1))
        expected_width = int(640 * (0.7 - 0.3))
        
        assert roi.shape[0] == expected_height
        assert roi.shape[1] == expected_width
        assert roi.shape[2] == 3  # RGB channels
    
    def test_roi_preserves_dtype(self):
        """Test ROI maintains uint8 dtype."""
        preprocessor = Preprocessor()
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        roi = preprocessor._extract_roi(frame)
        
        assert roi.dtype == np.uint8


class TestFrameResizing:
    """Test frame resizing functionality."""
    
    def test_resizes_to_correct_dimensions(self):
        """Test resize produces correct output shape."""
        preprocessor = Preprocessor(image_size=36)
        
        # Create various input sizes
        frame_sizes = [(100, 100, 3), (200, 300, 3), (480, 640, 3)]
        
        for frame_size in frame_sizes:
            frame = np.random.randint(0, 255, frame_size, dtype=np.uint8)
            resized = preprocessor._resize_frame(frame)
            
            assert resized.shape == (36, 36, 3)
            assert resized.dtype == np.uint8
    
    def test_resize_with_custom_size(self):
        """Test resize with non-default size."""
        preprocessor = Preprocessor(image_size=64)
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        resized = preprocessor._resize_frame(frame)
        
        assert resized.shape == (64, 64, 3)


class TestFrameNormalization:
    """Test frame normalization."""
    
    def test_normalizes_to_zero_one_range(self):
        """Test normalization produces [0, 1] range."""
        preprocessor = Preprocessor()
        
        # Create frame with known values
        frame = np.array([[[0, 128, 255]]], dtype=np.uint8)
        
        normalized = preprocessor._normalize_frame(frame)
        
        assert normalized.dtype == np.float32
        assert normalized.min() >= 0.0
        assert normalized.max() <= 1.0
        
        # Check specific values
        np.testing.assert_almost_equal(normalized[0, 0, 0], 0.0, decimal=5)
        np.testing.assert_almost_equal(normalized[0, 0, 1], 128/255, decimal=5)
        np.testing.assert_almost_equal(normalized[0, 0, 2], 1.0, decimal=5)


class TestFrameDifferencing:
    """Test frame differencing."""
    
    def test_computes_difference_correctly(self):
        """Test frame difference computation."""
        preprocessor = Preprocessor()
        
        # Create two frames with known difference
        frame1 = np.ones((36, 36, 3), dtype=np.float32) * 0.5
        frame2 = np.ones((36, 36, 3), dtype=np.float32) * 0.7
        
        diff = preprocessor._compute_difference(frame2, frame1)
        
        # Difference should be 0.2 everywhere
        expected_diff = 0.2
        np.testing.assert_almost_equal(diff, expected_diff, decimal=5)
    
    def test_difference_range(self):
        """Test difference is in valid range."""
        preprocessor = Preprocessor()
        
        frame1 = np.random.rand(36, 36, 3).astype(np.float32)
        frame2 = np.random.rand(36, 36, 3).astype(np.float32)
        
        diff = preprocessor._compute_difference(frame2, frame1)
        
        # Difference should be in [-1, 1] range
        assert diff.min() >= -1.0
        assert diff.max() <= 1.0


class TestSingleFramePreprocessing:
    """Test complete single frame preprocessing."""
    
    def test_preprocess_frame_output_shapes(self):
        """Test preprocess_frame returns correct shapes."""
        preprocessor = Preprocessor()
        
        # Create test frame
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        diff, app = preprocessor.preprocess_frame(frame)
        
        # Both outputs should be (36, 36, 3) float32
        assert diff.shape == (36, 36, 3)
        assert app.shape == (36, 36, 3)
        assert diff.dtype == np.float32
        assert app.dtype == np.float32
    
    def test_first_frame_difference_is_zero(self):
        """Test first frame has zero difference."""
        preprocessor = Preprocessor()
        
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        
        diff, app = preprocessor.preprocess_frame(frame)
        
        # First frame difference should be all zeros
        np.testing.assert_array_equal(diff, np.zeros((36, 36, 3)))
    
    def test_second_frame_has_nonzero_difference(self):
        """Test second frame has non-zero difference."""
        preprocessor = Preprocessor()
        
        # Process first frame
        frame1 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        preprocessor.preprocess_frame(frame1)
        
        # Process second frame (different from first)
        frame2 = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        diff, app = preprocessor.preprocess_frame(frame2)
        
        # Should have some non-zero differences
        assert not np.allclose(diff, 0.0)


class TestBatchFormation:
    """Test batch formation and buffer management."""
    
    def test_buffer_fills_correctly(self):
        """Test frame buffer fills up to batch_size."""
        preprocessor = Preprocessor(batch_size=10)
        
        # Add frames one by one
        for i in range(10):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            preprocessor.add_frame(frame)
            
            if i < 9:
                assert not preprocessor.has_batch()
            else:
                assert preprocessor.has_batch()
    
    def test_get_batch_returns_correct_shapes(self):
        """Test get_batch returns correctly shaped tensors."""
        preprocessor = Preprocessor(batch_size=10)
        
        # Add 10 frames
        for _ in range(10):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            preprocessor.add_frame(frame)
        
        diff_batch, app_batch = preprocessor.get_batch()
        
        # Should be (10, 36, 36, 3)
        assert diff_batch.shape == (10, 36, 36, 3)
        assert app_batch.shape == (10, 36, 36, 3)
        assert diff_batch.dtype == np.float32
        assert app_batch.dtype == np.float32
    
    def test_get_batch_clears_buffer(self):
        """Test buffer is cleared after get_batch()."""
        preprocessor = Preprocessor(batch_size=10)
        
        # Fill buffer
        for _ in range(10):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            preprocessor.add_frame(frame)
        
        # Get batch
        preprocessor.get_batch()
        
        # Buffer should be empty
        assert len(preprocessor.frame_buffer) == 0
        assert not preprocessor.has_batch()
    
    def test_get_batch_raises_if_not_ready(self):
        """Test get_batch raises error if batch not ready."""
        preprocessor = Preprocessor(batch_size=10)
        
        # Add only 5 frames
        for _ in range(5):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            preprocessor.add_frame(frame)
        
        with pytest.raises(ValueError):
            preprocessor.get_batch()
    
    def test_multiple_batches_sequential(self):
        """Test can create multiple batches sequentially."""
        preprocessor = Preprocessor(batch_size=10)
        
        # Create 3 batches
        for batch_num in range(3):
            # Add 10 frames
            for _ in range(10):
                frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
                preprocessor.add_frame(frame)
            
            # Get batch
            diff_batch, app_batch = preprocessor.get_batch()
            
            assert diff_batch.shape == (10, 36, 36, 3)
            assert preprocessor.batches_formed == batch_num + 1


class TestPreprocessorReset:
    """Test preprocessor reset functionality."""
    
    def test_reset_clears_state(self):
        """Test reset clears all state."""
        preprocessor = Preprocessor()
        
        # Add some frames
        for _ in range(5):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            preprocessor.add_frame(frame)
        
        # Reset
        preprocessor.reset()
        
        assert len(preprocessor.frame_buffer) == 0
        assert preprocessor.previous_frame is None
        assert preprocessor.frames_processed == 0
        assert preprocessor.batches_formed == 0


class TestPreprocessorStatistics:
    """Test statistics tracking."""
    
    def test_stats_track_correctly(self):
        """Test get_stats returns accurate info."""
        preprocessor = Preprocessor(batch_size=10)
        
        # Add 5 frames
        for _ in range(5):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            preprocessor.add_frame(frame)
        
        stats = preprocessor.get_stats()
        
        assert stats['frames_processed'] == 5
        assert stats['batches_formed'] == 0
        assert stats['buffer_size'] == 5
        assert stats['is_batch_ready'] == False
        
        # Add 5 more frames to complete batch
        for _ in range(5):
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            preprocessor.add_frame(frame)
        
        stats = preprocessor.get_stats()
        assert stats['is_batch_ready'] == True


class TestEndToEndPreprocessing:
    """Test complete preprocessing workflow."""
    
    def test_full_pipeline(self):
        """Test complete preprocessing pipeline."""
        preprocessor = Preprocessor(batch_size=10)
        
        # Simulate video processing
        num_frames = 30
        
        for i in range(num_frames):
            # Create frame
            frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
            
            # Add to preprocessor
            preprocessor.add_frame(frame)
            
            # Check if batch ready
            if preprocessor.has_batch():
                diff_batch, app_batch = preprocessor.get_batch()
                
                # Verify batch
                assert diff_batch.shape == (10, 36, 36, 3)
                assert app_batch.shape == (10, 36, 36, 3)
        
        # Should have created 3 batches (30 frames / 10 per batch)
        assert preprocessor.batches_formed == 3
        assert preprocessor.frames_processed == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])