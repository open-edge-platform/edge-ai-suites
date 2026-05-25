#!/usr/bin/env python3
"""
MQTT-gated iperf3 traffic generator.

Listens to two camera MQTT topics; once BOTH have emitted frame 0, repeatedly
runs:
    iperf3 -c <target> -u -b <bitrate> -t <duration>
sleeping --sleep seconds between runs. Stops as soon as either camera's
frame field exceeds --stop-frame.
"""

import argparse
import json
import os
import signal
import ssl
import subprocess
import sys
import threading
import time
from typing import Dict

import paho.mqtt.client as mqtt


def parse_args() -> argparse.Namespace:
  p = argparse.ArgumentParser(description=__doc__,
                              formatter_class=argparse.RawDescriptionHelpFormatter)
  p.add_argument("--broker", default="10.106.147.105",
                 help="MQTT broker host (default: %(default)s)")
  p.add_argument("--port", type=int, default=1883,
                 help="MQTT broker port (default: %(default)s)")
  p.add_argument("--no-tls", action="store_true",
                 help="Disable TLS (default: TLS-insecure enabled)")
  p.add_argument("--topics", nargs="+",
                 default=["scenescape/data/camera/Cam_x1_0",
                          "scenescape/data/camera/Cam_x2_0"],
                 help="MQTT topics that must reach frame 0 before traffic starts")
  p.add_argument("--target", default="127.0.0.1",
                 help="iperf3 server host (-c)")
  p.add_argument("--bitrate", default="960M",
                 help="iperf3 bitrate (-b), default: %(default)s")
  p.add_argument("--duration", type=int, default=2,
                 help="iperf3 run duration in seconds (-t), default: %(default)s")
  p.add_argument("--sleep", type=float, default=1.0,
                 help="Seconds to sleep between iperf3 runs, default: %(default)s")
  p.add_argument("--stop-frame", type=int, default=1700,
                 help="Stop traffic when any camera frame exceeds this, default: %(default)s")
  p.add_argument("--iperf3", default="iperf3",
                 help="Path to iperf3 binary (default: %(default)s)")
  return p.parse_args()


class CameraState:

  def __init__(self):
    self.started = False
    self.latest_frame = -1


def main() -> int:
  args = parse_args()

  cams: Dict[str, CameraState] = {t: CameraState() for t in args.topics}
  start_event = threading.Event()  # set when ALL topics have started
  stop_event = threading.Event()   # set when ANY topic crosses stop-frame

  state_lock = threading.Lock()

  def on_connect(client, userdata, flags, rc):
    if rc != 0:
      print(f"MQTT connect failed (rc={rc})", file=sys.stderr)
      stop_event.set()
      return
    print(f"Connected to MQTT {args.broker}:{args.port}; subscribing:")
    for topic in args.topics:
      client.subscribe(topic)
      print(f"  - {topic}")

  def on_message(client, userdata, msg):
    cam = cams.get(msg.topic)
    if cam is None:
      return
    try:
      payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
      return
    frame = payload.get("frame")
    if not isinstance(frame, int):
      return

    with state_lock:
      cam.latest_frame = frame
      if not cam.started and frame == 0:
        cam.started = True
        print(f"[{msg.topic}] reached frame 0")
        if all(c.started for c in cams.values()):
          print("All cameras started; releasing traffic loop")
          start_event.set()

      if frame > args.stop_frame:
        # Only honor stop-frame after traffic generation has actually begun.
        # Otherwise, if we started the script mid-stream (frames already past
        # the threshold), we'd stop instantly and never wait for the next
        # frame-0 cycle.
        if not start_event.is_set():
          return
        if not stop_event.is_set():
          print(f"[{msg.topic}] frame {frame} > {args.stop_frame}; "
                f"stopping traffic generation")
        stop_event.set()

  client = mqtt.Client()
  client.on_connect = on_connect
  client.on_message = on_message
  if not args.no_tls:
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.tls_insecure_set(True)

  def traffic_loop():
    print(f"Waiting for frame 0 on all {len(cams)} topics...")
    while not start_event.wait(timeout=0.5):
      if stop_event.is_set():
        return

    cmd = [args.iperf3, "-c", args.target, "-u", "-b", args.bitrate,
           "-t", str(args.duration)]
    print(f"Traffic loop starting: {' '.join(cmd)}  (sleep={args.sleep}s "
          f"between runs, stop@frame>{args.stop_frame})")

    run = 0
    while not stop_event.is_set():
      run += 1
      print(f"\n--- iperf3 run #{run} ---", flush=True)
      try:
        subprocess.run(cmd, check=False)
      except FileNotFoundError:
        print(f"ERROR: '{args.iperf3}' not found in PATH", file=sys.stderr)
        stop_event.set()
        break
      except Exception as e:
        print(f"iperf3 invocation failed: {e}", file=sys.stderr)
        stop_event.set()
        break

      if stop_event.is_set():
        break
      # Interruptible sleep
      stop_event.wait(timeout=args.sleep)

    print(f"\nTraffic loop done after {run} run(s); disconnecting MQTT.")
    try:
      client.disconnect()
    except Exception:
      pass

  worker = threading.Thread(target=traffic_loop, daemon=True)
  worker.start()

  def handle_sigint(signum, frame):
    print("\nSIGINT received; stopping.", file=sys.stderr)
    stop_event.set()
    start_event.set()  # unblock waiter
    try:
      client.disconnect()
    except Exception:
      pass

  signal.signal(signal.SIGINT, handle_sigint)
  signal.signal(signal.SIGTERM, handle_sigint)

  try:
    client.connect(args.broker, args.port, keepalive=60)
    client.loop_forever()
  except Exception as e:
    print(f"MQTT loop ended: {e}", file=sys.stderr)
    stop_event.set()
    start_event.set()

  worker.join(timeout=max(args.duration + args.sleep + 2, 5))
  return 0 if stop_event.is_set() else 1


if __name__ == "__main__":
  sys.exit(main())
