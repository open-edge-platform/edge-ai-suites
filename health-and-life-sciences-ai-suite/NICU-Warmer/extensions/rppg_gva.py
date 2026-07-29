"""gvapython callback for rPPG (MTTS-CAN) inside DLSPS pipeline.

This module is loaded by gvapython inside the DL Streamer pipeline:

  gvapython class=RppgCallback function=process
      module=/extensions/rppg_gva.py name=rppg_callback

The callback:
  1. Extracts BGR pixel data from the GVA VideoFrame
  2. Crops an ROI, resizes to 36x36, builds frame-difference batches
  3. Runs the MTTS-CAN model via OpenVINO
  4. Computes HR/RR via FFT on accumulated model outputs
  5. Attaches {"rppg": {...}} via frame.add_message() for MQTTPublisher

No scipy dependency — uses numpy FFT with simple detrending.
"""
from __future__ import annotations

import json
import logging
import time as _time
from collections import deque
from typing import Any, Optional

import cv2
import numpy as np

logger = logging.getLogger("RppgCallback")
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Preprocessor: ROI crop → resize → normalize → frame difference → batch
# ---------------------------------------------------------------------------
class _Preprocessor:
    BATCH_SIZE = 10
    IMG_SIZE = 36

    def __init__(self, roi_top: float, roi_left: float,
                 roi_bottom: float, roi_right: float) -> None:
        self.roi_top = roi_top
        self.roi_left = roi_left
        self.roi_bottom = roi_bottom
        self.roi_right = roi_right
        self._buf: deque = deque(maxlen=self.BATCH_SIZE)
        self._prev: Optional[np.ndarray] = None

    def add_frame(self, bgr: np.ndarray) -> None:
        h, w = bgr.shape[:2]
        t = int(h * self.roi_top)
        b = int(h * self.roi_bottom)
        l = int(w * self.roi_left)
        r = int(w * self.roi_right)
        roi = bgr[t:b, l:r]
        resized = cv2.resize(roi, (self.IMG_SIZE, self.IMG_SIZE),
                             interpolation=cv2.INTER_LINEAR)
        rgb = resized[:, :, ::-1].astype(np.float32) / 255.0
        diff = (rgb - self._prev) if self._prev is not None else np.zeros_like(rgb)
        self._prev = rgb.copy()
        self._buf.append((diff, rgb))

    def has_batch(self) -> bool:
        return len(self._buf) == self.BATCH_SIZE

    def get_batch(self) -> tuple[np.ndarray, np.ndarray]:
        diffs = np.stack([x[0] for x in self._buf])
        apps = np.stack([x[1] for x in self._buf])
        return diffs, apps


