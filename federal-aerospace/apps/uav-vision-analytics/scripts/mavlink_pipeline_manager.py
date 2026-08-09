"""
Monitors drone ARMED/DISARMED status via MAVLink and starts/stops the
DL Streamer pipelines (server) accordingly:
  - ARMED    -> POST to start each pipeline (like pipe.py), keeping track
                of their instance_ids
  - DISARMED -> DELETE each pipeline using its stored instance_id

Additionally, mirrors /tmp/server.py's behavior: every MAVLink message
received is re-broadcast as a raw UDP packet on BROADCAST_OUTPUT_PORT so
other listeners (e.g. QGroundControl, other pipelines) can consume the
same telemetry stream.
"""

import json
import socket
import time

import requests
from pymavlink import mavutil

CONNECTION_STRING = 'udpin:0.0.0.0:14550'

# UDP broadcast settings (mirrors /tmp/server.py)
BROADCAST_IP = "255.255.255.255"
BROADCAST_OUTPUT_PORT = 14541

PIPELINE_BASE_URL = "http://localhost:8081/pipelines/user_defined_pipelines"
PIPELINE_DELETE_URL_TMPL = "http://localhost:8081/pipelines/{instance_id}"

MODEL_PATH = "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml"

# All pipelines to start when armed / stop when disarmed.
PIPELINES = [
    {
        "name": "drone_object_detection_cpu",
        "frame_path": "drone-mavlink-cpu",
        "device": "CPU",
    },
    {
        "name": "drone_object_detection_gpu",
        "frame_path": "drone-mavlink-gpu",
        "device": "GPU",
    },
]

# Holds the instance_ids of the currently running pipelines.
running_instance_ids = []


def build_payload(frame_path, device):
    return {
        "destination": {
            "metadata": {
                "type": "file",
                "path": "/tmp/results.jsonl",
                "format": "json-lines"
            },
            "frame": {
                "type": "rtsp",
                "path": frame_path
            }
        },
        "parameters": {
            "detection-properties": {
                "model": MODEL_PATH,
                "device": device
            }
        }
    }


def start_pipelines():
    """POST all configured pipelines and collect their instance_ids."""
    global running_instance_ids
    running_instance_ids = []

    for pipeline in PIPELINES:
        url = f"{PIPELINE_BASE_URL}/{pipeline['name']}"
        payload = build_payload(pipeline["frame_path"], pipeline["device"])
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10,
            )
            print(f"[pipeline] Start '{pipeline['name']}' status: {response.status_code}, response: {response.text}")
            if response.status_code == 200:
                try:
                    instance_id = json.loads(response.text)
                except (json.JSONDecodeError, ValueError):
                    instance_id = response.text.strip().strip('"')
                if instance_id:
                    running_instance_ids.append(instance_id)
        except requests.RequestException as exc:
            print(f"[pipeline] Failed to start '{pipeline['name']}': {exc}")


def stop_pipelines():
    """DELETE all currently tracked pipeline instances."""
    global running_instance_ids
    if not running_instance_ids:
        print("[pipeline] No running instance_ids; nothing to stop.")
        return

    for instance_id in running_instance_ids:
        url = PIPELINE_DELETE_URL_TMPL.format(instance_id=instance_id)
        try:
            response = requests.delete(url, timeout=10)
            print(f"[pipeline] Stop '{instance_id}' status: {response.status_code}, response: {response.text}")
        except requests.RequestException as exc:
            print(f"[pipeline] Failed to stop '{instance_id}': {exc}")

    running_instance_ids = []


def monitor_and_control():
    print(f"Connecting to {CONNECTION_STRING}...")
    master = mavutil.mavlink_connection(CONNECTION_STRING)

    print("Waiting for heartbeat...")
    master.wait_heartbeat()
    print(f"Heartbeat received from System {master.target_system} Component {master.target_component}")

    # UDP broadcaster (mirrors /tmp/server.py)
    broadcast_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    broadcast_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    print(f"Broadcasting MAVLink on {BROADCAST_IP}:{BROADCAST_OUTPUT_PORT}")

    current_instance_id = None
    last_armed_state = None  # None = unknown, True/False = last known state

    print("Monitoring ARMED/DISARMED status. Press Ctrl+C to stop.\n")
    try:
        while True:
            # No type filter so every message can be re-broadcast, not
            # just HEARTBEAT.
            msg = master.recv_match(blocking=True)
            if not msg:
                time.sleep(0.01)
                continue

            # Re-broadcast the raw MAVLink packet to other listeners.
            packet = msg.get_msgbuf()
            if packet:
                try:
                    broadcast_sock.sendto(packet, (BROADCAST_IP, BROADCAST_OUTPUT_PORT))
                except OSError as exc:
                    print(f"[broadcast] Failed to send packet: {exc}")

            if msg.get_type() != 'HEARTBEAT':
                continue

            base_mode = msg.base_mode
            is_armed = bool(base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

            # Only act on state transitions.
            if is_armed != last_armed_state:
                if is_armed:
                    print("Vehicle Status: ARMED -> starting pipelines")
                    start_pipelines()
                else:
                    print("Vehicle Status: DISARMED -> stopping pipelines")
                    stop_pipelines()

                last_armed_state = is_armed

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopping monitor.")
        # Ensure pipelines aren't left running if we exit while armed.
        if running_instance_ids:
            print("Cleaning up: stopping active pipelines before exit.")
            stop_pipelines()
    finally:
        broadcast_sock.close()


if __name__ == '__main__':
    monitor_and_control()
