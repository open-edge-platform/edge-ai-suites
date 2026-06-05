#!/usr/bin/env python3
"""
MQTT Camera Capture and Post-Processor.

Subscribes to per-camera MQTT detection topics, buffers frames starting
at frame 0, then once MAX_SAMPLES are collected, fills any missing frame
slots with empty-object placeholders and rewrites timestamps from a
reference frame->timestamp CSV mapping.

Output: one JSONL file per camera under OUTPUT_DIRECTORY.
"""

import json
import os
import ssl
import subprocess
import sys
import csv
from typing import Optional

import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Configuration (hardcoded; promote to CLI args later if needed)
# ---------------------------------------------------------------------------
MAX_SAMPLES = 1856
MQTT_BROKER_HOST = "127.0.0.1"
MQTT_BROKER_PORT = 1883
MQTT_KEEPALIVE = 60

# Both cameras share the same wall-clock timestamps (verified via
# compare of Cam_x1_0.json and Cam_x2_0.json), so one mapping is sufficient.
TIMESTAMP_MAPPING_CSV = "frame_timestamp_mapping.csv"

OUTPUT_DIRECTORY = "dataset"

# Pipeline command run after capture+post-processing completes.
# cwd is the directory of this script; PYTHONPATH=.. lets it import sibling
# modules from tools/tracker/evaluation.
PIPELINE_CMD = [sys.executable, "-m", "pipeline_engine",
                "metric_test_evaluation.yaml"]
PIPELINE_PYTHONPATH = ".."

# Per-camera config: MQTT topic -> output id used in filename and "id" field
CAMERAS = {
    "scenescape/data/camera/Cam_x1_0": "Cam_x1_0",
    "scenescape/data/camera/Cam_x2_0": "Cam_x2_0",
}


# ---------------------------------------------------------------------------
# Frame -> timestamp lookup
# ---------------------------------------------------------------------------
class FrameTimestampLookup:
  """O(1) frame_id -> timestamp lookup loaded from a CSV (frame,timestamp)."""

  def __init__(self, csv_file: str):
    self.mapping = {}
    with open(csv_file, "r") as f:
      for row in csv.DictReader(f):
        self.mapping[int(row["frame"])] = row["timestamp"]

  def get_timestamp(self, frame_id: int) -> Optional[str]:
    return self.mapping.get(frame_id)


# ---------------------------------------------------------------------------
# Per-camera capture state
# ---------------------------------------------------------------------------
class CameraCapture:
  """Tracks capture progress for a single camera topic."""

  def __init__(self, topic: str, cam_id: str):
    self.topic = topic
    self.cam_id = cam_id
    self.started = False
    self.done = False
    self.frames = {}  # frame_num -> message dict

  def ingest(self, message: dict) -> None:
    if self.done:
      return

    frame_num = message.get("frame")
    if frame_num is None:
      return

    # Wait for frame 0 before starting capture (drops any in-progress stream).
    if not self.started:
      if frame_num != 0:
        return
      self.started = True
      print(f"[{self.cam_id}] capture started at frame 0")

    self.frames[frame_num] = message
    print(f"[{self.cam_id}] frame {frame_num}")

    if len(self.frames) >= MAX_SAMPLES or frame_num >= MAX_SAMPLES - 1:
      self.done = True
      print(f"[{self.cam_id}] capture complete ({len(self.frames)} frames)")


