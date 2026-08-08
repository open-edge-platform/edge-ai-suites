"""
Monitors drone ARMED/DISARMED status via MAVLink and starts/stops the
DL Streamer pipeline (server) accordingly:
  - ARMED    -> POST to start the pipeline (like pipe.py)
  - DISARMED -> DELETE to stop the pipeline (using the instance_id
                returned when it was started)
"""

import json
import time

import requests
from pymavlink import mavutil

CONNECTION_STRING = 'udpin:0.0.0.0:14540'

PIPELINE_START_URL = (
    "http://localhost:8081/pipelines/user_defined_pipelines/"
    "drone_object_detection_cpu"
)
PIPELINE_DELETE_URL_TMPL = "http://localhost:8081/pipelines/{instance_id}"

PIPELINE_PAYLOAD = {
    "destination": {
        "metadata": {
            "type": "file",
            "path": "/tmp/results.jsonl",
            "format": "json-lines"
        },
        "frame": {
            "type": "rtsp",
            "path": "drone-mavlink-cpu"
        }
    },
    "parameters": {
        "detection-properties": {
            "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
            "device": "CPU"
        }
    }
}


def start_pipeline():
    """POST request to start the pipeline. Returns instance_id or None."""
    try:
        response = requests.post(
            PIPELINE_START_URL,
            headers={"Content-Type": "application/json"},
            json=PIPELINE_PAYLOAD,
            timeout=10,
        )
        print(f"[pipeline] Start status: {response.status_code}, response: {response.text}")
        if response.status_code == 200:
            try:
                instance_id = json.loads(response.text)
            except (json.JSONDecodeError, ValueError):
                instance_id = response.text.strip().strip('"')
            return instance_id
        return None
    except requests.RequestException as exc:
        print(f"[pipeline] Failed to start pipeline: {exc}")
        return None


def stop_pipeline(instance_id):
    """DELETE request to stop the pipeline given its instance_id."""
    if not instance_id:
        print("[pipeline] No instance_id available; nothing to stop.")
        return
    url = PIPELINE_DELETE_URL_TMPL.format(instance_id=instance_id)
    try:
        response = requests.delete(url, timeout=10)
        print(f"[pipeline] Stop status: {response.status_code}, response: {response.text}")
    except requests.RequestException as exc:
        print(f"[pipeline] Failed to stop pipeline: {exc}")


def monitor_and_control():
    print(f"Connecting to {CONNECTION_STRING}...")
    master = mavutil.mavlink_connection(CONNECTION_STRING)

    print("Waiting for heartbeat...")
    master.wait_heartbeat()
    print(f"Heartbeat received from System {master.target_system} Component {master.target_component}")

    current_instance_id = None
    last_armed_state = None  # None = unknown, True/False = last known state

    print("Monitoring ARMED/DISARMED status. Press Ctrl+C to stop.\n")
    try:
        while True:
            msg = master.recv_match(type='HEARTBEAT', blocking=True)
            if not msg:
                time.sleep(0.01)
                continue

            base_mode = msg.base_mode
            is_armed = bool(base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

            # Only act on state transitions.
            if is_armed != last_armed_state:
                if is_armed:
                    print("Vehicle Status: ARMED -> starting pipeline")
                    current_instance_id = start_pipeline()
                else:
                    print("Vehicle Status: DISARMED -> stopping pipeline")
                    stop_pipeline(current_instance_id)
                    current_instance_id = None

                last_armed_state = is_armed

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nStopping monitor.")
        # Ensure pipeline isn't left running if we exit while armed.
        if current_instance_id:
            print("Cleaning up: stopping active pipeline before exit.")
            stop_pipeline(current_instance_id)


if __name__ == '__main__':
    monitor_and_control()
