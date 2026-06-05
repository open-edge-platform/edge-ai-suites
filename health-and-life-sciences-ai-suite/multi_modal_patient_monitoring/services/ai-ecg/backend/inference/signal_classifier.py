"""Lightweight ECG rhythm classifier based on R-peak / RR-interval analysis.

Classifies a single-lead ECG signal into one of four categories used by the
PhysioNet Computing in Cardiology 2017 challenge:

  Normal Sinus Rhythm
  Atrial Fibrillation
  Other Rhythm  (bradycardia, tachycardia, premature beats, etc.)
  Too Noisy     (uninterpretable)

The classifier uses signal-processing heuristics (R-peak detection via
scipy, RR-interval statistics) and does **not** require a trained model.
"""

import numpy as np
from scipy.signal import find_peaks, butter, filtfilt


# ── Defaults for PhysioNet CinC-2017 single-lead data (300 Hz) ──────────
_DEFAULT_FS = 300  # sampling frequency in Hz


def _bandpass(sig: np.ndarray, fs: float,
              low: float = 8.0, high: float = 20.0,
              order: int = 2) -> np.ndarray:
    """Band-pass filter tuned to QRS complex energy (8-20 Hz)."""
    nyq = 0.5 * fs
    b, a = butter(order, [low / nyq, high / nyq], btype="band")
    return filtfilt(b, a, sig).astype(np.float64)


def _detect_r_peaks(sig: np.ndarray, fs: float) -> np.ndarray:
    """Polarity-aware R-peak detector on a band-pass filtered signal."""
    # Normalize to zero mean, unit variance
    sig_norm = (sig - np.mean(sig)) / (np.std(sig) + 1e-10)

    filtered = _bandpass(sig_norm, fs)

    # Determine dominant QRS polarity and flip if needed
    pos_energy = np.sum(np.maximum(filtered, 0) ** 2)
    neg_energy = np.sum(np.minimum(filtered, 0) ** 2)
    if neg_energy > pos_energy:
        filtered = -filtered

    # Minimum distance between peaks: ~330 ms (≈180 bpm upper bound)
    min_dist = int(0.33 * fs)

    # Adaptive height threshold based on positive signal percentile
    pos_vals = filtered[filtered > 0]
    if len(pos_vals) == 0:
        return np.array([], dtype=int)
    height_thr = 0.4 * np.percentile(pos_vals, 95)

    peaks, _ = find_peaks(filtered, distance=min_dist, height=height_thr)
    return peaks


def classify_ecg(sig: np.ndarray, fs: float = _DEFAULT_FS) -> str:
    """Return a human-readable classification string.

    Possible values: ``'Normal Sinus Rhythm'``, ``'Atrial Fibrillation'``,
    ``'Other Rhythm'``, ``'Too Noisy'``.

    Parameters
    ----------
    sig : 1-D numpy array
        Raw ECG amplitude values.
    fs : float
        Sampling frequency in Hz (default 300).
    """
    sig = np.asarray(sig, dtype=np.float64)

    # ── 1. Signal quality check ──────────────────────────────────────────
    if len(sig) < int(2 * fs):
        return "Too Noisy"

    if np.std(sig) < 1e-6:
        return "Too Noisy"

    # ── 2. R-peak detection ──────────────────────────────────────────────
    peaks = _detect_r_peaks(sig, fs)

    if len(peaks) < 3:
        return "Too Noisy"

    # ── 3. RR-interval statistics ────────────────────────────────────────
    rr = np.diff(peaks) / fs  # RR intervals in seconds

    # Remove outlier RR intervals (missed or false beats)
    median_rr = np.median(rr)
    mask = (rr > 0.5 * median_rr) & (rr < 2.0 * median_rr)
    rr_clean = rr[mask] if np.sum(mask) >= 3 else rr

    mean_rr = np.mean(rr_clean)
    cv_rr = np.std(rr_clean) / mean_rr if mean_rr > 0 else 0

    heart_rate = 60.0 / mean_rr if mean_rr > 0 else 0

    # ── 4. Classification rules ──────────────────────────────────────────
    # AF: irregularly irregular RR intervals (high coefficient of variation)
    if cv_rr > 0.18 and len(rr_clean) >= 4:
        return "Atrial Fibrillation"

    # Normal sinus rhythm: regular rate between 45-110 bpm
    if 45 <= heart_rate <= 110 and cv_rr < 0.15:
        return "Normal Sinus Rhythm"

    # Otherwise classify as Other (bradycardia, tachycardia, etc.)
    return "Other Rhythm"
