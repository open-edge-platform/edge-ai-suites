"""C2: NICU rPPG custom pipeline script.

Adapts the multi-modal rPPG service logic (preprocessor / OpenVINO inference /
postprocessor) into a standalone class that is safe to call from the DLSPS
status-polling loop.

Design decisions
----------------
- No network calls; operates purely on numpy arrays pushed by the caller.
- ``RppgPipeline`` is stateeful: it maintains a frame buffer so HR/RR improve
  over time as more frames accumulate.
- All failures are caught and surfaced as ``status: "error"`` so the calling
  poller never crashes.
- OpenVINO is imported lazily so the module loads even without GPU hardware,
  allowing unit tests to mock the inference engine.

Output schema (returned by ``process()``)
------------------------------------------
{
    "heart_rate_bpm":        float | None,
    "respiration_rate_bpm":  float | None,
    "signal_confidence":     float,   # 0.0–1.0
    "status":                str,     # "valid" | "warming_up" | "no_face" | "error"
}
"""
from __future__ import annotations

import logging
from collections import deque
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Preprocessor (adapted from multi_modal_patient_monitoring/services/rppg/)
# ---------------------------------------------------------------------------

class _Preprocessor:
    """Crop ROI → resize → normalise → frame difference → batch formation.

    Batch size is fixed at 10 frames (MTTS-CAN requirement).
    """

    BATCH_SIZE = 10
    IMG_SIZE = 36

    def __init__(
        self,
        crop_top: float = 0.1,
        crop_left: float = 0.3,
        crop_bottom: float = 0.56,
        crop_right: float = 0.7,
    ) -> None:
        self.crop_top = crop_top
        self.crop_left = crop_left
        self.crop_bottom = crop_bottom
        self.crop_right = crop_right
        self._buf: deque = deque(maxlen=self.BATCH_SIZE)
        self._prev: Optional[np.ndarray] = None

    def add_frame(self, frame_bgr: np.ndarray) -> None:
        """Add one BGR frame (H×W×3 uint8) to the rolling buffer."""
        try:
            import cv2  # noqa: PLC0415 – local import keeps module loadable without cv2
            h, w = frame_bgr.shape[:2]
            t = int(h * self.crop_top)
            b = int(h * self.crop_bottom)
            lft = int(w * self.crop_left)
            rgt = int(w * self.crop_right)
            roi = frame_bgr[t:b, lft:rgt]
            resized = cv2.resize(roi, (self.IMG_SIZE, self.IMG_SIZE), interpolation=cv2.INTER_LINEAR)
            # Convert BGR → RGB and normalise to [0,1]
            rgb = resized[:, :, ::-1].astype(np.float32) / 255.0
            diff = (rgb - self._prev) if self._prev is not None else np.zeros_like(rgb)
            self._prev = rgb.copy()
            self._buf.append((diff, rgb))
        except Exception as exc:
            logger.warning("Preprocessor.add_frame error: %s", exc)

    def has_batch(self) -> bool:
        return len(self._buf) == self.BATCH_SIZE

    def get_batch(self) -> tuple[np.ndarray, np.ndarray]:
        """Return (diff_batch, app_batch) each shaped (10, 36, 36, 3)."""
        diffs = np.stack([item[0] for item in self._buf])  # (10, 36, 36, 3)
        apps = np.stack([item[1] for item in self._buf])   # (10, 36, 36, 3)
        return diffs, apps


# ---------------------------------------------------------------------------
# Postprocessor (adapted from multi_modal_patient_monitoring/services/rppg/)
# ---------------------------------------------------------------------------

