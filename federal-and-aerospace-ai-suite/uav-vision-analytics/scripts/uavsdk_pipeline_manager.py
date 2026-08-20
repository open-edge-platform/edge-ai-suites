"""
Monitors UAV ARMED/DISARMED status via MQTT telemetry and starts/stops
the three DL Streamer pipelines defined in start_pipelines.sh accordingly:
  - armed == true  -> POST all three pipelines (nadir/CPU, forward/GPU,
                       rear/NPU), keeping track of their instance_ids
  - armed == false -> DELETE all pipelines using the stored instance_ids
"""

import argparse
import json
import subprocess
import time
import os

import paho.mqtt.client as mqtt
import requests

BROKER = "host.docker.internal"
PORT = 1884
TOPIC = "uav/uav-1/telemetry/status"

PIPELINE_BASE_URL = "http://localhost:8081/pipelines/user_defined_pipelines"
PIPELINE_DELETE_URL_TMPL = "http://localhost:8081/pipelines/{instance_id}"

MODEL_PATH = "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml"

RTSP_BASE_URL = f"rtsp://{BROKER}:8554/uav-1"
RTSP_OUTPUT_BASE_URL = f"rtsp://localhost:8555/"

# How long to wait (seconds) for ffprobe to confirm a stream is up, and how
# many times / how long to retry before giving up on a given pipeline.
RTSP_PROBE_TIMEOUT = 5
RTSP_PROBE_RETRIES = 3
RTSP_PROBE_RETRY_DELAY = 2

# Matches the three curl calls in start_pipelines.sh
PIPELINES = [
    {
        "name": "nadir_camera_rtsp_cpu",
        "frame_path": "nadir",
        "device": "CPU",
        "rtsp_url": f"{RTSP_BASE_URL}/nadir",
    },
    {
        "name": "forward_camera_rtsp_gpu",
        "frame_path": "forward",
        "device": "GPU",
        "rtsp_url": f"{RTSP_BASE_URL}/forward",
    },
    {
        "name": "rear_camera_rtsp_npu",
        "frame_path": "rear",
        "device": "NPU",
        "rtsp_url": f"{RTSP_BASE_URL}/rear",
    },
]

# Holds the instance_ids of the currently running pipelines.
running_instance_ids = []


def is_rtsp_stream_available(rtsp_url, timeout=RTSP_PROBE_TIMEOUT):
    """
    Uses ffprobe to check whether an RTSP stream is currently available.
    Returns True if ffprobe can read stream info before the timeout,
    False otherwise (stream down, unreachable, or timed out).
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-rtsp_transport", "tcp",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1",
        "-timeout", str(timeout * 1_000_000),  # ffprobe wants microseconds
        rtsp_url,
    ]
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 2,
        )
        return result.returncode == 0 and b"codec_type" in result.stdout
    except (subprocess.TimeoutExpired, OSError) as exc:
        print(f"[rtsp-check] Error probing {rtsp_url}: {exc}")
        return False


def wait_for_rtsp_stream(rtsp_url, retries=RTSP_PROBE_RETRIES, delay=RTSP_PROBE_RETRY_DELAY):
    """Retries the RTSP availability check a few times before giving up."""
    for attempt in range(1, retries + 1):
        print(f"[rtsp-check] Probing {rtsp_url} (attempt {attempt}/{retries})...")
        if is_rtsp_stream_available(rtsp_url):
            print(f"[rtsp-check] {rtsp_url} is available.")
            return True
        if attempt < retries:
            time.sleep(delay)
    print(f"[rtsp-check] {rtsp_url} is NOT available after {retries} attempts.")
    return False


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
    """POST all three pipelines and collect their instance_ids."""
    global running_instance_ids
    running_instance_ids = []

    npu_device = os.getenv("NPU_DEVICE", "/dev/null")
    for pipeline in PIPELINES:
        if pipeline["device"] == "NPU" and npu_device == "/dev/null":
            print(f"[pipeline] Skipping '{pipeline['name']}': NPU_DEVICE not available.")
            continue

        if not wait_for_rtsp_stream(pipeline["rtsp_url"]):
            print(f"[pipeline] Skipping '{pipeline['name']}': RTSP source {pipeline['rtsp_url']} unavailable.")
            continue

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

    active = [p for p in PIPELINES if p["device"] != "NPU" or npu_device != "/dev/null"]
    stream_urls = "\n".join(f"{p['device']}: {RTSP_OUTPUT_BASE_URL}{p['frame_path']}" for p in active)
    print(f"RTSP streams available at:\n{stream_urls}")

    inputs = " \\\n".join(f"  -rtsp_transport tcp -i {RTSP_OUTPUT_BASE_URL}{p['frame_path']}" for p in active)
    outputs = " \\\n".join(f"  -map {i}:v -c:v copy {p['frame_path']}.mkv" for i, p in enumerate(active))
    print(f"\nTo save all streams to disk, run:\nffmpeg \\\n{inputs} \\\n{outputs}")


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


# Tracks the last known armed state so we only act on transitions.
last_armed_state = None


def on_connect(client, userdata, flags, rc):
    print("Connected with result code", rc)
    client.subscribe(TOPIC)


def on_message(client, userdata, msg):
    global last_armed_state

    payload = msg.payload.decode("utf-8", errors="replace")
    #print(f"{msg.topic} {payload}")

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        print("[mqtt] Failed to parse payload as JSON, ignoring.")
        return

    is_armed = bool(data.get("armed", False))

    if is_armed != last_armed_state:
        if is_armed:
            print("Vehicle Status: ARMED -> starting pipelines")
            start_pipelines()
        else:
            print("Vehicle Status: DISARMED -> stopping pipelines")
            stop_pipelines()

        last_armed_state = is_armed


def main():
    parser = argparse.ArgumentParser(
        description="MQTT-triggered DL Streamer pipeline manager"
    )
    parser.add_argument(
        "--sink",
        choices=["rtsp", "udp"],
        default="rtsp",
        help="Output sink type (default: rtsp). Note: only 'rtsp' is supported by this manager.",
    )
    args = parser.parse_args()

    if args.sink == "udp":
        print("Note: mqtt_pipeline_manager only supports RTSP sink. UDP sink is not supported. "
              "Continuing with RTSP.")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT, 60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nStopping monitor.")
        if running_instance_ids:
            print("Cleaning up: stopping active pipelines before exit.")
            stop_pipelines()


if __name__ == '__main__':
    main()
