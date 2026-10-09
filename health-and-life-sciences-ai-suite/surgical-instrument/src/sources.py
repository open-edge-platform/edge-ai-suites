"""Frame sources — one interface for Basler, generic V4L2/USB, and video files.
 
Every source yields BGR numpy frames via ``read()`` so the rest of the app is
source-agnostic. This is what makes the demo work identically for a live camera
and a recorded video file.
"""
from __future__ import annotations
 
import logging
import time
from typing import Protocol
 
import cv2
import numpy as np
 
log = logging.getLogger("sources")
 
 
class Source(Protocol):
    name: str
    width: int
    height: int
    fps: float
    is_live: bool
 
    def read(self) -> np.ndarray | None: ...
    def close(self) -> None: ...
 
 
class FileSource:
    """Video file via OpenCV. Loops on EOF so demos run continuously."""
 
    is_live = False
 
    def __init__(self, path: str, loop: bool = True) -> None:
        self.name = f"file:{path}"
        self._path = path
        self._loop = loop
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            raise RuntimeError(f"cannot open video file: {path}")
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or 30.0
 
    def read(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        if not ok:
            if not self._loop:
                return None
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self._cap.read()
        return frame if ok else None
 
    def close(self) -> None:
        self._cap.release()
 
 
class V4L2Source:
    """Generic USB/webcam via OpenCV (device index or /dev/videoN)."""
 
    is_live = True
 
    def __init__(self, device: str | int, width: int, height: int, fps: float) -> None:
        self.name = f"v4l2:{device}"
        dev = int(device) if str(device).isdigit() else device
        self._cap = cv2.VideoCapture(dev)
        if not self._cap.isOpened():
            raise RuntimeError(f"cannot open camera: {device}")
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # newest-frame-wins
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or width
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or height
        self.fps = self._cap.get(cv2.CAP_PROP_FPS) or fps
 
    def read(self) -> np.ndarray | None:
        ok, frame = self._cap.read()
        return frame if ok else None
 
    def close(self) -> None:
        self._cap.release()
 
 
class BaslerSource:
    """Basler camera via pypylon, newest-frame-wins (LatestImageOnly)."""
 
    is_live = True
 
    def __init__(
        self,
        serial: str | None,
        width: int,
        height: int,
        exposure_us: float | None = None,
        gain: float | None = None,
        fps_limit: float | None = None,
        trigger: str = "off",
    ) -> None:
        from pypylon import pylon  # imported lazily so file/v4l2 users don't need it

        self._pylon = pylon
        self._trigger = trigger  # off | software | vsync (vsync = software-trigger, vblank-paced)
        tl = pylon.TlFactory.GetInstance()
        if serial:
            di = pylon.DeviceInfo()
            di.SetSerialNumber(str(serial))
            self._cam = pylon.InstantCamera(tl.CreateDevice(di))
        else:
            self._cam = pylon.InstantCamera(tl.CreateFirstDevice())
        self._cam.Open()
        self.name = f"basler:{self._cam.GetDeviceInfo().GetSerialNumber()}"
 
        self._try_set_size(width, height)
        # Only override exposure/gain when explicitly requested. A short exposure cuts
        # latency + motion blur but darkens the image; endoscopy needs adequate,
        # clinically-validated illumination, so we do NOT force a fixed value here —
        # left untouched, the camera keeps the operator's configured exposure.
        if exposure_us is not None:
            self._try("ExposureAuto", "Off")
            self._try("ExposureTime", float(exposure_us))
        if gain is not None:
            self._try("GainAuto", "Off")
            self._try("Gain", float(gain))

        # Software trigger: expose one frame per read() instead of free-running, so
        # the frame is captured just-in-time (optionally vblank-paced by the caller).
        # This is the reference's photon-to-pixel latency mechanism.
        self._triggered = trigger in ("software", "vsync")
        if self._triggered:
            self._try("TriggerSelector", "FrameStart")
            self._try("TriggerMode", "On")
            self._try("TriggerSource", "Software")
        else:
            self._try("TriggerMode", "Off")
 
        # Optional capture-rate cap (equivalent to gencamsrc frame-rate=<n>): locks
        # the sensor to a fixed FPS so it doesn't beat against the display refresh.
        # Node names differ across Basler models / SFNC versions, so try both.
        if fps_limit and fps_limit > 0:
            self._try("AcquisitionFrameRateEnable", True)
            self._try("AcquisitionFrameRate", float(fps_limit))     # SFNC 2.x (USB3 / ace 2)
            self._try("AcquisitionFrameRateAbs", float(fps_limit))  # SFNC 1.x (GigE / older)
        else:
            # 0 == free-running: actively release any cap the camera retained from
            # a previous run (Basler keeps this across process restarts).
            self._try("AcquisitionFrameRateEnable", False)

        self.width = int(self._cam.Width.GetValue())
        self.height = int(self._cam.Height.GetValue())
        # Report the capped rate when set; otherwise free-running (app reports effective).
        self.fps = float(fps_limit) if (fps_limit and fps_limit > 0) else 0.0

        self._conv = pylon.ImageFormatConverter()
        self._conv.OutputPixelFormat = pylon.PixelType_BGR8packed
        self._conv.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        # Always LatestImageOnly: the grab result queue holds only the newest frame
        # (zero queue), even when software-triggered. This mirrors the reference and
        # is what the BU team requires -- OneByOne builds an in-order backlog that
        # shows up as a "queue of frames" and adds photon-to-pixel latency.
        self._cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
 
    def _try(self, node: str, value) -> None:  # noqa: ANN001
        try:
            getattr(self._cam, node).SetValue(value)
        except Exception as exc:  # noqa: BLE001
            log.debug("basler: could not set %s=%s (%s)", node, value, exc)
 
    def _try_set_size(self, width: int, height: int) -> None:
        try:
            max_w, max_h = self._cam.Width.GetMax(), self._cam.Height.GetMax()
            w, h = min(width, max_w), min(height, max_h)
            self._cam.OffsetX.SetValue(0)
            self._cam.OffsetY.SetValue(0)
            self._cam.Width.SetValue(w)
            self._cam.Height.SetValue(h)
            ix, iy = self._cam.OffsetX.GetInc(), self._cam.OffsetY.GetInc()
            self._cam.OffsetX.SetValue(((max_w - w) // 2 // ix) * ix)
            self._cam.OffsetY.SetValue(((max_h - h) // 2 // iy) * iy)
        except Exception as exc:  # noqa: BLE001
            log.warning("basler: ROI setup skipped (%s)", exc)
 
    def read(self) -> np.ndarray | None:
        # TimeoutHandling_Return (not ThrowException): a GenICam C++ exception
        # crossing back into Python is a known trigger for the glibc
        # "longjmp causes uninitialized stack frame" abort. Return None instead.
        if self._triggered:
            if not self._cam.WaitForFrameTriggerReady(1000, self._pylon.TimeoutHandling_Return):
                return None
            self._cam.ExecuteSoftwareTrigger()
        grab = self._cam.RetrieveResult(5000, self._pylon.TimeoutHandling_Return)
        if grab is None:
            return None
        try:
            if not grab.GrabSucceeded():
                return None
            return self._conv.Convert(grab).GetArray()
        finally:
            grab.Release()
 
    def close(self) -> None:
        try:
            if self._cam.IsGrabbing():
                self._cam.StopGrabbing()
            self._cam.Close()
        except Exception:  # noqa: BLE001
            pass
 
 
def create_source(cfg) -> Source:  # noqa: ANN001
    kind = cfg.source
    if kind == "file":
        return FileSource(cfg.source_arg, loop=cfg.loop)
    if kind == "v4l2":
        return V4L2Source(cfg.source_arg or 0, cfg.width, cfg.height, cfg.target_fps)
    if kind == "basler":
        # Exposure is left as the camera has it unless --exposure-us is given, so
        # clinical illumination isn't silently changed. Lower it explicitly to trade
        # brightness for less latency/motion blur once validated.
        return BaslerSource(
            serial=cfg.source_arg or None,
            width=cfg.width,
            height=cfg.height,
            exposure_us=cfg.exposure_us,
            gain=cfg.gain,
            fps_limit=cfg.camera_fps,
            trigger=cfg.camera_trigger,
        )
    raise ValueError(f"unknown source: {kind!r} (want file|v4l2|basler)")