# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Monitors UAV ARMED/DISARMED status via MAVLink and starts/stops DL Streamer
pipelines accordingly:
  - ARMED    -> POST to start each configured pipeline
  - DISARMED -> DELETE each pipeline using its stored instance_id

Usage:
  python3 pipeline_manager.py --sink rtsp       # RTSP output (default)
  python3 pipeline_manager.py --sink udp        # UDP sink output
"""

import argparse
import json
import os
import time

import requests
from pymavlink import mavutil

# ── Constants ─────────────────────────────────────────────────────────────────

CONNECTION_STRING   = "udpin:0.0.0.0:14541"
PIPELINE_BASE_URL   = "http://localhost:8081/pipelines/user_defined_pipelines"
PIPELINE_DELETE_URL = "http://localhost:8081/pipelines/{instance_id}"
MODEL_PATH          = (
    "/home/pipeline-server/resources/models/"
    "yolov8n-visdrone/best_openvino_model/best.xml"
)
# Passed via make start-rtsp DEVICE=cpu|gpu|npu|all; default is gpu.
PIPELINE_DEVICE = os.getenv("PIPELINE_DEVICE", "gpu").lower()

# ── Pipeline definitions ──────────────────────────────────────────────────────

RTSP_PIPELINES = [
    {"name": "uav_object_detection_cpu", "frame_path": "uav-mavlink-cpu", "device": "CPU"},
    {"name": "uav_object_detection_gpu", "frame_path": "uav-mavlink-gpu", "device": "GPU"},
    {"name": "uav_object_detection_npu", "frame_path": "uav-mavlink-npu", "device": "NPU"},
]

UDP_PIPELINES = [
    {"name": "uav_udpsink_cpu", "frame_path": "uav-mavlink-cpu", "device": "CPU", "port": 5600},
    {"name": "uav_udpsink_gpu", "frame_path": "uav-mavlink-gpu", "device": "GPU", "port": 5601},
    {"name": "uav_udpsink_npu", "frame_path": "uav-mavlink-npu", "device": "NPU", "port": 5602},
]

# ── Payload builders ──────────────────────────────────────────────────────────

def _build_rtsp_payload(pipeline: dict) -> dict:
    return {
        "destination": {
            "metadata": {
                "type": "file",
                "path": "/tmp/results.jsonl",
                "format": "json-lines",
            },
            "frame": {
                "type": "rtsp",
                "path": pipeline["frame_path"],
            },
        },
        "parameters": {
            "detection-properties": {
                "model": MODEL_PATH,
                "device": pipeline["device"],
            }
        },
    }


def _build_udp_payload(pipeline: dict) -> dict:
    return {
        "destination": {
            "metadata": {
                "type": "file",
                "path": "/tmp/results.jsonl",
                "format": "json-lines",
            },
        },
        "parameters": {
            "detection-properties": {
                "model": MODEL_PATH,
                "device": pipeline["device"],
            }
        },
    }

# ── Pipeline lifecycle ────────────────────────────────────────────────────────

def _filter_by_device(pipelines: list[dict], device: str) -> list[dict]:
    """Return pipelines matching device; 'all' returns the full list."""
    if device == "all":
        return pipelines
    filtered = [p for p in pipelines if p["device"].lower() == device]
    if not filtered:
        print(f"[config] Warning: no pipeline for device='{device}' — defaulting to GPU.")
        return [p for p in pipelines if p["device"] == "GPU"]
    return filtered


running_instance_ids: list[str] = []


def start_pipelines(pipelines: list[dict], build_payload) -> None:
    """POST all configured pipelines and record their instance_ids."""
    global running_instance_ids
    running_instance_ids = []

    npu_device = os.getenv("NPU_DEVICE", "/dev/null")
    for pipeline in pipelines:
        if pipeline["device"] == "NPU" and npu_device == "/dev/null":
            print(f"[pipeline] Skipping '{pipeline['name']}': NPU_DEVICE not available.")
            continue

        url     = f"{PIPELINE_BASE_URL}/{pipeline['name']}"
        payload = build_payload(pipeline)
        try:
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=10,
            )
            print(f"[pipeline] Start '{pipeline['name']}' → {resp.status_code}: {resp.text}")
            if resp.status_code == 200:
                try:
                    instance_id = json.loads(resp.text)
                except (json.JSONDecodeError, ValueError):
                    instance_id = resp.text.strip().strip('"')
                if instance_id:
                    running_instance_ids.append(instance_id)
        except requests.RequestException as exc:
            print(f"[pipeline] Failed to start '{pipeline['name']}': {exc}")


def _print_stream_urls(pipelines: list[dict], sink: str) -> None:
    host_ip = os.getenv("HOST_IP", "127.0.0.1")
    npu_device = os.getenv("NPU_DEVICE", "/dev/null")
    active = [p for p in pipelines if p["device"] != "NPU" or npu_device != "/dev/null"]
    if sink == "rtsp":
        urls = "\n".join(f"  rtsp://{host_ip}:8555/{p['frame_path']}" for p in active)
        print(f"RTSP streams available at:\n{urls}")
    else:
        urls = "\n".join(f"  {p['device']}: udp://0.0.0.0:{p['port']}" for p in active)
        print(f"UDP streams available at:\n{urls}")


def stop_pipelines() -> None:
    """DELETE all currently tracked pipeline instances."""
    global running_instance_ids
    if not running_instance_ids:
        print("[pipeline] No running instances; nothing to stop.")
        return

    for instance_id in running_instance_ids:
        url = PIPELINE_DELETE_URL.format(instance_id=instance_id)
        try:
            resp = requests.delete(url, timeout=10)
            print(f"[pipeline] Stop '{instance_id}' → {resp.status_code}: {resp.text}")
        except requests.RequestException as exc:
            print(f"[pipeline] Failed to stop '{instance_id}': {exc}")

    running_instance_ids = []

# ── Main monitor loop ─────────────────────────────────────────────────────────

def monitor_and_control(sink: str) -> None:
    pipelines     = RTSP_PIPELINES if sink == "rtsp" else UDP_PIPELINES
    pipelines     = _filter_by_device(pipelines, PIPELINE_DEVICE)
    build_payload = _build_rtsp_payload if sink == "rtsp" else _build_udp_payload

    print(f"[config] Sink mode : {sink.upper()}")
    print(f"[config] Device    : {PIPELINE_DEVICE.upper()}")
    print(f"[config] Pipelines : {[p['name'] for p in pipelines]}")
    print(f"Connecting to {CONNECTION_STRING}...")

    master = mavutil.mavlink_connection(CONNECTION_STRING)
    print("Waiting for heartbeat...")
    master.wait_heartbeat()
    print(f"Heartbeat received from System {master.target_system} "
          f"Component {master.target_component}")

    last_armed_state = None
    print("Monitoring ARMED/DISARMED status. Press Ctrl+C to stop.\n")

    try:
        while True:
            msg = master.recv_match(type="HEARTBEAT", blocking=True)
            if not msg:
                time.sleep(0.01)
                continue

            is_armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)

            if is_armed != last_armed_state:
                if is_armed:
                    print("Vehicle Status: ARMED → starting pipelines")
                    start_pipelines(pipelines, build_payload)
                    _print_stream_urls(pipelines, sink)
                else:
                    print("Vehicle Status: DISARMED → stopping pipelines")
                    stop_pipelines()
                last_armed_state = is_armed

            time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nInterrupted — stopping active pipelines before exit.")
        if running_instance_ids:
            stop_pipelines()

# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="MAVLink-triggered DL Streamer pipeline manager"
    )
    parser.add_argument(
        "--sink",
        choices=["rtsp", "udp"],
        default="rtsp",
        help="Output sink type: 'rtsp' (default) or 'udp'",
    )
    args = parser.parse_args()
    monitor_and_control(args.sink)


if __name__ == "__main__":
    main()