# ---------------------------------------------------------------------------
# Post-processing
# ---------------------------------------------------------------------------
def write_camera_output(capture: CameraCapture, lookup: FrameTimestampLookup,
                        output_dir: str) -> None:
  """Fill missing frames, fix timestamps, write JSONL output for one camera."""
  os.makedirs(output_dir, exist_ok=True)
  output_path = os.path.join(output_dir, f"{capture.cam_id}.json")

  # Build a template from the first received frame; missing frames inherit
  # its keys but with an empty objects dict.
  any_frame = next(iter(capture.frames.values()), None)
  if any_frame is None:
    print(f"[{capture.cam_id}] no frames captured; skipping output")
    return

  template = {k: v for k, v in any_frame.items()
              if k not in ("frame", "timestamp", "objects")}

  missing = 0
  with open(output_path, "w") as f:
    for frame_num in range(MAX_SAMPLES):
      if frame_num in capture.frames:
        entry = dict(capture.frames[frame_num])
      else:
        entry = dict(template)
        entry["objects"] = {}
        missing += 1

      entry["frame"] = frame_num
      entry["timestamp"] = lookup.get_timestamp(frame_num)
      entry["id"] = capture.cam_id
      f.write(json.dumps(entry) + "\n")

  print(f"[{capture.cam_id}] wrote {output_path} "
        f"(filled {missing} missing frames)")


def finalize_all(captures: dict, lookup: FrameTimestampLookup) -> None:
  for capture in captures.values():
    write_camera_output(capture, lookup, OUTPUT_DIRECTORY)


def run_pipeline() -> int:
  """Invoke the evaluation pipeline; stream its stdout/stderr to console."""
  script_dir = os.path.dirname(os.path.abspath(__file__))
  env = os.environ.copy()
  existing = env.get("PYTHONPATH", "")
  env["PYTHONPATH"] = (PIPELINE_PYTHONPATH + os.pathsep + existing
                       if existing else PIPELINE_PYTHONPATH)

  print("\n" + "=" * 60)
  print("Running pipeline: PYTHONPATH={} {}".format(
      env["PYTHONPATH"], " ".join(PIPELINE_CMD)))
  print("=" * 60, flush=True)

  # Inherit stdout/stderr so output is shown live to the user.
  result = subprocess.run(PIPELINE_CMD, cwd=script_dir, env=env)
  print("=" * 60)
  print(f"Pipeline exited with code {result.returncode}")
  print("=" * 60, flush=True)
  return result.returncode


# ---------------------------------------------------------------------------
# MQTT plumbing
# ---------------------------------------------------------------------------
def build_client(captures: dict, lookup: FrameTimestampLookup) -> mqtt.Client:
  client = mqtt.Client()

  def on_connect(client, userdata, flags, rc):
    if rc != 0:
      print(f"MQTT connect failed (rc={rc})", file=sys.stderr)
      sys.exit(1)
    print("MQTT connected; subscribing to camera topics:")
    for topic in captures:
      client.subscribe(topic)
      print(f"  - {topic}")

  def on_message(client, userdata, msg):
    capture = captures.get(msg.topic)
    if capture is None or capture.done:
      return

    try:
      payload = json.loads(msg.payload.decode())
    except json.JSONDecodeError as e:
      print(f"[{msg.topic}] bad JSON: {e}", file=sys.stderr)
      return

    capture.ingest(payload)

    if all(c.done for c in captures.values()):
      print("All cameras complete; post-processing...")
      finalize_all(captures, lookup)
      client.disconnect()
      run_pipeline()

  client.on_connect = on_connect
  client.on_message = on_message

  # TLS without peer/hostname verification (matches original behavior).
  client.tls_set(cert_reqs=ssl.CERT_NONE)
  client.tls_insecure_set(True)

  return client


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
  lookup = FrameTimestampLookup(TIMESTAMP_MAPPING_CSV)
  print(f"Loaded {len(lookup.mapping)} timestamps from {TIMESTAMP_MAPPING_CSV}")

  captures = {topic: CameraCapture(topic, cam_id)
              for topic, cam_id in CAMERAS.items()}

  client = build_client(captures, lookup)

  print(f"Connecting to MQTT broker {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}...")
  try:
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_KEEPALIVE)
    client.loop_forever()
  except Exception as e:
    print(f"Could not connect: {e}", file=sys.stderr)
    return 1

  return 0


if __name__ == "__main__":
  sys.exit(main())
