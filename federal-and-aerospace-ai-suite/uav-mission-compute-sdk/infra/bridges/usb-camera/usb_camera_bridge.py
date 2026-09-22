#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
USB Camera Bridge — real V4L2 camera → RTSP (or MQTT) output.

Drop-in sibling of infra/bridges/camera/camera_bridge.py: instead of reading
synthetic frames from a Gazebo gz-transport topic, this reads real frames from
a USB camera device (e.g. /dev/video0) via GStreamer's v4l2src, then either:
  - RTSP mode (default): pipes raw BGR frames to ffmpeg, which encodes H264
    and pushes them to MediaMTX via RTSP ANNOUNCE — same target path shape
    used by the simulated camera-bridge (rtsp://mediamtx:8554/<uav>/<cam>),
    so vision-processor / edge-ai-showcase can consume it unchanged.
  - MQTT mode: encodes JPEG and publishes frame-by-frame to MQTT.

Enumerate available devices on the host with:
    v4l2-ctl --list-devices

Configuration is via environment variables (see README / docker-compose.yml).
"""

import logging
import os
import subprocess
import threading
import time
from typing import Optional

import cv2
import numpy as np
import paho.mqtt.client as mqtt

try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    GST_AVAILABLE = True
except (ImportError, ValueError):
    GST_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("usb-camera-bridge")

# ── Core config ───────────────────────────────────────────────────────────────
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
UAV_ID           = os.getenv("UAV_ID", "uav-1")
CAMERA_ID        = os.getenv("CAMERA_ID", "usb")

# ── V4L2 capture config ───────────────────────────────────────────────────────
VIDEO_DEVICE    = os.getenv("VIDEO_DEVICE", "/dev/video0")
CAPTURE_WIDTH   = int(os.getenv("CAPTURE_WIDTH", "1280"))
CAPTURE_HEIGHT  = int(os.getenv("CAPTURE_HEIGHT", "720"))
SENSOR_FPS      = int(os.getenv("SENSOR_FPS", "30"))
# "mjpeg" (v4l2src ! image/jpeg ! jpegdec) or "raw" (v4l2src ! video/x-raw)
CAPTURE_FORMAT  = os.getenv("CAPTURE_FORMAT", "mjpeg").lower()

# ── RTSP config ────────────────────────────────────────────────────────────────
USE_RTSP     = os.getenv("USE_RTSP", "true").lower() == "true"
RTSP_HOST    = os.getenv("RTSP_HOST", "mediamtx")
RTSP_PORT    = int(os.getenv("RTSP_PORT", "8554"))
RTSP_BITRATE = int(os.getenv("RTSP_BITRATE", "2000"))  # kbps

# ── MQTT mode config ───────────────────────────────────────────────────────────
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))
MQTT_MAX_FPS = float(os.getenv("MQTT_MAX_FPS", "0"))


def list_v4l2_devices() -> None:
    """Best-effort log of available V4L2 devices, for diagnostics."""
    try:
        result = subprocess.run(
            ["v4l2-ctl", "--list-devices"], capture_output=True, text=True, timeout=5
        )
        log.info("Available V4L2 devices:\n%s", result.stdout.strip() or result.stderr.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.warning("Could not enumerate V4L2 devices (%s)", e)


# ── V4L2 reader (GStreamer v4l2src → BGR frames) ──────────────────────────────

class V4L2Reader:
    """Captures the latest frame from a local USB camera in its own thread."""

    def __init__(self, cam_id: str):
        self.cam_id    = cam_id
        self._latest: Optional[np.ndarray] = None
        self._seq      = 0
        self._lock     = threading.Lock()
        self._stop     = threading.Event()
        self._pipeline = None

    def _pipeline_desc(self) -> str:
        src = f"v4l2src device={VIDEO_DEVICE} io-mode=2"
        if CAPTURE_FORMAT == "raw":
            src += (
                f" ! video/x-raw,width={CAPTURE_WIDTH},height={CAPTURE_HEIGHT},"
                f"framerate={SENSOR_FPS}/1"
            )
        else:
            src += (
                f" ! image/jpeg,width={CAPTURE_WIDTH},height={CAPTURE_HEIGHT},"
                f"framerate={SENSOR_FPS}/1 ! jpegdec"
            )
        return (
            f"{src} ! videoconvert ! video/x-raw,format=BGR ! "
            f"appsink name=sink emit-signals=false max-buffers=2 drop=true sync=false"
        )

    def start(self):
        t = threading.Thread(target=self._run, daemon=True, name=f"v4l2-{self.cam_id}")
        t.start()

    def latest(self) -> tuple[Optional[np.ndarray], int]:
        with self._lock:
            return self._latest, self._seq

    def stop(self):
        self._stop.set()
        if self._pipeline is not None:
            self._pipeline.set_state(Gst.State.NULL)

    def _run(self):
        while not self._stop.is_set():
            desc = self._pipeline_desc()
            log.info("[%s] Starting V4L2 capture on %s: %s", self.cam_id, VIDEO_DEVICE, desc)
            try:
                self._pipeline = Gst.parse_launch(desc)
                sink = self._pipeline.get_by_name("sink")
                self._pipeline.set_state(Gst.State.PLAYING)
                self._pull_loop(sink)
            except Exception as e:
                log.error("[%s] V4L2 pipeline error: %s", self.cam_id, e)
            finally:
                if self._pipeline is not None:
                    self._pipeline.set_state(Gst.State.NULL)
                    self._pipeline = None
            if not self._stop.is_set():
                log.warning("[%s] Capture ended — restarting in 3s", self.cam_id)
                time.sleep(3)

    def _pull_loop(self, sink):
        while not self._stop.is_set():
            sample = sink.emit("pull-sample")
            if sample is None:
                return  # EOS, device unplugged, or pipeline stopped
            buf = sample.get_buffer()
            caps = sample.get_caps().get_structure(0)
            w, h = caps.get_value("width"), caps.get_value("height")
            ok, mapinfo = buf.map(Gst.MapFlags.READ)
            if not ok:
                continue
            try:
                frame = np.frombuffer(mapinfo.data, np.uint8).reshape((h, w, 3)).copy()
            finally:
                buf.unmap(mapinfo)
            with self._lock:
                self._latest = frame
                self._seq += 1


# ── RTSP publisher (raw BGR → ffmpeg H264 → MediaMTX) ─────────────────────────

class RtspPublisher:
    """Pushes frames from a V4L2Reader into an ffmpeg → RTSP (MediaMTX) pipeline."""

    def __init__(self, cam_id: str, reader: V4L2Reader):
        self.cam_id   = cam_id
        self.reader   = reader
        self._pushed  = 0
        self._ffmpeg  = None
        self._running = False

    def ensure_running(self):
        if self._running:
            return
        rtsp_url = f"rtsp://{RTSP_HOST}:{RTSP_PORT}/{UAV_ID}/{self.cam_id}"
        self._ffmpeg = subprocess.Popen(
            [
                "ffmpeg", "-y", "-f", "rawvideo",
                "-pix_fmt", "bgr24", "-s", f"{CAPTURE_WIDTH}x{CAPTURE_HEIGHT}",
                "-r", str(SENSOR_FPS),
                "-i", "pipe:0",
                "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                "-b:v", f"{RTSP_BITRATE}k",
                "-g", str(SENSOR_FPS * 2),
                "-f", "rtsp", "-rtsp_transport", "tcp",
                rtsp_url,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._running = True
        log.info("[%s] RTSP pipeline %s → %s", self.cam_id,
                  "started" if self._pushed == 0 else "restarted", rtsp_url)

    def teardown(self):
        if not self._running:
            return
        self._running = False
        if self._ffmpeg:
            self._ffmpeg.stdin.close()
            self._ffmpeg.wait(timeout=5)
            self._ffmpeg = None

    def push_latest(self, seq_seen: int) -> int:
        frame, seq = self.reader.latest()
        if frame is None or seq == seq_seen:
            return seq_seen
        if not self._running or not self._ffmpeg or self._ffmpeg.poll() is not None:
            self._running = False
            return seq_seen
        try:
            self._ffmpeg.stdin.write(frame.tobytes())
        except (BrokenPipeError, OSError):
            self._running = False
            return seq_seen
        self._pushed += 1
        if self._pushed == 1:
            log.info("[%s] First frame pushed to RTSP", self.cam_id)
        elif self._pushed % 300 == 0:
            log.info("[%s] Pushed %d frames", self.cam_id, self._pushed)
        return seq

    def stop(self):
        self.teardown()


# ── MQTT publisher ─────────────────────────────────────────────────────────────

class MqttPublisher:
    """Publishes JPEG frames to MQTT from a V4L2Reader."""

    def __init__(self, cam_id: str, reader: V4L2Reader, client: mqtt.Client):
        self.cam_id = cam_id
        self.reader = reader
        self.client = client
        self.topic  = f"uav/{UAV_ID}/camera/{cam_id}/frame"
        self._last  = -1
        self._total = 0

    def publish_latest(self) -> None:
        frame, seq = self.reader.latest()
        if frame is None or seq == self._last:
            return
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        self.client.publish(self.topic, buf.tobytes(), qos=0)
        self._last   = seq
        self._total += 1
        if self._total == 1:
            log.info("[%s] First frame published to MQTT (%d bytes)", self.cam_id, len(buf.tobytes()))
        elif self._total % 300 == 0:
            log.info("[%s] Published %d frames", self.cam_id, self._total)


def make_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"usb-camera-bridge-{UAV_ID}-{CAMERA_ID}",
    )

    def on_connect(c, userdata, flags, rc, props):
        if rc == 0:
            log.info("MQTT connected to %s:%d", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
        else:
            log.error("MQTT connect failed: rc=%s", rc)

    client.on_connect = on_connect
    return client


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if not GST_AVAILABLE:
        log.error("GStreamer Python bindings are not installed — cannot capture from V4L2")
        return

    Gst.init(None)
    list_v4l2_devices()

    mqtt_client = make_mqtt_client()
    mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    mqtt_client.loop_start()

    log.info("=" * 60)
    log.info("USB CAMERA BRIDGE")
    log.info("  Mode:    %s", "RTSP" if USE_RTSP else "MQTT")
    log.info("  UAV:     %s | Camera: %s", UAV_ID, CAMERA_ID)
    log.info("  Device:  %s (%s, %dx%d @ %d FPS)",
              VIDEO_DEVICE, CAPTURE_FORMAT, CAPTURE_WIDTH, CAPTURE_HEIGHT, SENSOR_FPS)
    if USE_RTSP:
        log.info("  RTSP:    %s:%d  bitrate=%d kbps", RTSP_HOST, RTSP_PORT, RTSP_BITRATE)
    else:
        cap = f"capped at {MQTT_MAX_FPS:.0f} FPS" if MQTT_MAX_FPS > 0 else "uncapped"
        log.info("  MQTT:    quality=%d  %s", JPEG_QUALITY, cap)
    log.info("=" * 60)

    reader = V4L2Reader(CAMERA_ID)
    reader.start()

    if USE_RTSP:
        publisher = RtspPublisher(CAMERA_ID, reader)
        seq_seen = -1
        try:
            while True:
                if reader.latest()[0] is not None:
                    publisher.ensure_running()
                    seq_seen = publisher.push_latest(seq_seen)
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            publisher.stop()
    else:
        publisher = MqttPublisher(CAMERA_ID, reader, mqtt_client)
        mqtt_interval = (1.0 / MQTT_MAX_FPS) if MQTT_MAX_FPS > 0 else 0
        try:
            while True:
                publisher.publish_latest()
                time.sleep(mqtt_interval or 0.001)
        except KeyboardInterrupt:
            pass

    reader.stop()
    mqtt_client.loop_stop()
    log.info("Shutdown complete")


if __name__ == "__main__":
    main()
