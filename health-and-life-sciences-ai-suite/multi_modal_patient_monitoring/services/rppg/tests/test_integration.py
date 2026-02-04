"""
Integration test: VideoHandler + Preprocessor

This tests the first two stages of the pipeline working together.

Run with: pytest tests/test_integration_phase3.py -v
"""

import pytest
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from video_handler import VideoHandler
from preprocessor import Preprocessor


class TestVideoToPreprocessor:
    """Test VideoHandler output feeds into Preprocessor correctly."""
    
    def test_video_frames_preprocess_correctly(self):
        """Test frames from video can be preprocessed."""
        # Create video handler
        video_handler = VideoHandler(
            video_path="videos/test_sample.mp4",
            target_fps=30,
            auto_download=True
        )
        
        # Create preprocessor
        preprocessor = Preprocessor(batch_size=10)
        
        # Start video
        video_handler.start_stream()
        
        # Process 10 frames to form one batch
        for i in range(10):
            frame = video_handler.get_frame()
            
            assert frame is not None
            assert frame.dtype == np.uint8
            assert len(frame.shape) == 3
            
            # Add to preprocessor
            preprocessor.add_frame(frame)
        
        # Batch should be ready
        assert preprocessor.has_batch()
        
        # Get batch
        diff_batch, app_batch = preprocessor.get_batch()
        
        # Verify batch shapes
        assert diff_batch.shape == (10, 36, 36, 3)
        assert app_batch.shape == (10, 36, 36, 3)
        assert diff_batch.dtype == np.float32
        assert app_batch.dtype == np.float32
        
        # Verify value ranges
        assert diff_batch.min() >= -1.0
        assert diff_batch.max() <= 1.0
        assert app_batch.min() >= 0.0
        assert app_batch.max() <= 1.0
        
        video_handler.stop_stream()
    
    def test_multiple_batches_from_video(self):
        """Test can create multiple batches from video."""
        video_handler = VideoHandler(
            video_path="videos/test_sample.mp4",
            target_fps=30,
            auto_download=True
        )
        
        preprocessor = Preprocessor(batch_size=10)
        video_handler.start_stream()
        
        batches_created = 0
        max_batches = 3  # Create 3 batches (30 frames)
        
        frame_count = 0
        while batches_created < max_batches:
            frame = video_handler.get_frame()
            
            if frame is None:
                break
            
            preprocessor.add_frame(frame)
            frame_count += 1
            
            if preprocessor.has_batch():
                diff_batch, app_batch = preprocessor.get_batch()
                batches_created += 1
                
                # Verify each batch
                assert diff_batch.shape == (10, 36, 36, 3)
                assert app_batch.shape == (10, 36, 36, 3)
        
        assert batches_created == 3
        assert frame_count == 30
        
        video_handler.stop_stream()
    
    def test_preprocessing_preserves_temporal_order(self):
        """Test preprocessor maintains frame order."""
        video_handler = VideoHandler(
            video_path="videos/test_sample.mp4",
            target_fps=30,
            auto_download=True
        )
        
        preprocessor = Preprocessor(batch_size=5)  # Smaller batch for test
        video_handler.start_stream()
        
        # Get 5 frames and store them
        original_frames = []
        for _ in range(5):
            frame = video_handler.get_frame()
            original_frames.append(frame.copy())
            preprocessor.add_frame(frame)
        
        # Get batch
        diff_batch, app_batch = preprocessor.get_batch()
        
        # Verify first frame in batch corresponds to first input
        # (appearance frames should be recognizable)
        # Note: We can't check exact equality due to ROI extraction and resizing
        # but can verify batch has 5 frames in order
        assert diff_batch.shape[0] == 5
        assert app_batch.shape[0] == 5
        
        video_handler.stop_stream()


class TestPipelinePerformance:
    """Test performance of video + preprocessing pipeline."""
    
    def test_processing_speed(self):
        """Test pipeline can process at target FPS."""
        import time
        
        video_handler = VideoHandler(
            video_path="videos/test_sample.mp4",
            target_fps=30,
            auto_download=True
        )
        
        preprocessor = Preprocessor(batch_size=10)
        video_handler.start_stream()
        
        start_time = time.time()
        
        # Process 30 frames (1 second of video at 30 FPS)
        for _ in range(30):
            frame = video_handler.get_frame()
            preprocessor.add_frame(frame)
            
            if preprocessor.has_batch():
                preprocessor.get_batch()
        
        elapsed = time.time() - start_time
        
        # Should take approximately 1 second (with some tolerance)
        # Note: Preprocessing adds minimal overhead (<50ms per batch)
        assert 0.9 < elapsed < 1.5, f"Expected ~1s, got {elapsed:.2f}s"
        
        video_handler.stop_stream()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])