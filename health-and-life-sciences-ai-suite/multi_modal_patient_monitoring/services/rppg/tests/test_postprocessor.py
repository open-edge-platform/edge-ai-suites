"""
Unit tests for SignalPostprocessor module.

Run with: pytest tests/test_postprocessor.py -v
"""

import pytest
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from postprocessr import SignalPostprocessor


class TestPostprocessorInitialization:
    """Test SignalPostprocessor initialization."""
    
    def test_creates_with_defaults(self):
        """Test default initialization."""
        postprocessor = SignalPostprocessor()
        
        assert postprocessor.sampling_rate == 30.0
        assert postprocessor.pulse_sos is not None
        assert postprocessor.resp_sos is not None


class TestSignalProcessing:
    """Test signal processing functionality."""
    
    @pytest.fixture
    def postprocessor(self):
        """Create postprocessor for testing."""
        return SignalPostprocessor(sampling_rate=30.0)
    
    def test_process_signal_returns_normalized_array(self, postprocessor):
        """Test signal processing output."""
        # Create dummy raw signal
        raw_signal = np.random.randn(10, 150).astype(np.float32)
        
        waveform = postprocessor.process_signal(raw_signal, kind="pulse")
        
        # Check output
        assert isinstance(waveform, np.ndarray)
        assert waveform.ndim == 1  # 1D waveform
        assert waveform.min() >= -1.0
        assert waveform.max() <= 1.0
    
    def test_process_signal_handles_pulse_and_resp(self, postprocessor):
        """Test both signal types."""
        raw_signal = np.random.randn(10, 150).astype(np.float32)
        
        pulse_waveform = postprocessor.process_signal(raw_signal, kind="pulse")
        resp_waveform = postprocessor.process_signal(raw_signal, kind="resp")
        
        assert pulse_waveform is not None
        assert resp_waveform is not None
        assert len(pulse_waveform) > 0
        assert len(resp_waveform) > 0


class TestMetricExtraction:
    """Test HR/RR extraction from waveforms."""
    
    @pytest.fixture
    def postprocessor(self):
        """Create postprocessor for testing."""
        return SignalPostprocessor(sampling_rate=30.0)
    
    def test_compute_hr_returns_valid_range(self, postprocessor):
        """Test HR is in valid physiological range."""
        # Create synthetic pulse signal at ~72 BPM (1.2 Hz)
        t = np.linspace(0, 5, 150)  # 5 seconds at 30 Hz
        pulse_waveform = np.sin(2 * np.pi * 1.2 * t)  # 72 BPM
        
        hr = postprocessor.compute_hr_from_fft(pulse_waveform)
        
        # Should be close to 72 BPM
        assert 60 <= hr <= 90, f"HR {hr} outside expected range"
    
    def test_compute_rr_returns_valid_range(self, postprocessor):
        """Test RR is in valid physiological range."""
        # Create synthetic respiration signal at ~15 BrPM (0.25 Hz)
        t = np.linspace(0, 5, 150)
        resp_waveform = np.sin(2 * np.pi * 0.25 * t)  # 15 BrPM
        
        rr = postprocessor.compute_rr_from_fft(resp_waveform)
        
        # Should be close to 15 BrPM
        assert 10 <= rr <= 20, f"RR {rr} outside expected range"
    
    def test_process_batch_returns_complete_result(self, postprocessor):
        """Test complete batch processing."""
        pulse_raw = np.random.randn(10, 150).astype(np.float32)
        resp_raw = np.random.randn(10, 150).astype(np.float32)
        
        result = postprocessor.process_batch(pulse_raw, resp_raw)
        
        # Check structure
        assert 'metrics' in result
        assert 'waveforms' in result
        assert 'heart_rate' in result['metrics']
        assert 'resp_rate' in result['metrics']
        assert 'pulse' in result['waveforms']
        assert 'resp' in result['waveforms']


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])