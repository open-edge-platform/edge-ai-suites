"""
Unit tests for InferenceEngine module.

Run with: pytest tests/test_inference_engine.py -v
"""

import pytest
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from inference_engine import InferenceEngine, InferenceError


class TestInferenceEngineInitialization:
    """Test InferenceEngine initialization."""
    
    def test_creates_with_defaults(self):
        """Test default initialization."""
        engine = InferenceEngine(
            model_path="models/mtts_can.hdf5",
            auto_download=True
        )
        
        assert engine.model is not None
        assert engine.batch_size == 10
        assert engine.inference_count == 0
    
    def test_raises_if_model_missing_no_download(self, tmp_path):
        """Test error when model missing and auto_download=False."""
        fake_path = tmp_path / "nonexistent.hdf5"
        
        with pytest.raises(FileNotFoundError):
            InferenceEngine(
                model_path=str(fake_path),
                auto_download=False
            )


class TestInferenceBatch:
    """Test batch inference functionality."""
    
    @pytest.fixture
    def engine(self):
        """Create inference engine for testing."""
        return InferenceEngine(
            model_path="models/mtts_can.hdf5",
            auto_download=True
        )
    
    def test_infer_batch_returns_correct_shapes(self, engine):
        """Test inference output shapes."""
        # Create dummy batches
        diff_batch = np.random.rand(10, 36, 36, 3).astype(np.float32)
        app_batch = np.random.rand(10, 36, 36, 3).astype(np.float32)
        
        pulse_raw, resp_raw = engine.infer_batch(diff_batch, app_batch)
        
        # Check shapes (temporal dimension varies by model architecture)
        assert pulse_raw.shape[0] == 10  # batch size
        assert resp_raw.shape[0] == 10
        assert pulse_raw.ndim == 2  # (batch, time)
        assert resp_raw.ndim == 2
    
    def test_infer_batch_validates_input_shape(self, engine):
        """Test input validation."""
        # Wrong shape
        wrong_shape = np.random.rand(5, 36, 36, 3).astype(np.float32)
        correct_shape = np.random.rand(10, 36, 36, 3).astype(np.float32)
        
        with pytest.raises(ValueError):
            engine.infer_batch(wrong_shape, correct_shape)
    
    def test_infer_batch_handles_dtype_conversion(self, engine):
        """Test automatic dtype conversion."""
        # Create uint8 batches (will be converted to float32)
        diff_batch = np.random.randint(0, 255, (10, 36, 36, 3), dtype=np.uint8)
        app_batch = np.random.randint(0, 255, (10, 36, 36, 3), dtype=np.uint8)
        
        # Should not raise error (auto-converts)
        pulse_raw, resp_raw = engine.infer_batch(diff_batch, app_batch)
        
        assert pulse_raw is not None
        assert resp_raw is not None


class TestInferenceStatistics:
    """Test statistics tracking."""
    
    def test_tracks_inference_count(self):
        """Test inference counter increments."""
        engine = InferenceEngine(
            model_path="models/mtts_can.hdf5",
            auto_download=True
        )
        
        diff_batch = np.random.rand(10, 36, 36, 3).astype(np.float32)
        app_batch = np.random.rand(10, 36, 36, 3).astype(np.float32)
        
        # Run 3 inferences
        for _ in range(3):
            engine.infer_batch(diff_batch, app_batch)
        
        stats = engine.get_stats()
        assert stats['inference_count'] == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])