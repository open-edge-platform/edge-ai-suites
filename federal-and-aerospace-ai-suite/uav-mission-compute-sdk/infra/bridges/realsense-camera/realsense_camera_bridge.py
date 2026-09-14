#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
RealSense Camera Bridge — Intel RealSense depth camera (D400 series) → RTSP (or MQTT).

Drop-in sibling of infra/bridges/usb-camera/usb_camera_bridge.py: instead of a
plain V4L2 webcam, this captures from an Intel RealSense camera via the
RealSense SDK (pyrealsense2) — the active-infrared stereo pair (850nm
illuminated, so it senses beyond the visible spectrum, including in low/zero
ambient light) and the depth stream derived from it. Each enabled stream is
republished the same way the other bridges do:
  - RTSP mode (default): colorized/grayscale frames are piped to ffmpeg, which
    encodes H264 and pushes to MediaMTX via RTSP ANNOUNCE
    (rtsp://mediamtx:8554/<uav>/<camera_id>), so vision-processor /
    edge-ai-showcase can consume it unchanged.
  - MQTT mode: encodes JPEG and publishes frame-by-frame to MQTT.

In both modes, live depth statistics (min/max/mean distance in meters) are
also published to MQTT so the depth data can be consumed as metrics, not just
as an image.

Enumerate attached RealSense devices on the host with:
    rs-enumerate-devices --short

Configuration is via environment variables (see README / docker-compose.yml).
"""

import json
import logging
import os
import subprocess
import threading
import time
from typing import Optional

import cv2
import numpy as np
import paho.mqtt.client as mqtt
import pyrealsense2 as rs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("realsense-camera-bridge")

# ── Core config ───────────────────────────────────────────────────────────────
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
UAV_ID           = os.getenv("UAV_ID", "uav-1")

# ── RealSense capture config ──────────────────────────────────────────────────
RS_SERIAL   = os.getenv("RS_SERIAL", "")  # optional — pin to one device when several are attached
RS_WIDTH    = int(os.getenv("RS_WIDTH", "640"))
RS_HEIGHT   = int(os.getenv("RS_HEIGHT", "480"))
RS_FPS      = int(os.getenv("RS_FPS", "30"))
ENABLE_IR    = os.getenv("ENABLE_IR", "true").lower() == "true"
ENABLE_DEPTH = os.getenv("ENABLE_DEPTH", "true").lower() == "true"
CAMERA_ID_IR    = os.getenv("CAMERA_ID_IR", "ir")
CAMERA_ID_DEPTH = os.getenv("CAMERA_ID_DEPTH", "depth")

# ── RTSP config ────────────────────────────────────────────────────────────────
USE_RTSP     = os.getenv("USE_RTSP", "true").lower() == "true"
RTSP_HOST    = os.getenv("RTSP_HOST", "mediamtx")
RTSP_PORT    = int(os.getenv("RTSP_PORT", "8554"))
RTSP_BITRATE = int(os.getenv("RTSP_BITRATE", "2000"))  # kbps

# ── MQTT mode config ───────────────────────────────────────────────────────────
JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))
MQTT_MAX_FPS = float(os.getenv("MQTT_MAX_FPS", "0"))

# ── Depth stats config ─────────────────────────────────────────────────────────
DEPTH_STATS_INTERVAL_S = float(os.getenv("DEPTH_STATS_INTERVAL_S", "1.0"))


def list_realsense_devices() -> None:
    """Best-effort log of attached RealSense devices, for diagnostics."""
    try:
        devices = rs.context().query_devices()
        if len(devices) == 0:
            log.warning("No RealSense devices detected")
        for d in devices:
            log.info(
                "RealSense device: %s (serial=%s, fw=%s)",
                d.get_info(rs.camera_info.name),
                d.get_info(rs.camera_info.serial_number),
                d.get_info(rs.camera_info.firmware_version),
            )
    except Exception as e:
        log.warning("Could not enumerate RealSense devices (%s)", e)


# ── RealSense reader (pyrealsense2 pipeline → IR/depth frames) ────────────────

class RealSenseReader:
    """Captures the latest IR + depth frames from a RealSense camera in its own thread."""

    def __init__(self):
        self._latest_ir: Optional[np.ndarray] = None
        self._latest_depth_bgr: Optional[np.ndarray] = None
        self._latest_depth_raw: Optional[np.ndarray] = None
        self._depth_scale = 0.001  # meters/unit — overwritten once the device reports it
        self._seq_ir    = 0
        self._seq_depth = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._colorizer = rs.colorizer()

    def start(self):
        t = threading.Thread(target=self._run, daemon=True, name="realsense-reader")
        t.start()

    def latest_ir(self) -> tuple[Optional[np.ndarray], int]:
        with self._lock:
            return self._latest_ir, self._seq_ir

    def latest_depth(self) -> tuple[Optional[np.ndarray], int]:
        with self._lock:
            return self._latest_depth_bgr, self._seq_depth

    def depth_stats(self) -> Optional[dict]:
        """Min/max/mean distance in meters over the latest depth frame (valid pixels only)."""
        with self._lock:
            raw, seq = self._latest_depth_raw, self._seq_depth
        if raw is None:
            return None
        valid = raw[raw > 0]
        if valid.size == 0:
            return {"seq": seq, "min_m": None, "max_m": None, "mean_m": None, "valid_pixels": 0}
        meters = valid.astype(np.float32) * self._depth_scale
        return {
            "seq": seq,
            "min_m": round(float(meters.min()), 3),
            "max_m": round(float(meters.max()), 3),
            "mean_m": round(float(meters.mean()), 3),
            "valid_pixels": int(valid.size),
        }

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            pipeline = rs.pipeline()
            config = rs.config()
            if RS_SERIAL:
                config.enable_device(RS_SERIAL)
            if ENABLE_IR:
                config.enable_stream(rs.stream.infrared, 1, RS_WIDTH, RS_HEIGHT, rs.format.y8, RS_FPS)
            if ENABLE_DEPTH:
                config.enable_stream(rs.stream.depth, RS_WIDTH, RS_HEIGHT, rs.format.z16, RS_FPS)
            try:
                log.info(
                    "Starting RealSense pipeline (ir=%s depth=%s, %dx%d @ %d FPS)",
                    ENABLE_IR, ENABLE_DEPTH, RS_WIDTH, RS_HEIGHT, RS_FPS,
                )
                profile = pipeline.start(config)
                if ENABLE_DEPTH:
                    depth_sensor = profile.get_device().first_depth_sensor()
                    self._depth_scale = depth_sensor.get_depth_scale()
                self._pull_loop(pipeline)
            except Exception as e:
                log.error("RealSense pipeline error: %s", e)
            finally:
                try:
                    pipeline.stop()
                except Exception:
                    pass
            if not self._stop.is_set():
                log.warning("Capture ended — restarting in 3s")
                time.sleep(3)

    def _pull_loop(self, pipeline):
        while not self._stop.is_set():
            try:
                frames = pipeline.wait_for_frames(timeout_ms=5000)
            except RuntimeError as e:
                log.warning("wait_for_frames timed out (%s)", e)
                return
            with self._lock:
                if ENABLE_IR:
                    ir_frame = frames.get_infrared_frame(1)
                    if ir_frame:
                        ir = np.asanyarray(ir_frame.get_data())
                        self._latest_ir = cv2.cvtColor(ir, cv2.COLOR_GRAY2BGR)
                        self._seq_ir += 1
                if ENABLE_DEPTH:
                    depth_frame = frames.get_depth_frame()
                    if depth_frame:
                        self._latest_depth_raw = np.asanyarray(depth_frame.get_data())
                        colorized = self._colorizer.colorize(depth_frame)
                        self._latest_depth_bgr = np.asanyarray(colorized.get_data())
                        self._seq_depth += 1


# ── RTSP publisher (BGR frames → ffmpeg H264 → MediaMTX) ──────────────────────

class RtspPublisher:
    """Pushes frames from a `latest() -> (frame, seq)` source into an ffmpeg → RTSP pipeline."""

    def __init__(self, cam_id: str, latest_fn):
        self.cam_id    = cam_id
        self.latest_fn = latest_fn
        self._last_seq = -1
        self._pushed   = 0
        self._ffmpeg   = None
        self._running  = False

    def ensure_running(self):
        if self._running:
            return
        rtsp_url = f"rtsp://{RTSP_HOST}:{RTSP_PORT}/{UAV_ID}/{self.cam_id}"
        self._ffmpeg = subprocess.Popen(
            [
                "ffmpeg", "-y", "-f", "rawvideo",
                "-pix_fmt", "bgr24", "-s", f"{RS_WIDTH}x{RS_HEIGHT}",
                "-r", str(RS_FPS),
                "-i", "pipe:0",
                "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
                "-b:v", f"{RTSP_BITRATE}k",
                "-g", str(RS_FPS * 2),
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

    def push_latest(self) -> None:
        frame, seq = self.latest_fn()
        if frame is None or seq == self._last_seq:
            return
        if not self._running or not self._ffmpeg or self._ffmpeg.poll() is not None:
            self._running = False
            return
        try:
            self._ffmpeg.stdin.write(frame.tobytes())
        except (BrokenPipeError, OSError):
            self._running = False
            return
        self._last_seq = seq
        self._pushed += 1
        if self._pushed == 1:
            log.info("[%s] First frame pushed to RTSP", self.cam_id)
        elif self._pushed % 300 == 0:
            log.info("[%s] Pushed %d frames", self.cam_id, self._pushed)

    def stop(self):
        self.teardown()


# ── MQTT publishers ────────────────────────────────────────────────────────────

class MqttPublisher:
    """Publishes JPEG frames to MQTT from a `latest() -> (frame, seq)` source."""

    def __init__(self, cam_id: str, latest_fn, client: mqtt.Client):
        self.cam_id    = cam_id
        self.latest_fn = latest_fn
        self.client    = client
        self.topic     = f"uav/{UAV_ID}/camera/{cam_id}/frame"
        self._last     = -1
        self._total    = 0

    def publish_latest(self) -> None:
        frame, seq = self.latest_fn()
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
        client_id=f"realsense-camera-bridge-{UAV_ID}",
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
    if not ENABLE_IR and not ENABLE_DEPTH:
        log.error("Both ENABLE_IR and ENABLE_DEPTH are false — nothing to capture")
        return

    list_realsense_devices()

    mqtt_client = make_mqtt_client()
    mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT)
    mqtt_client.loop_start()

    log.info("=" * 60)
    log.info("REALSENSE CAMERA BRIDGE")
    log.info("  Mode:    %s", "RTSP" if USE_RTSP else "MQTT")
    log.info("  UAV:     %s", UAV_ID)
    log.info("  IR:      %s (camera_id=%s)", ENABLE_IR, CAMERA_ID_IR)
    log.info("  Depth:   %s (camera_id=%s)", ENABLE_DEPTH, CAMERA_ID_DEPTH)
    log.info("  Capture: %dx%d @ %d FPS", RS_WIDTH, RS_HEIGHT, RS_FPS)
    if USE_RTSP:
        log.info("  RTSP:    %s:%d  bitrate=%d kbps", RTSP_HOST, RTSP_PORT, RTSP_BITRATE)
    else:
        cap = f"capped at {MQTT_MAX_FPS:.0f} FPS" if MQTT_MAX_FPS > 0 else "uncapped"
        log.info("  MQTT:    quality=%d  %s", JPEG_QUALITY, cap)
    log.info("=" * 60)

    reader = RealSenseReader()
    reader.start()

    depth_stats_topic = f"uav/{UAV_ID}/camera/{CAMERA_ID_DEPTH}/depth_stats"
    last_stats_at = 0.0

    def maybe_publish_depth_stats():
        nonlocal last_stats_at
        if not ENABLE_DEPTH:
            return
        now = time.time()
        if now - last_stats_at < DEPTH_STATS_INTERVAL_S:
            return
        stats = reader.depth_stats()
        if stats is not None:
            mqtt_client.publish(depth_stats_topic, json.dumps(stats), qos=0)
        last_stats_at = now

    if USE_RTSP:
        publishers = []
        if ENABLE_IR:
            publishers.append(RtspPublisher(CAMERA_ID_IR, reader.latest_ir))
        if ENABLE_DEPTH:
            publishers.append(RtspPublisher(CAMERA_ID_DEPTH, reader.latest_depth))
        try:
            while True:
                for pub in publishers:
                    frame, _ = pub.latest_fn()
                    if frame is not None:
                        pub.ensure_running()
                        pub.push_latest()
                maybe_publish_depth_stats()
                time.sleep(0.001)
        except KeyboardInterrupt:
            pass
        finally:
            for pub in publishers:
                pub.stop()
    else:
        mqtt_publishers = []
        if ENABLE_IR:
            mqtt_publishers.append(MqttPublisher(CAMERA_ID_IR, reader.latest_ir, mqtt_client))
        if ENABLE_DEPTH:
            mqtt_publishers.append(MqttPublisher(CAMERA_ID_DEPTH, reader.latest_depth, mqtt_client))
        mqtt_interval = (1.0 / MQTT_MAX_FPS) if MQTT_MAX_FPS > 0 else 0
        try:
            while True:
                for pub in mqtt_publishers:
                    pub.publish_latest()
                maybe_publish_depth_stats()
                time.sleep(mqtt_interval or 0.001)
        except KeyboardInterrupt:
            pass

    reader.stop()
    mqtt_client.loop_stop()
    log.info("Shutdown complete")


if __name__ == "__main__":
    main()
