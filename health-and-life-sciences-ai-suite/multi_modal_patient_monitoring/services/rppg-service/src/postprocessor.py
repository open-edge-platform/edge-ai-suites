import numpy as np
import logging
"""
Signal Postprocessor - Extract HR/RR from raw model outputs.
"""

import numpy as np
from scipy import signal
from scipy.fft import rfft, rfftfreq
import logging
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class SignalPostprocessor:
    """
    Postprocess raw MTTS-CAN outputs to extract vital signs.
    
    Handles both single-value and temporal sequence outputs.
    """
    
    def __init__(
        self,
        sampling_rate: float = 30.0,
        pulse_lowcut: float = 0.75,
        pulse_highcut: float = 2.5,
        resp_lowcut: float = 0.1,
        resp_highcut: float = 0.5,
        filter_order: int = 3,
        waveform_samples: int = 150
    ):
        """
        Initialize postprocessor.
        
        Args:
            sampling_rate: Video frame rate (Hz)
            pulse_lowcut: Lower cutoff for pulse (Hz) - 45 BPM
            pulse_highcut: Upper cutoff for pulse (Hz) - 150 BPM
            resp_lowcut: Lower cutoff for respiration (Hz) - 6 BrPM
            resp_highcut: Upper cutoff for respiration (Hz) - 30 BrPM
            filter_order: Butterworth filter order
            waveform_samples: Number of samples to maintain in buffer
        """
        self.sampling_rate = sampling_rate
        self.pulse_lowcut = pulse_lowcut
        self.pulse_highcut = pulse_highcut
        self.resp_lowcut = resp_lowcut
        self.resp_highcut = resp_highcut
        self.filter_order = filter_order
        self.waveform_samples = waveform_samples
        
        # Signal buffers
        self.pulse_buffer = []
        self.resp_buffer = []
        
        logger.info("Postprocessor initialized")
        logger.info(f"  Sampling rate: {sampling_rate} Hz")
        logger.info(f"  Pulse range: {pulse_lowcut*60:.0f}-{pulse_highcut*60:.0f} BPM")
        logger.info(f"  Resp range: {resp_lowcut*60:.0f}-{resp_highcut*60:.0f} BrPM")
    
    def process_signal(
        self,
        raw_output: np.ndarray,
        kind: str = "pulse"
    ) -> np.ndarray:
        """
        Process raw model output into filtered waveform.
        
        Args:
            raw_output: Model output, shape (batch, temporal) or (batch, 1)
            kind: "pulse" or "resp"
        
        Returns:
            Filtered waveform as 1D array
        """
        # Flatten to 1D if needed
        if raw_output.ndim > 1:
            signal_1d = raw_output.flatten()
        else:
            signal_1d = raw_output
        
        # Choose filter parameters
        if kind == "pulse":
            lowcut, highcut = self.pulse_lowcut, self.pulse_highcut
            buffer = self.pulse_buffer
        else:  # resp
            lowcut, highcut = self.resp_lowcut, self.resp_highcut
            buffer = self.resp_buffer
        
        # Add to buffer
        buffer.extend(signal_1d.tolist())
        
        # Trim buffer
        if len(buffer) > self.waveform_samples:
            buffer[:] = buffer[-self.waveform_samples:]
        
        # Need enough samples for filtering
        if len(buffer) < 30:
            logger.debug(f"Not enough samples yet: {len(buffer)}")
            return np.array(buffer)
        
        # Bandpass filter
        try:
            filtered = self._bandpass_filter(
                np.array(buffer),
                lowcut,
                highcut,
                self.sampling_rate,
                self.filter_order
            )
            return filtered
        except Exception as e:
            logger.warning(f"Filtering failed: {e}, returning raw")
            return np.array(buffer)
    
    def _bandpass_filter(
        self,
        data: np.ndarray,
        lowcut: float,
        highcut: float,
        fs: float,
        order: int
    ) -> np.ndarray:
        """Apply Butterworth bandpass filter."""
        nyquist = 0.5 * fs
        low = lowcut / nyquist
        high = highcut / nyquist
        
        # Clamp to valid range
        low = max(0.01, min(low, 0.99))
        high = max(low + 0.01, min(high, 0.99))
        
        b, a = signal.butter(order, [low, high], btype='band')
        filtered = signal.filtfilt(b, a, data)
        
        return filtered
    
    def compute_hr_from_fft(self, waveform: np.ndarray) -> float:
        """
        Compute heart rate from pulse waveform using FFT.
        
        Args:
            waveform: Pulse waveform (1D array)
        
        Returns:
            Heart rate in BPM
        """
        if len(waveform) < 30:
            return 0.0
        
        # Compute FFT
        freqs = rfftfreq(len(waveform), 1.0 / self.sampling_rate)
        fft_vals = np.abs(rfft(waveform))
        
        # Find peak in valid HR range (0.75 - 2.5 Hz = 45-150 BPM)
        valid_idx = np.where((freqs >= self.pulse_lowcut) & (freqs <= self.pulse_highcut))[0]
        
        if len(valid_idx) == 0:
            return 0.0
        
        peak_idx = valid_idx[np.argmax(fft_vals[valid_idx])]
        hr_hz = freqs[peak_idx]
        hr_bpm = hr_hz * 60.0
        
        logger.debug(f"HR: {hr_bpm:.1f} BPM (peak at {hr_hz:.3f} Hz)")
        
        return hr_bpm
    
    def compute_rr_from_fft(self, waveform: np.ndarray) -> float:
        """
        Compute respiration rate from resp waveform using FFT.
        
        Args:
            waveform: Respiration waveform (1D array)
        
        Returns:
            Respiration rate in breaths per minute
        """
        if len(waveform) < 30:
            return 0.0
        
        # Compute FFT
        freqs = rfftfreq(len(waveform), 1.0 / self.sampling_rate)
        fft_vals = np.abs(rfft(waveform))
        
        # Find peak in valid RR range (0.1 - 0.5 Hz = 6-30 BrPM)
        valid_idx = np.where((freqs >= self.resp_lowcut) & (freqs <= self.resp_highcut))[0]
        
        if len(valid_idx) == 0:
            return 0.0
        
        peak_idx = valid_idx[np.argmax(fft_vals[valid_idx])]
        rr_hz = freqs[peak_idx]
        rr_brpm = rr_hz * 60.0
        
        logger.debug(f"RR: {rr_brpm:.1f} BrPM (peak at {rr_hz:.3f} Hz)")
        
        return rr_brpm
    
    def get_waveforms(self) -> Dict[str, np.ndarray]:
        """Get current waveform buffers."""
        return {
            'pulse': np.array(self.pulse_buffer),
            'resp': np.array(self.resp_buffer)
        }
    
    def reset_buffers(self):
        """Clear signal buffers."""
        self.pulse_buffer.clear()
        self.resp_buffer.clear()
        logger.debug("Buffers reset")
