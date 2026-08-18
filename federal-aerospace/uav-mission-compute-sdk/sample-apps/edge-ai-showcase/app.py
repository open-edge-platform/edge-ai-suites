#!/usr/bin/env python3

# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""
Intel Edge AI Showcase Dashboard
Real-time multi-camera uav surveillance with performance analytics
"""

import json
import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from flask import Flask, render_template, jsonify, Response
from flask_sock import Sock
import paho.mqtt.client as mqtt

app = Flask(__name__)
sock = Sock(app)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
UAV_ID = os.getenv("UAV_ID", "uav-1")
CAMERA_IDS = ["nadir", "forward", "rear"]

# State storage
state = {
    "telemetry": {},
    "frames": {cam: None for cam in CAMERA_IDS},
    "detections": {cam: [] for cam in CAMERA_IDS},
    "stats": {
        "total_detections": 0,
        "fps": {cam: 0.0 for cam in CAMERA_IDS},
        "latency": {cam: 0.0 for cam in CAMERA_IDS},
        "frame_counts": {cam: 0 for cam in CAMERA_IDS},
    },
    "anomalies": [],
}

# Performance tracking
frame_times = {cam: deque(maxlen=30) for cam in CAMERA_IDS}
last_detection_time = {cam: 0.0 for cam in CAMERA_IDS}
detection_counts = {cam: 0 for cam in CAMERA_IDS}

# MQTT Client
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def on_connect(client, userdata, flags, reason_code, properties=None):
    log.info(f"Connected to MQTT broker: {reason_code}")
    for cam in CAMERA_IDS:
        client.subscribe(f"uav/{UAV_ID}/camera/{cam}/detections")
        client.subscribe(f"uav/{UAV_ID}/camera/{cam}/processed")
    client.subscribe(f"uav/{UAV_ID}/telemetry/#")

def on_message(client, userdata, msg):
    topic = msg.topic

    try:
        if "/camera/" in topic and "/processed" in topic:
            cam_id = topic.split("/camera/")[1].split("/")[0]
            state["frames"][cam_id] = msg.payload
            state["stats"]["frame_counts"][cam_id] += 1

        elif "/camera/" in topic and "/detections" in topic:
            cam_id = topic.split("/camera/")[1].split("/")[0]
            detections = json.loads(msg.payload)

            state["detections"][cam_id] = detections.get("objects", [])
            detection_counts[cam_id] = len(detections.get("objects", []))
            state["stats"]["total_detections"] = sum(detection_counts.values())

            now = time.time()
            frame_times[cam_id].append(now)
            last_detection_time[cam_id] = now
            if len(frame_times[cam_id]) >= 2:
                elapsed = frame_times[cam_id][-1] - frame_times[cam_id][0]
                if elapsed > 0:
                    state["stats"]["fps"][cam_id] = len(frame_times[cam_id]) / elapsed

        elif "/telemetry/" in topic:
            telem_type = topic.split("/telemetry/")[1]
            data = json.loads(msg.payload)
            state["telemetry"][telem_type] = data

    except Exception as e:
        log.warning(f"Error processing message on {topic}: {e}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# Background thread to reset stale FPS counters and detections
def reset_stale_fps():
    """Reset FPS and detections if no detections received for 2+ seconds."""
    while True:
        time.sleep(1)
        now = time.time()
        for cam in CAMERA_IDS:
            if now - last_detection_time[cam] > 2.0:
                if state["stats"]["fps"][cam] > 0:
                    state["stats"]["fps"][cam] = 0.0
                    frame_times[cam].clear()

                if detection_counts[cam] > 0:
                    detection_counts[cam] = 0
                    state["detections"][cam] = []

        state["stats"]["total_detections"] = sum(detection_counts.values())

threading.Thread(target=reset_stale_fps, daemon=True).start()

# Flask Routes

@app.route("/")
def index():
    return render_template("showcase_v2.html", cameras=CAMERA_IDS)

@app.route("/v1")
def index_v1():
    return render_template("showcase.html", cameras=CAMERA_IDS)

@app.route("/api/stats")
def api_stats():
    """Real-time statistics"""
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "fps": state["stats"]["fps"],
        "detection_count": state["stats"]["total_detections"],
        "detections_per_camera": detection_counts,
        "frame_counts": state["stats"]["frame_counts"],
        "telemetry": state["telemetry"],
    })

@app.route("/api/detections/<cam_id>")
def api_detections(cam_id):
    """Get detections for specific camera"""
    return jsonify({
        "camera_id": cam_id,
        "detections": state["detections"].get(cam_id, []),
        "fps": state["stats"]["fps"].get(cam_id, 0.0),
    })

@app.route("/video/<cam_id>")
def video_feed(cam_id):
    """MJPEG stream for camera"""
    def generate():
        while True:
            frame = state["frames"].get(cam_id)
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.033)  # ~30 FPS max

    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy",
        "mqtt_connected": mqtt_client.is_connected(),
        "cameras_active": [cam for cam in CAMERA_IDS if state["frames"][cam] is not None],
    })

# Mission control
import requests

COMPANION_BRIDGE_URL = os.getenv("COMPANION_BRIDGE_URL", "http://px4-gazebo:8080")
POST_MISSION_REBOOT = os.getenv("POST_MISSION_REBOOT", "true").lower() == "true"

mission_status_data = {"running": False, "step": "Idle", "progress": 0}
mission_lock = threading.Lock()

def _send_command(action: str, timeout: float = 15.0, **kwargs) -> tuple[bool, str]:
    """POST action directly to companion_bridge REST API."""
    try:
        req_kwargs = {"timeout": timeout}
        if kwargs:
            req_kwargs["json"] = kwargs
        resp = requests.post(
            f"{COMPANION_BRIDGE_URL}/action/{action}",
            **req_kwargs,
        )
        data = resp.json()
        if resp.ok and data.get("success"):
            return True, "ok"
        return False, data.get("error") or f"HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, "Command timed out"
    except Exception as e:
        return False, str(e)

def _wait_altitude_reached(target_m: float, tolerance: float, timeout: float, step: str, progress: int) -> bool:
    """Wait until relative altitude is within tolerance of target (metres AGL)."""
    with mission_lock:
        mission_status_data.update(running=True, step=step, progress=progress)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        alt = state["telemetry"].get("position", {}).get("relative_altitude_m", 0.0)
        if abs(alt - target_m) <= tolerance:
            return True
        time.sleep(0.5)
    return False


def _wait_for_disarm(timeout: float, step: str, progress: int) -> bool:
    """Wait until the uav is disarmed (landed and auto-disarmed)."""
    with mission_lock:
        mission_status_data.update(running=True, step=step, progress=progress)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        armed = state["telemetry"].get("status", {}).get("armed", True)
        if not armed:
            return True
        time.sleep(1)
    return False


def _wait_for_arm(timeout: float, step: str, progress: int) -> bool:
    """Wait until the uav is armed."""
    with mission_lock:
        mission_status_data.update(running=True, step=step, progress=progress)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if state["telemetry"].get("status", {}).get("armed", False):
            return True
        time.sleep(0.5)
    return False


def _wait_for_connected(timeout: float, step: str, progress: int) -> bool:
    """Wait until telemetry reports a live connection to PX4."""
    with mission_lock:
        mission_status_data.update(running=True, step=step, progress=progress)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = state["telemetry"].get("status", {})
        if status.get("connected", False) and not status.get("stale", True):
            return True
        time.sleep(1)
    return False


def _reset_dashboard_state() -> None:
    """Clear per-mission camera and inference counters for a fresh next run."""
    for cam in CAMERA_IDS:
        state["frames"][cam] = None
        state["detections"][cam] = []
        state["stats"]["fps"][cam] = 0.0
        state["stats"]["frame_counts"][cam] = 0
        detection_counts[cam] = 0
        frame_times[cam].clear()
        last_detection_time[cam] = 0.0
    state["stats"]["total_detections"] = 0
    state["anomalies"] = []


def _arm_with_retries(max_attempts: int = 6) -> tuple[bool, str]:
    """Arm with short backoff to tolerate transient post-landing denial windows."""
    last_error = "arm failed"
    for attempt in range(1, max_attempts + 1):
        with mission_lock:
            mission_status_data.update(
                running=True,
                step=f"Arming (attempt {attempt}/{max_attempts})",
                progress=5,
            )
        ok, msg = _send_command("arm", timeout=20)
        if ok and _wait_for_arm(timeout=6, step="Confirming arm", progress=8):
            return True, "ok"
        last_error = msg
        time.sleep(2)
    return False, last_error


def _recover_from_arm_denied() -> bool:
    """Reboot FCU and wait for reconnect when arm is persistently denied."""
    with mission_lock:
        mission_status_data.update(
            running=True,
            step="Recovering FCU (reboot)",
            progress=6,
        )
    ok, _ = _send_command("reboot", timeout=10)
    if not ok:
        return False
    return _wait_for_connected(timeout=60, step="Waiting for reconnect", progress=7)


def _post_mission_reset() -> None:
    """Return system to a clean ready state after a completed mission."""
    with mission_lock:
        mission_status_data.update(running=True, step="Resetting dashboard", progress=98)

    _reset_dashboard_state()

    if POST_MISSION_REBOOT:
        ok, _ = _send_command("reboot", timeout=10)
        if ok:
            _wait_for_connected(timeout=60, step="Reconnecting after reset", progress=99)
        else:
            log.warning("Post-mission reboot request failed")

    with mission_lock:
        mission_status_data.update(running=False, step="Ready", progress=0)


# Survey waypoints over Baylands objects (north, east in meters from home)
_SURVEY_WAYPOINTS = [
    (8, 0),        # Hatchback (north)
    (12, 10),      # Red hatchback (north-east)
    (0, 8),        # SUV (east)
    (-5, 12),      # Person 1 (east)
    (10, -8),      # Person 2 (south-east)
    (-10, -7),     # Pickup truck (south-west)
    (0, 0),        # Return home
]

CRUISE_ALTITUDE = 12.0  # meters above ground


def _demo_mission():
    def _set(step, progress):
        with mission_lock:
            mission_status_data.update(running=True, step=step, progress=progress)

    def _cmd(action, step, progress, **kwargs):
        _set(step, progress)
        ok, msg = _send_command(action, timeout=20, **kwargs)
        if not ok:
            raise RuntimeError(f"{action} failed: {msg}")

    try:
        # Arm (retry-friendly to handle transient commander cooldowns after land)
        armed_ok, arm_msg = _arm_with_retries(max_attempts=6)
        if not armed_ok and "COMMAND_DENIED" in arm_msg:
            recovered = _recover_from_arm_denied()
            if recovered:
                armed_ok, arm_msg = _arm_with_retries(max_attempts=8)
        if not armed_ok:
            raise RuntimeError(f"arm failed: {arm_msg}")
        time.sleep(2)

        # Takeoff to cruise altitude
        _cmd("takeoff", "Taking Off", 10, altitude=CRUISE_ALTITUDE)
        if not _wait_altitude_reached(CRUISE_ALTITUDE, tolerance=2.0, timeout=60,
                                      step=f"Climbing to {CRUISE_ALTITUDE:.0f}m", progress=15):
            raise RuntimeError("Takeoff did not reach altitude within 60s")

        time.sleep(3)

        # Fly survey pattern over objects
        num_wps = len(_SURVEY_WAYPOINTS)
        for i, (north, east) in enumerate(_SURVEY_WAYPOINTS):
            progress_pct = 20 + int(60 * i / num_wps)
            _cmd("goto", f"Waypoint {i+1}/{num_wps}", progress_pct,
                 north=north, east=east, down=-CRUISE_ALTITUDE)

            # Flight time between waypoints
            _set(f"Flying to WP {i+1}/{num_wps}", progress_pct + 2)
            time.sleep(8)

            # Hover for detection
            _set(f"Scanning WP {i+1}/{num_wps}", progress_pct + 4)
            time.sleep(4)

        # Land and wait for auto-disarm
        _cmd("land", "Landing", 85)

        if not _wait_for_disarm(timeout=40, step="Landing & disarming", progress=95):
            log.warning("Auto-disarm timed out")
            _send_command("disarm", timeout=5)

        with mission_lock:
            mission_status_data.update(running=True, step="Mission Complete", progress=100)
        log.info("Mission complete")
        _post_mission_reset()

    except Exception as e:
        log.error(f"Mission failed: {e}")
        # Only trigger emergency landing if the uav is actually armed.
        if state["telemetry"].get("status", {}).get("armed", False):
            _send_command("land", timeout=10)
            if not _wait_for_disarm(timeout=30, step="Emergency landing", progress=0):
                _send_command("disarm", timeout=5)
        with mission_lock:
            mission_status_data.update(running=False, step=f"Error: {e}", progress=0)

@app.route("/api/mission/arm", methods=["POST"])
def mission_arm():
    """Direct arm command"""
    ok, msg = _send_command("arm")
    return jsonify({"success": ok, "error": msg if not ok else None}), (200 if ok else 500)

@app.route("/api/mission/takeoff", methods=["POST"])
def mission_takeoff():
    """Direct takeoff command"""
    ok, msg = _send_command("takeoff")
    return jsonify({"success": ok, "error": msg if not ok else None}), (200 if ok else 500)

@app.route("/api/mission/start", methods=["POST"])
def start_mission():
    """Start full demo mission"""
    with mission_lock:
        if mission_status_data["running"]:
            return jsonify({"success": False, "error": "Mission already running"}), 400
        mission_status_data.update(running=True, step="Starting", progress=0)

    threading.Thread(target=_demo_mission, daemon=True).start()
    return jsonify({"success": True, "message": "Mission started"})

@app.route("/api/mission/status")
def get_mission_status():
    """Get mission status"""
    with mission_lock:
        return jsonify(mission_status_data)

if __name__ == "__main__":
    log.info("Starting Intel Edge AI Showcase Dashboard")
    log.info(f"Access at: http://0.0.0.0:5002")
    app.run(host="0.0.0.0", port=5002, debug=False, threaded=True)
