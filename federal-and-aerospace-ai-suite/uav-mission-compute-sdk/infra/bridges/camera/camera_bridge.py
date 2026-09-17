#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Gazebo Camera Bridge — Unified single/multi-camera, RTSP or MQTT output.

Reads Gazebo camera frames via gz topic subprocess, then either:
  - RTSP mode: encodes H264 and pushes to MediaMTX via RTMP
  - MQTT mode: encodes JPEG and publishes frame-by-frame to MQTT

Camera configuration is fully driven by environment variables, so the same
image handles the single-camera (baylands_detection) and multi-camera
(baylands_multicam) setups.
"""

import base64
import json
import os
import subprocess
import threading
import time
import logging
from typing import Optional

import cv2
import numpy as np
import paho.mqtt.client as mqtt

try:
    import gi
    gi.require_version("Gst", "1.0")
    gi.require_version("GstApp", "1.0")
    from gi.repository import Gst, GstApp
    GST_AVAILABLE = True
except (ImportError, ValueError):
    GST_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("camera-bridge")

# ── Core config ──────────────────────────────────────────────────────────────
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
UAV_ID         = os.getenv("UAV_ID", "uav-1")
SENSOR_FPS       = int(os.getenv("SENSOR_FPS", "30"))
GZ_WORLD         = os.getenv("GZ_WORLD", "baylands_multicam")
GZ_MODEL         = os.getenv("GZ_MODEL", "x500_mono_cam_down_0")

# ── Camera config ─────────────────────────────────────────────────────────────
CAMERA_IDS = [c.strip() for c in os.getenv("CAMERA_IDS", "nadir,forward,rear").split(",")]

_sensor_map_raw = os.getenv("CAMERA_SENSORS", "")
CAMERA_SENSORS: dict[str, str] = {}
if _sensor_map_raw:
    for pair in _sensor_map_raw.split(","):
        cam, _, sensor = pair.strip().partition(":")
        if cam and sensor:
            CAMERA_SENSORS[cam.strip()] = sensor.strip()

def sensor_for(cam_id: str) -> str:
    return CAMERA_SENSORS.get(cam_id, f"imager_{cam_id}")

GZ_LINK = os.getenv("GZ_LINK", "camera_link")

# ── RTSP config ───────────────────────────────────────────────────────────────
USE_RTSP      = os.getenv("USE_RTSP", "false").lower() == "true"
RTSP_HOST     = os.getenv("RTSP_HOST", "mediamtx")
RTSP_PORT     = int(os.getenv("RTSP_PORT", "8554"))
RTSP_BITRATE  = int(os.getenv("RTSP_BITRATE", "2000"))   # kbps

# ── MQTT mode config ──────────────────────────────────────────────────────────
JPEG_QUALITY  = int(os.getenv("JPEG_QUALITY", "80"))
MQTT_MAX_FPS  = float(os.getenv("MQTT_MAX_FPS", "0"))

# ── Shared state ──────────────────────────────────────────────────────────────
_decoder      = json.JSONDecoder()
_armed        = {"value": False}


# ── Gazebo helpers ────────────────────────────────────────────────────────────

def gz_topic(cam_id: str) -> str:
    return (
        f"/world/{GZ_WORLD}/model/{GZ_MODEL}"
        f"/link/{GZ_LINK}/sensor/{sensor_for(cam_id)}/image"
    )


def wait_for_gz_topics(timeout: int = 180) -> bool:
    log.info("Waiting for Gazebo camera topics (up to %ds)…", timeout)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(
                ["gz", "topic", "-l"], capture_output=True, text=True, timeout=10
            )
            for cam_id in CAMERA_IDS:
                if gz_topic(cam_id) in result.stdout:
                    log.info("Found topic for camera '%s'", cam_id)
                    return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        time.sleep(3)
    log.error("No camera topics appeared after %ds", timeout)
    return False


def decode_frame(msg: dict) -> Optional[np.ndarray]:
    """Decode a Gazebo JSON image message to an OpenCV BGR ndarray."""
    w, h = msg.get("width", 0), msg.get("height", 0)
    raw_str = msg.get("data", "")
    if not w or not h or not raw_str:
        return None
    try:
        raw = base64.b64decode(raw_str)
    except Exception:
        raw = raw_str.encode("latin-1")

    if len(raw) == w * h * 4:
        arr = np.frombuffer(raw, np.uint8).reshape((h, w, 4))
        return cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    if len(raw) == w * h * 3:
        arr = np.frombuffer(raw, np.uint8).reshape((h, w, 3))
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
    return None


# ── MQTT helpers ──────────────────────────────────────────────────────────────

def make_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"camera-bridge-{UAV_ID}",
    )

    def on_connect(c, userdata, flags, rc, props):
        if rc == 0:
            log.info("MQTT connected to %s:%d", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
            c.subscribe(f"uav/{UAV_ID}/telemetry/status")
        else:
            log.error("MQTT connect failed: rc=%s", rc)

    def on_message(c, userdata, msg):
        if "telemetry/status" in msg.topic:
            try:
                data = json.loads(msg.payload)
                prev = _armed["value"]
                _armed["value"] = bool(data.get("armed", False))
                if _armed["value"] != prev:
                    log.info("UAV %s", "ARMED — cameras active" if _armed["value"] else "DISARMED — cameras paused")
            except Exception:
                pass

    client.on_connect = on_connect
    client.on_message = on_message
    return client


# ── Per-camera GZ reader ──────────────────────────────────────────────────────

class GzReader:
    """Reads the latest frame from a Gazebo topic subprocess in its own thread."""

    def __init__(self, cam_id: str):
        self.cam_id  = cam_id
        self._topic  = gz_topic(cam_id)
        self._latest: Optional[np.ndarray] = None
        self._seq    = 0
        self._lock   = threading.Lock()
        self._stop   = threading.Event()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True, name=f"gz-{self.cam_id}")
        t.start()

    def latest(self) -> tuple[Optional[np.ndarray], int]:
        with self._lock:
            return self._latest, self._seq

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            log.info("[%s] Starting gz stream: %s", self.cam_id, self._topic)
            try:
                proc = subprocess.Popen(
                    ["gz", "topic", "-e", "-t", self._topic, "--json-output"],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0,
                )
                self._read_loop(proc)
                proc.kill()
                proc.wait()
            except Exception as e:
                log.error("[%s] gz stream error: %s", self.cam_id, e)
            if not self._stop.is_set():
                log.warning("[%s] Stream ended — restarting in 3s", self.cam_id)
                time.sleep(3)

    def _read_loop(self, proc: subprocess.Popen):
        buf = ""
        while proc.poll() is None and not self._stop.is_set():
            chunk = proc.stdout.read(524288)
            if not chunk:
                return
            buf += chunk.decode("latin-1")
            latest_msg = None
            while True:
                buf = buf.lstrip()
                if not buf or buf[0] != "{":
                    idx = buf.find("{")
                    buf = buf[idx:] if idx != -1 else ""
                    break
                try:
                    msg, end = _decoder.raw_decode(buf)
                except ValueError:
                    break
                buf = buf[end:]
                latest_msg = msg
            if latest_msg is not None:
                frame = decode_frame(latest_msg)
                if frame is not None:
                    with self._lock:
                        self._latest = frame
                        self._seq += 1


# ── RTSP publisher (one GStreamer pipeline per camera) ───────────────────────

class RtspPublisher:
    """Pushes frames from a GzReader into a GStreamer RTMP→MediaMTX pipeline.

    Lifecycle is tied to the uav's armed state:
      - Armed:    pipeline running, frames pushed to RTMP
      - Disarmed: pipeline torn down, RTMP connection closed cleanly
    This prevents MediaMTX from timing out idle connections.
    """

    def __init__(self, cam_id: str, reader: GzReader):
        self.cam_id   = cam_id
        self.reader   = reader
        self._pushed  = 0
        self._ffmpeg  = None
        self._running = False

    def ensure_running(self):
        """Start the pipeline if not already running."""
        if self._running:
            return
        rtsp_url = f"rtsp://{RTSP_HOST}:{RTSP_PORT}/{UAV_ID}/{self.cam_id}"
        self._ffmpeg = subprocess.Popen(
            [
                "ffmpeg", "-y", "-f", "rawvideo",
                "-pix_fmt", "bgr24", "-s", "416x416",
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
        if self._pushed == 0:
            log.info("[%s] RTSP pipeline started → %s", self.cam_id, rtsp_url)
        else:
            log.info("[%s] RTSP pipeline restarted → %s", self.cam_id, rtsp_url)

    def teardown(self):
        """Stop ffmpeg and close the RTSP connection."""
        if not self._running:
            return
        self._running = False
        if self._ffmpeg:
            self._ffmpeg.stdin.close()
            self._ffmpeg.wait(timeout=5)
            self._ffmpeg = None

    def push_latest(self, seq_seen: int) -> int:
        """Push the latest frame if newer than seq_seen. Returns new seq."""
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


# ── MQTT publisher (one slot per camera) ─────────────────────────────────────

class MqttPublisher:
    """Publishes JPEG frames to MQTT from a GzReader."""

    def __init__(self, cam_id: str, reader: GzReader, client: mqtt.Client):
        self.cam_id  = cam_id
        self.reader  = reader
        self.client  = client
        self.topic   = f"uav/{UAV_ID}/camera/{cam_id}/frame"
        self._last   = -1
        self._total  = 0

    def publish_latest(self) -> None:
        if not _armed["value"]:
            return
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


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if USE_RTSP and not GST_AVAILABLE:
        log.error("USE_RTSP=true but GStreamer Python bindings are not installed")
        return

    if USE_RTSP:
        Gst.init(None)

    mqtt_client = make_mqtt_client()
    mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    mqtt_client.loop_start()

    log.info("=" * 60)
    log.info("CAMERA BRIDGE")
    log.info("  Mode:    %s", "RTSP" if USE_RTSP else "MQTT")
    log.info("  UAV:   %s", UAV_ID)
    log.info("  World:   %s | Model: %s", GZ_WORLD, GZ_MODEL)
    log.info("  Cameras: %s", ", ".join(CAMERA_IDS))
    log.info("  Sensor:  %d FPS", SENSOR_FPS)
    if USE_RTSP:
        log.info("  RTSP:    %s:%d  bitrate=%d kbps", RTSP_HOST, RTSP_PORT, RTSP_BITRATE)
    else:
        cap = f"capped at {MQTT_MAX_FPS:.0f} FPS" if MQTT_MAX_FPS > 0 else "uncapped"
        log.info("  MQTT:    quality=%d  %s", JPEG_QUALITY, cap)
    log.info("  Sensors: %s", {c: sensor_for(c) for c in CAMERA_IDS})
    log.info("=" * 60)

    if not wait_for_gz_topics():
        log.error("Aborting — no camera topics appeared")
        return

    readers = {cam: GzReader(cam) for cam in CAMERA_IDS}
    for r in readers.values():
        r.start()

    if USE_RTSP:
        publishers = {cam: RtspPublisher(cam, reader) for cam, reader in readers.items()}
        seqs = {cam: -1 for cam in publishers}

        try:
            while True:
                if _armed["value"]:
                    for cam, pub in publishers.items():
                        if pub.reader.latest()[0] is not None:
                            pub.ensure_running()
                            seqs[cam] = pub.push_latest(seqs[cam])
                else:
                    for pub in publishers.values():
                        pub.teardown()
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            for pub in publishers.values():
                pub.stop()
    else:
        publishers = {
            cam: MqttPublisher(cam, reader, mqtt_client)
            for cam, reader in readers.items()
        }
        mqtt_interval = (1.0 / MQTT_MAX_FPS) if MQTT_MAX_FPS > 0 else 0
        try:
            while True:
                for pub in publishers.values():
                    pub.publish_latest()
                if mqtt_interval:
                    time.sleep(mqtt_interval)
                else:
                    time.sleep(0.001)
        except KeyboardInterrupt:
            pass

    for r in readers.values():
        r.stop()
    mqtt_client.loop_stop()
    log.info("Shutdown complete")


if __name__ == "__main__":
    main()