class _Postprocessor:
    """Buffer raw model outputs and compute HR/RR via FFT.

    Falls back to numpy FFT so scipy is not a hard dependency, but will use
    scipy bandpass filtering when available.
    """

    WAVEFORM_SAMPLES = 150
    SAMPLING_RATE = 30.0  # assumed fps; good enough for MVP

    PULSE_LO = 0.75   # Hz → 45 BPM
    PULSE_HI = 2.5    # Hz → 150 BPM
    RESP_LO = 0.1     # Hz → 6 BrPM
    RESP_HI = 0.5     # Hz → 30 BrPM

    MIN_SAMPLES_FOR_FFT = 30
    EMA_ALPHA = 0.15  # smoothing factor – lower = smoother

    def __init__(self) -> None:
        self._pulse_buf: list[float] = []
        self._resp_buf: list[float] = []
        self._ema_hr: float | None = None
        self._ema_rr: float | None = None

    def add(self, raw_output: np.ndarray) -> None:
        """Append model output to pulse/resp buffers."""
        flat = raw_output.flatten().tolist()
        # Heuristic: first half → pulse, second half → resp
        half = max(1, len(flat) // 2)
        self._pulse_buf.extend(flat[:half])
        self._resp_buf.extend(flat[half:])
        # Trim to window
        if len(self._pulse_buf) > self.WAVEFORM_SAMPLES:
            self._pulse_buf = self._pulse_buf[-self.WAVEFORM_SAMPLES:]
        if len(self._resp_buf) > self.WAVEFORM_SAMPLES:
            self._resp_buf = self._resp_buf[-self.WAVEFORM_SAMPLES:]

    def compute(self) -> dict[str, Any]:
        if len(self._pulse_buf) < self.MIN_SAMPLES_FOR_FFT:
            return {
                "heart_rate_bpm": None,
                "respiration_rate_bpm": None,
                "signal_confidence": 0.0,
                "status": "warming_up",
                "pulse_waveform": [],
                "resp_waveform": [],
            }

        pulse_wave = self._bandpass(np.array(self._pulse_buf), self.PULSE_LO, self.PULSE_HI)
        resp_wave = self._bandpass(np.array(self._resp_buf), self.RESP_LO, self.RESP_HI)

        hr = self._peak_freq_bpm(pulse_wave, self.PULSE_LO, self.PULSE_HI)
        rr = self._peak_freq_bpm(resp_wave, self.RESP_LO, self.RESP_HI)

        # EMA smoothing for stable display
        if hr > 0:
            self._ema_hr = hr if self._ema_hr is None else (
                self.EMA_ALPHA * hr + (1 - self.EMA_ALPHA) * self._ema_hr)
        if rr > 0:
            self._ema_rr = rr if self._ema_rr is None else (
                self.EMA_ALPHA * rr + (1 - self.EMA_ALPHA) * self._ema_rr)

        # Confidence proxy: normalised FFT peak magnitude
        confidence = self._confidence(pulse_wave, self.PULSE_LO, self.PULSE_HI)

        return {
            "heart_rate_bpm": round(self._ema_hr, 1) if self._ema_hr else None,
            "respiration_rate_bpm": round(self._ema_rr, 1) if self._ema_rr else None,
            "signal_confidence": round(confidence, 3),
            "status": "valid" if self._ema_hr else "no_signal",
            "pulse_waveform": pulse_wave.tolist(),
            "resp_waveform": resp_wave.tolist(),
        }

    # ------------------------------------------------------------------
    def _bandpass(self, data: np.ndarray, lo: float, hi: float) -> np.ndarray:
        try:
            from scipy.signal import butter, filtfilt  # noqa: PLC0415
            nyq = 0.5 * self.SAMPLING_RATE
            b, a = butter(3, [max(0.01, lo / nyq), min(0.99, hi / nyq)], btype="band")
            return filtfilt(b, a, data)
        except Exception:
            # scipy not available or filter fails — return detrended signal
            return data - np.mean(data)

    def _peak_freq_bpm(self, wave: np.ndarray, lo: float, hi: float) -> float:
        freqs = np.fft.rfftfreq(len(wave), d=1.0 / self.SAMPLING_RATE)
        mags = np.abs(np.fft.rfft(wave))
        mask = (freqs >= lo) & (freqs <= hi)
        if not mask.any():
            return 0.0
        peak_hz = freqs[mask][np.argmax(mags[mask])]
        return peak_hz * 60.0

    def _confidence(self, wave: np.ndarray, lo: float, hi: float) -> float:
        freqs = np.fft.rfftfreq(len(wave), d=1.0 / self.SAMPLING_RATE)
        mags = np.abs(np.fft.rfft(wave))
        mask = (freqs >= lo) & (freqs <= hi)
        total = mags.sum()
        if total < 1e-9:
            return 0.0
        return float(mags[mask].sum() / total)


# ---------------------------------------------------------------------------
# Public pipeline class
# ---------------------------------------------------------------------------

class RppgPipeline:
    """End-to-end rPPG pipeline: frames in, HR/RR dict out.

    Usage
    -----
    pipeline = RppgPipeline(model_xml="/models/rppg/mtts_can.xml", device="GPU")
    result = pipeline.process([frame1, frame2, ...])   # BGR uint8 frames
    # {"heart_rate_bpm": 73.5, "respiration_rate_bpm": 14.2, ...}

    The pipeline is designed to be called every polling cycle with whatever
    frames DLSPS makes available.  The preprocessor and postprocessor buffers
    are persistent across calls so estimates improve over time.
    """

    def __init__(
        self,
        model_xml: str = "/models/rppg/mtts_can.xml",
        device: str = "GPU",
        batch_size: int = 10,
    ) -> None:
        self._model_xml = model_xml
        self._device = device
        self._batch_size = batch_size
        self._preprocessor = _Preprocessor()
        self._postprocessor = _Postprocessor()
        self._engine: Any = None  # lazy-loaded

    # ------------------------------------------------------------------
    # Lazy inference engine (avoids heavy OV import at module load time)
    # ------------------------------------------------------------------

    def _get_engine(self) -> Any:
        if self._engine is None:
            from pathlib import Path  # noqa: PLC0415
            if not Path(self._model_xml).exists():
                raise FileNotFoundError(
                    f"rPPG model not found: {self._model_xml}. "
                    "Run asset preparation with rppg.enabled=true first."
                )
            # Import InferenceEngine inline so tests can patch it without
            # importing the whole openvino stack.
            import sys, os  # noqa: PLC0415, E401
            sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
            import openvino as ov  # noqa: PLC0415
            core = ov.Core()
            try:
                compiled = core.compile_model(self._model_xml, self._device)
            except Exception:
                logger.warning("rPPG: failed to compile on %s, falling back to CPU", self._device)
                compiled = core.compile_model(self._model_xml, "CPU")
            self._engine = compiled
        return self._engine

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def process(self, frames_bgr: list[np.ndarray]) -> dict[str, Any]:
        """Process a list of BGR frames and return normalised rPPG output.

        Returns a safe dict even when inference fails.
        """
        if not frames_bgr:
            return _safe_output("no_frames")

        try:
            for frame in frames_bgr:
                self._preprocessor.add_frame(frame)

            if not self._preprocessor.has_batch():
                return _safe_output("warming_up")

            diff_batch, app_batch = self._preprocessor.get_batch()

            engine = self._get_engine()
            inputs = list(engine.inputs)
            outputs = engine([app_batch, diff_batch])
            raw = outputs[engine.output(0)]

            self._postprocessor.add(raw)
            result = self._postprocessor.compute()
            logger.debug("rPPG result: %s", result)
            return result

        except FileNotFoundError as exc:
            logger.warning("rPPG inference skipped: %s", exc)
            return _safe_output("model_not_loaded")
        except Exception as exc:
            logger.exception("rPPG inference error: %s", exc)
            return _safe_output("error")


def _safe_output(status: str) -> dict[str, Any]:
    return {
        "heart_rate_bpm": None,
        "respiration_rate_bpm": None,
        "signal_confidence": 0.0,
        "status": status,
        "pulse_waveform": [],
        "resp_waveform": [],
    }
