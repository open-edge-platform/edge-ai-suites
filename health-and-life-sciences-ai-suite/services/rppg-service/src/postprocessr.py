"""
Signal Postprocessor - Convert raw model output to waveforms and metrics.

This module implements the complete signal processing pipeline:
1. Raw signal processing (detrend, cumsum, filter)
2. Waveform generation (pulse and respiration)
3. Metric extraction (HR and RR via FFT)

Reference:
- rppg-web: Waveform generation and visualization
- SDC-MM-Simulator: Metric extraction (HR/RR)
"""

import numpy as np
import scipy.signal
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


class SignalPostprocessor:
    """
    Postprocess raw model signals into waveforms and metrics.
    
    Attributes:
        sampling_rate (float): Sampling rate in Hz (default: 30.0)
        pulse_sos (np.ndarray): Butterworth filter for pulse (SOS format)
        resp_sos (np.ndarray): Butterworth filter for respiration (SOS format)
    """
    
    def __init__(
        self,
        sampling_rate: float = 30.0,
        pulse_lowcut: float = 0.75,
        pulse_highcut: float = 2.5,
        resp_lowcut: float = 0.1,
        resp_highcut: float = 0.5,
        filter_order: int = 3
    ):
        """
        Initialize signal postprocessor.
        
        Args:
            sampling_rate: Sampling rate in Hz (default: 30.0)
            pulse_lowcut: Pulse bandpass lower cutoff in Hz (default: 0.75 → 45 BPM)
            pulse_highcut: Pulse bandpass upper cutoff in Hz (default: 2.5 → 150 BPM)
            resp_lowcut: Respiration bandpass lower cutoff in Hz (default: 0.1 → 6 BrPM)
            resp_highcut: Respiration bandpass upper cutoff in Hz (default: 0.5 → 30 BrPM)
            filter_order: Butterworth filter order (default: 3)
        """
        self.sampling_rate = sampling_rate
        
        # Design Butterworth bandpass filters
        self.pulse_sos = scipy.signal.butter(
            N=filter_order,
            Wn=[pulse_lowcut, pulse_highcut],
            btype='bandpass',
            fs=sampling_rate,
            output='sos'
        )
        
        self.resp_sos = scipy.signal.butter(
            N=filter_order,
            Wn=[resp_lowcut, resp_highcut],
            btype='bandpass',
            fs=sampling_rate,
            output='sos'
        )
        
        logger.info(
            f"SignalPostprocessor initialized: "
            f"sampling_rate={sampling_rate}Hz, "
            f"pulse=[{pulse_lowcut}-{pulse_highcut}]Hz, "
            f"resp=[{resp_lowcut}-{resp_highcut}]Hz"
        )
    
    def process_signal(
        self,
        raw_signal: np.ndarray,
        kind: str = "pulse"
    ) -> np.ndarray:
        """
        Process raw model output into clean waveform.
        
        Pipeline:
        1. Flatten and detrend (remove baseline drift)
        2. Cumulative sum (integrate motion signal)
        3. Bandpass filter (isolate physiological frequencies)
        4. Normalize to [-1, 1] range (for visualization)
        
        Args:
            raw_signal: Raw signal from model (batch_size, temporal_dim)
            kind: Signal type ("pulse" or "resp")
        
        Returns:
            Processed waveform as 1D numpy array, normalized to [-1, 1]
        
        Example:
            >>> postprocessor = SignalPostprocessor()
            >>> pulse_waveform = postprocessor.process_signal(pulse_raw, "pulse")
            >>> print(pulse_waveform.shape)  # (150,)
            >>> print(pulse_waveform.min(), pulse_waveform.max())  # -1.0, 1.0
        """
        # Step 1: Flatten batch dimension
        signal_flat = raw_signal.flatten()
        
        logger.debug(f"Processing {kind} signal: shape={signal_flat.shape}")
        
        # Step 2: Detrend (remove linear trend/baseline drift)
        signal_detrended = scipy.signal.detrend(signal_flat)
        
        # Step 3: Cumulative sum (integrate motion)
        # This converts motion signal to displacement signal
        signal_cumsum = np.cumsum(signal_detrended)
        
        # Step 4: Bandpass filter
        sos = self.pulse_sos if kind == "pulse" else self.resp_sos
        signal_filtered = scipy.signal.sosfilt(sos, signal_cumsum)
        
        # Step 5: Normalize to [-1, 1] for consistent visualization
        signal_normalized = self._normalize(signal_filtered)
        
        logger.debug(
            f"  Detrended range: [{signal_detrended.min():.3f}, {signal_detrended.max():.3f}]"
        )
        logger.debug(
            f"  Filtered range: [{signal_filtered.min():.3f}, {signal_filtered.max():.3f}]"
        )
        logger.debug(
            f"  Normalized range: [{signal_normalized.min():.3f}, {signal_normalized.max():.3f}]"
        )
        
        return signal_normalized
    
    def compute_hr_from_fft(self, pulse_waveform: np.ndarray) -> float:
        """
        Compute heart rate from pulse waveform using FFT.
        
        Steps:
        1. Apply Hanning window (reduce spectral leakage)
        2. Compute FFT (frequency domain)
        3. Find peak in valid HR range (42-180 BPM → 0.7-3.0 Hz)
        4. Convert to BPM
        
        Args:
            pulse_waveform: Processed pulse waveform (1D array)
        
        Returns:
            Heart rate in beats per minute (BPM)
        
        Example:
            >>> hr = postprocessor.compute_hr_from_fft(pulse_waveform)
            >>> print(f"Heart Rate: {hr:.1f} BPM")
            Heart Rate: 72.3 BPM
        """
        # Step 1: Apply Hanning window
        windowed = pulse_waveform * np.hanning(len(pulse_waveform))
        
        # Step 2: Compute FFT
        pulse_fft = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(windowed), 1/self.sampling_rate)
        
        # Step 3: Find peak in valid HR range
        # Valid range: 42-180 BPM → 0.7-3.0 Hz
        valid_range = (freqs >= 0.7) & (freqs <= 3.0)
        
        if not np.any(valid_range):
            logger.warning("No valid HR frequencies found, returning default 70 BPM")
            return 70.0
        
        peak_freq = freqs[valid_range][np.argmax(np.abs(pulse_fft[valid_range]))]
        
        # Step 4: Convert to BPM
        heart_rate = peak_freq * 60.0
        
        logger.debug(f"Heart Rate: {heart_rate:.1f} BPM (peak at {peak_freq:.3f} Hz)")
        
        return heart_rate
    
    def compute_rr_from_fft(self, resp_waveform: np.ndarray) -> float:
        """
        Compute respiration rate from respiration waveform using FFT.
        
        Same process as HR but with different valid frequency range.
        
        Args:
            resp_waveform: Processed respiration waveform (1D array)
        
        Returns:
            Respiration rate in breaths per minute (BrPM)
        
        Example:
            >>> rr = postprocessor.compute_rr_from_fft(resp_waveform)
            >>> print(f"Respiration Rate: {rr:.1f} BrPM")
            Respiration Rate: 14.2 BrPM
        """
        # Step 1: Apply Hanning window
        windowed = resp_waveform * np.hanning(len(resp_waveform))
        
        # Step 2: Compute FFT
        resp_fft = np.fft.rfft(windowed)
        freqs = np.fft.rfftfreq(len(windowed), 1/self.sampling_rate)
        
        # Step 3: Find peak in valid RR range
        # Valid range: 6-30 BrPM → 0.1-0.5 Hz
        valid_range = (freqs >= 0.1) & (freqs <= 0.5)
        
        if not np.any(valid_range):
            logger.warning("No valid RR frequencies found, returning default 15 BrPM")
            return 15.0
        
        peak_freq = freqs[valid_range][np.argmax(np.abs(resp_fft[valid_range]))]
        
        # Step 4: Convert to BrPM
        resp_rate = peak_freq * 60.0
        
        logger.debug(f"Respiration Rate: {resp_rate:.1f} BrPM (peak at {peak_freq:.3f} Hz)")
        
        return resp_rate
    
    def process_batch(
        self,
        pulse_raw: np.ndarray,
        resp_raw: np.ndarray
    ) -> Dict:
        """
        Complete postprocessing: waveforms + metrics.
        
        Args:
            pulse_raw: Raw pulse signal from model
            resp_raw: Raw respiration signal from model
        
        Returns:
            Dictionary with:
            - metrics: {heart_rate, resp_rate}
            - waveforms: {pulse, resp}
        
        Example:
            >>> result = postprocessor.process_batch(pulse_raw, resp_raw)
            >>> print(result['metrics']['heart_rate'])  # 72.3
            >>> print(len(result['waveforms']['pulse']))  # 150
        """
        # Process signals into waveforms
        pulse_waveform = self.process_signal(pulse_raw, kind="pulse")
        resp_waveform = self.process_signal(resp_raw, kind="resp")
        
        # Compute metrics from waveforms
        hr = self.compute_hr_from_fft(pulse_waveform)
        rr = self.compute_rr_from_fft(resp_waveform)
        
        # Package result
        result = {
            "metrics": {
                "heart_rate": float(hr),
                "resp_rate": float(rr),
                "confidence": 0.95  # TODO: Implement confidence estimation
            },
            "waveforms": {
                "pulse": pulse_waveform.tolist(),
                "resp": resp_waveform.tolist(),
                "sampling_rate": self.sampling_rate
            }
        }
        
        return result
    
    def _normalize(self, signal: np.ndarray) -> np.ndarray:
        """
        Normalize signal to [-1, 1] range for consistent visualization.
        
        Args:
            signal: Input signal (any range)
        
        Returns:
            Normalized signal in [-1, 1] range
        """
        signal_min = np.min(signal)
        signal_max = np.max(signal)
        
        # Handle constant signal case
        if signal_max - signal_min < 1e-6:
            logger.warning("Signal has no variation, returning zeros")
            return np.zeros_like(signal)
        
        # Normalize to [-1, 1]
        return 2 * (signal - signal_min) / (signal_max - signal_min) - 1
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"SignalPostprocessor(sampling_rate={self.sampling_rate}Hz)"