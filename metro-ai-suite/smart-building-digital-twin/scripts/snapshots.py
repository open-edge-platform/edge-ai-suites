#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""SnapshotClient — captures camera frames via MQTT getimage protocol.

MQTT flow (mirrors sscape.js):
  Publish  → scenescape/cmd/camera/{cam_id}        payload: "getimage"
  Subscribe← scenescape/image/camera/{cam_id}      payload: JSON {"image": "<base64_jpeg>", ...}

Use capture(camera_ids) to request frames from a specific subset of cameras,
or pass None/empty to capture all known cameras.

Only one capture runs at a time — concurrent callers queue and execute serially.
"""

import json
import logging
import re
import ssl
import threading
from pathlib import Path

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

# MQTT topics  (mirror constants.js: APP_NAME + CMD_CAMERA / IMAGE_CAMERA)
_CMD_PREFIX   = "scenescape/cmd/camera/"
_IMAGE_PREFIX = "scenescape/image/camera/"

# Regex to extract camera IDs from alert text, e.g. "[cams: cam-1, cam-3]"
_CAM_RE = re.compile(r'\bcam-\d+\b')


def parse_cameras_from_alert(alert_text: str) -> list[str]:
  """Return the ordered, deduplicated list of camera IDs mentioned in an alert entry."""
  seen, result = set(), []
  for cam in _CAM_RE.findall(alert_text):
    if cam not in seen:
      seen.add(cam)
      result.append(cam)
  return result


class SnapshotClient:
  """Persistent MQTT client that captures annotated camera frames on demand.

  Thread-safe: concurrent capture() calls are serialized by _capture_lock so
  they never corrupt each other's pending-response state.
  """

  def __init__(
    self,
    all_camera_ids: list[str],
    broker_host: str,
    broker_port: int = 1883,
    ca_cert: str | None = None,
    tls_insecure: bool = True,
    broker_auth: str | None = None,
    timeout_s: float = 3.0,
  ):
    self._all_cameras  = list(all_camera_ids)
    self._timeout_s    = timeout_s

    # Serializes concurrent capture() calls end-to-end
    self._capture_lock = threading.Lock()

    # Protects _pending and _done_event state accessed by _on_message
    self._state_lock   = threading.Lock()
    self._pending: dict[str, str | None] = {}
    self._done_event   = threading.Event()

    self._client = mqtt.Client(client_id="snapshot-client", protocol=mqtt.MQTTv311)
    self._client.enable_logger(logger)

    if broker_auth and Path(broker_auth).exists():
      with open(broker_auth) as f:
        creds = json.load(f)
      self._client.username_pw_set(creds["user"], creds["password"])

    if ca_cert and Path(ca_cert).exists():
      self._client.tls_set(
        ca_certs=ca_cert,
        cert_reqs=ssl.CERT_NONE,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
      )
      self._client.tls_insecure_set(tls_insecure)

    self._client.on_connect = self._on_connect
    self._client.on_message = self._on_message

    self._client.connect(broker_host, broker_port, keepalive=60)
    self._client.loop_start()

  def _on_connect(self, client, userdata, flags, rc):
    if rc == 0:
      client.subscribe(_IMAGE_PREFIX + "#")
      logger.info("SnapshotClient connected, subscribed to %s#", _IMAGE_PREFIX)
    else:
      logger.error("SnapshotClient connect failed rc=%d", rc)

  def _on_message(self, client, userdata, msg):
    topic = msg.topic
    if not topic.startswith(_IMAGE_PREFIX):
      return
    cam_id = topic[len(_IMAGE_PREFIX):]

    with self._state_lock:
      if cam_id not in self._pending:
        return  # not a camera we're waiting for

      try:
        payload = json.loads(msg.payload.decode("utf-8"))
        b64 = payload.get("image", "")
        if b64:
          self._pending[cam_id] = b64
      except Exception:
        logger.exception("SnapshotClient: failed to parse payload for %s", cam_id)

      if all(v is not None for v in self._pending.values()):
        self._done_event.set()

  def capture(self, camera_ids: list[str] | None = None) -> dict[str, str]:
    """Capture annotated JPEG frames from the specified cameras.

    Args:
      camera_ids: list of camera IDs to capture, e.g. ["cam-1", "cam-3"].
                  Pass None or [] to capture all known cameras.

    Returns:
      dict mapping cam_id → "data:image/jpeg;base64,..." for cameras that responded.
    """
    targets = [c for c in (camera_ids or self._all_cameras) if c in self._all_cameras or not self._all_cameras]
    if not targets:
      targets = self._all_cameras

    with self._capture_lock:
      # Set up pending state inside the serialization lock so concurrent callers
      # can never overwrite each other's state.
      with self._state_lock:
        self._pending = {cam: None for cam in targets}
        self._done_event.clear()

      for cam_id in targets:
        self._client.publish(_CMD_PREFIX + cam_id, payload="getimage", qos=1)
      logger.debug("SnapshotClient: getimage → %s", targets)

      self._done_event.wait(timeout=self._timeout_s)

      with self._state_lock:
        result = {
          cam: "data:image/jpeg;base64," + b64
          for cam, b64 in self._pending.items()
          if b64
        }
        self._pending.clear()

    received = len(result)
    logger.info("SnapshotClient: received %d/%d camera frames %s",
                received, len(targets), sorted(result))
    return result
