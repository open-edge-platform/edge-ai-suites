"""
Unit tests for VideoHandler module.

Run with: pytest tests/test_video_handler.py -v
"""

import pytest
import numpy as np
import time
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from video_handler import VideoHandler


class TestVideoHandlerInitialization:
    """Test VideoHandler initialization and setup."""
    
    def test_creates_with_defaults(self):
        """Test VideoHandler can be created with minimal args."""
        handler = VideoHandler(
            video_path="videos/test_sample.mp4",
            auto_download=True
        )
        
        assert handler.video_path.exists()
        assert handler.target_fps == 30
        assert handler.loop == True
        assert handler.frame_count == 0
    
    def test_downloads_video_if_missing(self, tmp_path):
        """Test auto-download when video doesn't exist."""
        video_path = tmp_path / "test_video.avi"
        
        handler = VideoHandler(
            video_path=str(video_path),
            auto_download=True
        )
        
        # Should have downloaded
        assert video_path.exists()
        assert video_path.stat().st_size > 0
    
    def test_raises_if_no_download_and_missing(self, tmp_path):
        """Test error when video missing and auto_download=False."""
        video_path = tmp_path / "nonexistent.mp4"
        
        with pytest.raises(FileNotFoundError):
            VideoHandler(
                video_path=str(video_path),
                auto_download=False
            )


class TestVideoStreamingimport:
    """Test video frame streaming functionality."""
    
    @pytest.fixture
    def handler(self):
        """Create handler for testing."""
        h = VideoHandler(
            video_path="videos/test_sample.mp4",
            target_fps=30,
            auto_download=True
        )
        h.start_stream()
        yield h
        h.stop_stream()
    
    def test_get_frame_returns_rgb_array(self, handler):
        """Test frame format is correct."""
        frame = handler.get_frame()
        
        assert frame is not None
        assert isinstance(frame, np.ndarray)
        assert len(frame.shape) == 3  # H, W, C
        assert frame.shape[2] == 3  # RGB channels
        assert frame.dtype == np.uint8
        assert frame.min() >= 0
        assert frame.max() <= 255
    
    def test_fps_throttling(self):
        """Test frame rate control."""
        handler = VideoHandler(
            video_path="videos/test_sample.mp4",
            target_fps=10,  # Slow FPS for testing
            auto_download=True
        )
        handler.start_stream()
        
        start_time = time.time()
        
        # Get 10 frames
        for _ in range(10):
            frame = handler.get_frame()
            assert frame is not None
        
        elapsed = time.time() - start_time
        
        # Should take approximately 1 second (10 frames at 10 FPS)
        # Allow 20% tolerance for timing
        assert 0.8 < elapsed < 1.2, f"Expected ~1s, got {elapsed:.2f}s"
        
        handler.stop_stream()
    
    def test_video_loops_correctly(self):
        """Test video restarts when loop=True."""
        handler = VideoHandler(
            video_path="videos/test_sample.mp4",
            loop=True,
            auto_download=True
        )
        
        metadata = handler.get_metadata()
        total_frames = metadata['frame_count']
        
        handler.start_stream()
        
        # Read more frames than video contains
        frames_to_read = min(total_frames + 20, 150)  # Limit for test speed
        
        for i in range(frames_to_read):
            frame = handler.get_frame()
            assert frame is not None, f"Frame {i} is None (looping failed)"
        
        handler.stop_stream()
    
    def test_video_stops_when_loop_false(self):
        """Test video returns None when finished and loop=False."""
        handler = VideoHandler(
            video_path="videos/test_sample.mp4",
            loop=False,
            auto_download=True
        )
        
        metadata = handler.get_metadata()
        total_frames = metadata['frame_count']
        
        handler.start_stream()
        
        # Read all frames
        for _ in range(total_frames):
            frame = handler.get_frame()
            if frame is None:
                break
        
        # Next frame should be None
        frame = handler.get_frame()
        assert frame is None
        
        handler.stop_stream()


class TestVideoHandlerContextManager:
    """Test context manager functionality."""
    
    def test_context_manager_starts_and_stops(self):
        """Test with statement works correctly."""
        with VideoHandler("videos/test_sample.mp4", auto_download=True) as handler:
            frame = handler.get_frame()
            assert frame is not None
            assert handler.cap is not None
        
        # Stream should be closed after context exit
        assert handler.cap is None


class TestVideoMetadata:
    """Test metadata retrieval."""
    
    def test_get_metadata_returns_dict(self):
        """Test metadata contains expected keys."""
        handler = VideoHandler(
            video_path="videos/test_sample.mp4",
            auto_download=True
        )
        
        metadata = handler.get_metadata()
        
        assert isinstance(metadata, dict)
        assert 'path' in metadata
        assert 'fps' in metadata
        assert 'width' in metadata
        assert 'height' in metadata
        assert 'frame_count' in metadata
        assert 'duration' in metadata
        
        assert metadata['width'] > 0
        assert metadata['height'] > 0
        assert metadata['frame_count'] > 0
        assert metadata['duration'] > 0


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])