# ---------------------------------------------------------------------------
# Postprocessor: buffer model outputs → FFT → HR/RR
# ---------------------------------------------------------------------------
class _Postprocessor:
    WAVEFORM_LEN = 150
    FS = 30.0  # assumed sampling rate

    PULSE_LO, PULSE_HI = 0.75, 2.5   # Hz (45–150 BPM)
    RESP_LO, RESP_HI = 0.1, 0.5      # Hz (6–30 BrPM)
    MIN_SAMPLES = 30
    EMA_ALPHA = 0.15

    def __init__(self) -> None:
        self._pulse: list[float] = []
        self._resp: list[float] = []
        self._ema_hr: float | None = None
        self._ema_rr: float | None = None

    def add(self, raw: np.ndarray) -> None:
        flat = raw.flatten().tolist()
        half = max(1, len(flat) // 2)
        self._pulse.extend(flat[:half])
        self._resp.extend(flat[half:])
        if len(self._pulse) > self.WAVEFORM_LEN:
            self._pulse = self._pulse[-self.WAVEFORM_LEN:]
        if len(self._resp) > self.WAVEFORM_LEN:
            self._resp = self._resp[-self.WAVEFORM_LEN:]

    def compute(self) -> dict[str, Any]:
        if len(self._pulse) < self.MIN_SAMPLES:
            return self._empty("warming_up")

        pw = self._detrend(np.array(self._pulse))
        rw = self._detrend(np.array(self._resp))

        hr = self._peak_bpm(pw, self.PULSE_LO, self.PULSE_HI)
        rr = self._peak_bpm(rw, self.RESP_LO, self.RESP_HI)

        if hr > 0:
            self._ema_hr = hr if self._ema_hr is None else (
                self.EMA_ALPHA * hr + (1 - self.EMA_ALPHA) * self._ema_hr)
        if rr > 0:
            self._ema_rr = rr if self._ema_rr is None else (
                self.EMA_ALPHA * rr + (1 - self.EMA_ALPHA) * self._ema_rr)

        conf = self._confidence(pw, self.PULSE_LO, self.PULSE_HI)

        return {
            "heart_rate_bpm": round(self._ema_hr, 1) if self._ema_hr else None,
            "respiration_rate_bpm": round(self._ema_rr, 1) if self._ema_rr else None,
            "signal_confidence": round(conf, 3),
            "status": "valid" if self._ema_hr else "no_signal",
            "pulse_waveform": pw.tolist(),
            "resp_waveform": rw.tolist(),
        }

    # --- helpers ---
    @staticmethod
    def _detrend(data: np.ndarray) -> np.ndarray:
        return data - np.mean(data)

    def _peak_bpm(self, wave: np.ndarray, lo: float, hi: float) -> float:
        freqs = np.fft.rfftfreq(len(wave), d=1.0 / self.FS)
        mags = np.abs(np.fft.rfft(wave))
        mask = (freqs >= lo) & (freqs <= hi)
        if not mask.any():
            return 0.0
        return float(freqs[mask][np.argmax(mags[mask])] * 60.0)

    def _confidence(self, wave: np.ndarray, lo: float, hi: float) -> float:
        freqs = np.fft.rfftfreq(len(wave), d=1.0 / self.FS)
        mags = np.abs(np.fft.rfft(wave))
        mask = (freqs >= lo) & (freqs <= hi)
        total = mags.sum()
        if total < 1e-9:
            return 0.0
        return float(mags[mask].sum() / total)

    @staticmethod
    def _empty(status: str) -> dict[str, Any]:
        return {
            "heart_rate_bpm": None,
            "respiration_rate_bpm": None,
            "signal_confidence": 0.0,
            "status": status,
            "pulse_waveform": [],
            "resp_waveform": [],
        }


# ---------------------------------------------------------------------------
# gvapython callback class
# ---------------------------------------------------------------------------
class RppgCallback:
    """Called by gvapython for each frame in the DL Streamer pipeline.

    Constructor kwargs (passed via pipeline parameters):
        model_path: str   — path to MTTS-CAN .xml model inside container
        device: str       — OpenVINO device (default "CPU")
        roi_top: float    — ROI top fraction (default 0.10)
        roi_left: float   — ROI left fraction (default 0.30)
        roi_bottom: float — ROI bottom fraction (default 0.56)
        roi_right: float  — ROI right fraction (default 0.70)
    """

    def __init__(self, model_path: str = "/models/rppg/mtts_can.xml",
                 device: str = "CPU",
                 roi_top: float = 0.10, roi_left: float = 0.30,
                 roi_bottom: float = 0.56, roi_right: float = 0.70) -> None:
        self._model_path = model_path
        self._device = device
        self._preproc = _Preprocessor(roi_top, roi_left, roi_bottom, roi_right)
        self._postproc = _Postprocessor()
        self._engine: Any = None
        self._frame_count = 0
        logger.info("RppgCallback init: model=%s device=%s roi=(%.2f,%.2f,%.2f,%.2f)",
                     model_path, device, roi_top, roi_left, roi_bottom, roi_right)

    def _get_engine(self) -> Any:
        if self._engine is None:
            import openvino as ov
            core = ov.Core()
            try:
                self._engine = core.compile_model(self._model_path, self._device)
                logger.info("rPPG model compiled on %s", self._device)
            except Exception:
                logger.warning("rPPG compile failed on %s, falling back to CPU", self._device)
                self._engine = core.compile_model(self._model_path, "CPU")
        return self._engine

    def process(self, frame) -> bool:
        """gvapython entry point — called once per frame.

        Attaches {"rppg": {...}} as a frame message so MQTTPublisher
        includes it in the MQTT metadata payload.
        """
        try:
            self._frame_count += 1

            # Extract BGR numpy array from GVA VideoFrame
            with frame.data() as image:
                vi = frame.video_info()
                h, w = vi.height, vi.width
                fmt = vi.to_caps().get_structure(0).get_value('format')

                if fmt in ('RGBA', 'BGRA', 'BGRx'):
                    channels = 4
                elif fmt == 'GRAY8':
                    channels = 1
                else:
                    channels = 3

                arr = np.frombuffer(image, dtype=np.uint8).reshape((h, w, channels))

                # Convert to BGR if needed
                if fmt == 'RGB':
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                elif fmt in ('RGBA',):
                    bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
                elif fmt in ('BGRA', 'BGRx'):
                    bgr = arr[:, :, :3].copy()
                elif fmt == 'GRAY8':
                    bgr = cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
                else:
                    bgr = arr  # assume BGR

                self._preproc.add_frame(bgr)

            # Only run inference when we have a full batch
            if not self._preproc.has_batch():
                # Attach warming_up status
                rppg_data = _Postprocessor._empty("warming_up")
                rppg_data["inference_ms"] = 0.0
                frame.add_message(json.dumps({"rppg": rppg_data}))
                return True

            diff_batch, app_batch = self._preproc.get_batch()
            engine = self._get_engine()
            _t0 = _time.monotonic()
            outputs = engine([app_batch, diff_batch])
            _infer_ms = (_time.monotonic() - _t0) * 1000.0
            raw = outputs[engine.output(0)]
            self._postproc.add(raw)
            result = self._postproc.compute()
            result["inference_ms"] = round(_infer_ms, 2)

            frame.add_message(json.dumps({"rppg": result}))

            if self._frame_count % 100 == 0:
                logger.info("rPPG frame %d: HR=%.1f RR=%.1f conf=%.2f",
                            self._frame_count,
                            result.get("heart_rate_bpm") or 0,
                            result.get("respiration_rate_bpm") or 0,
                            result.get("signal_confidence", 0))

        except Exception as exc:
            logger.warning("RppgCallback error at frame %d: %s", self._frame_count, exc)
            # Attach error status so downstream sees something
            frame.add_message(json.dumps({"rppg": {
                "heart_rate_bpm": None, "respiration_rate_bpm": None,
                "signal_confidence": 0.0, "status": "error",
                "pulse_waveform": [], "resp_waveform": [],
            }}))

        return True
