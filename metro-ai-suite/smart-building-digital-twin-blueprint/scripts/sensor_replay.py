#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Replay sensor events synchronized to a looping Scenescape video stream.

Loop timing is derived only from raw camera metadata:

1. Watch one camera topic for a dark gap followed by the first detection.
2. Record that wall-clock moment as the loop restart reference.
3. Replay sensor events in open loop from the recorded sensor timestamps and
   the elapsed wall-clock time since that restart reference.

The optional timestamp_offset is a fixed fudge factor applied to every sensor
timestamp to compensate for the fixed delta between the first post-gap camera
detection and the desired replay start point.
"""

import argparse
import json
import logging
import ssl
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# Consecutive zero-object raw camera frames to declare scene dark.
# Raw camera metadata goes dark at loop boundaries (unlike the regulated topic
# which keeps objects alive through fades via the tracker).
DARK_THRESHOLD = 3

# Open-loop publisher cadence once a loop start has been detected.
PUBLISH_INTERVAL_S = 0.02


class SensorReplay:
  def __init__(self, sensor_file, broker_host, broker_port, ca_cert, tls_insecure,
                 broker_auth, light_sensor_id, sync_camera, timestamp_offset=0.0):
    with open(sensor_file) as f:
      data = json.load(f)
    self.messages = sorted(data['messages'], key=lambda x: x['timestamp'])
    self.light_sensor_id = light_sensor_id
    self.sync_camera = sync_camera
    self.timestamp_offset = timestamp_offset
    logger.info(f"Loaded {len(self.messages)} sensor messages "
          f"(span {self.messages[0]['timestamp']:.1f}s – "
          f"{self.messages[-1]['timestamp']:.1f}s)")
    logger.info(f"Sync camera: {sync_camera}")
    if timestamp_offset:
      logger.info(f"Timestamp offset: +{timestamp_offset:.2f}s")

    self.loop_start_wall = None
    self.scene_dark = True
    self.consec_empty = 0
    self._seen_dark_boundary = False
    self.next_index = 0
    self.loop_count = 0
    self.messages_sent = 0
    self._lock = threading.Lock()

    self._broker_host = broker_host
    self._broker_port = broker_port

    self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

    if broker_auth and Path(broker_auth).exists():
      with open(broker_auth) as f:
        creds = json.load(f)
      self.client.username_pw_set(creds['user'], creds['password'])
      logger.info(f"Using broker auth as user '{creds['user']}'")

    if ca_cert and Path(ca_cert).exists():
      self.client.tls_set(ca_certs=ca_cert, cert_reqs=ssl.CERT_NONE,
                tls_version=ssl.PROTOCOL_TLS_CLIENT)
      self.client.tls_insecure_set(tls_insecure)

    self.client.on_connect = self._on_connect
    self.client.on_message = self._on_camera_message
    self.client.on_subscribe = self._on_subscribe
    self.client.on_disconnect = self._on_disconnect
    self.client.connect(broker_host, broker_port, 60)

  def _on_connect(self, client, userdata, flags, rc):
    logger.info(f"Connected to {self._broker_host}:{self._broker_port} (rc={rc})")
    client.subscribe(f"scenescape/data/camera/{self.sync_camera}")
    logger.info(f"Subscribed: scenescape/data/camera/{self.sync_camera}")

  def _on_subscribe(self, client, userdata, mid, granted_qos):
    logger.info(f"Subscription confirmed: mid={mid} granted_qos={granted_qos}")

  def _on_disconnect(self, client, userdata, rc):
    logger.warning(f"Disconnected from broker (rc={rc})")

  def _publish_light(self, lux):
    if not self.light_sensor_id:
      return
    self.client.publish(
      f"scenescape/data/sensor/{self.light_sensor_id}",
      json.dumps({
        'id': self.light_sensor_id,
        'timestamp': datetime.now(tz=timezone.utc).isoformat().replace('+00:00', 'Z'),
        'value': lux,
        'subtype': 'light',
      })
    )
    logger.info(f"Light sensor: {lux} lux")

  def _on_camera_message(self, client, userdata, msg):
    """Use raw camera metadata for loop boundary detection.

    The regulated topic keeps objects alive through video fades (tracker
    continuity), so it never goes dark. Raw camera metadata drops to zero
    objects for a few frames at each loop boundary, giving a reliable signal.
    """
    try:
      payload = json.loads(msg.payload.decode())
    except Exception:
      return

    objects = payload.get('objects', {})
    has_objects = bool(objects)

    with self._lock:
      if has_objects:
        self.consec_empty = 0
        if self.scene_dark and self._seen_dark_boundary:
          self.scene_dark = False
          self.loop_start_wall = time.time()
          self.next_index = 0
          self.loop_count += 1
          logger.info(f"Loop {self.loop_count} started")
          self._publish_light(500)
        elif self.scene_dark and not self._seen_dark_boundary:
          logger.debug("Ignoring live camera frame until a dark loop boundary is observed")
      else:
        self.consec_empty += 1
        if self.consec_empty >= DARK_THRESHOLD:
          if not self.scene_dark:
            self.scene_dark = True
            logger.info("Scene dark")
            self._publish_light(0)
          self._seen_dark_boundary = True

  def _publish_due(self):
    with self._lock:
      if self.scene_dark or self.loop_start_wall is None:
        return
      position = time.time() - self.loop_start_wall
      now_iso = datetime.now(tz=timezone.utc).isoformat().replace('+00:00', 'Z')
      while self.next_index < len(self.messages):
        msg = self.messages[self.next_index]
        if msg['timestamp'] + self.timestamp_offset > position:
          break
        self.client.publish(msg['topic'], json.dumps({
          'id': msg['payload']['id'],
          'timestamp': now_iso,
          'value': msg['payload']['value'],
        }))
        self.messages_sent += 1
        self.next_index += 1

  def _publisher_loop(self):
    while True:
      self._publish_due()
      time.sleep(PUBLISH_INTERVAL_S)

  def run(self):
    def _status_loop():
      while True:
        time.sleep(10)
        with self._lock:
          position = (time.time() - self.loop_start_wall) if self.loop_start_wall else 0.0
          logger.info(
            f"Loop {self.loop_count} | {position:.1f}s | "
            f"Sent: {self.messages_sent} | {self.next_index}/{len(self.messages)} | "
            f"{'live' if not self.scene_dark else 'dark'}"
          )

    threading.Thread(target=self._publisher_loop, daemon=True).start()
    threading.Thread(target=_status_loop, daemon=True).start()
    logger.info(f"Waiting for camera data from {self.sync_camera}...")
    self.client.loop_forever()


def main():
  p = argparse.ArgumentParser(description='Replay sensor data synced to Scenescape regulated topic')
  p.add_argument('--sensor-file', default='/workspace/sensor_data_stitched.json')
  p.add_argument('--broker', default='broker.scenescape.intel.com')
  p.add_argument('--port', type=int, default=1883)
  p.add_argument('--ca-cert', default='/run/secrets/certs/scenescape-ca.pem')
  p.add_argument('--tls-insecure', action='store_true')
  p.add_argument('--broker-auth', default='/run/secrets/controller.auth')
  p.add_argument('--light-sensor-id', default=None,
                   help='Sensor ID for ambient light; publishes 500 lux on loop start, 0 lux on dark')
  p.add_argument('--sync-camera', default='cam-5',
                   help='Camera ID whose raw metadata topic is used for loop boundary detection '
            '(default: cam-5). Must be a camera that goes dark at loop boundaries.')
  p.add_argument('--timestamp-offset', type=float, default=0.0,
                   help='Fixed seconds added to each sensor timestamp before it is due. '
                        'Use this to compensate for the constant delta between the first '
                        'post-gap camera detection and the desired replay start point '
                        '(default: 0.0).')
  p.add_argument('--verbose', action='store_true')
  args = p.parse_args()

  logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
            format='%(asctime)s %(levelname)s %(message)s')

  SensorReplay(
    sensor_file=args.sensor_file,
    broker_host=args.broker,
    broker_port=args.port,
    ca_cert=args.ca_cert,
    tls_insecure=args.tls_insecure,
    broker_auth=args.broker_auth,
    light_sensor_id=args.light_sensor_id,
    sync_camera=args.sync_camera,
    timestamp_offset=args.timestamp_offset,
  ).run()


if __name__ == '__main__':
  main()
