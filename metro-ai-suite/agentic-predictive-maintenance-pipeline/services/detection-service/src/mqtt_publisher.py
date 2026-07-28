# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""MQTT publisher — announces "batch-complete" events when a detection run finishes.

This is the sole contract between the detection layer and the (detection-
agnostic) agent-service: once a detection run reaches a terminal state, the
detection layer publishes one event describing the outcome and the id window
of detections it produced. The agent-service subscribes to this topic and
reasons only when it observes a ``status: completed`` event — it never talks
to DL Streamer or any other detector directly.
"""

import json
import logging
import os

import paho.mqtt.publish as publish

log = logging.getLogger(__name__)

_MQTT_HOST        = os.environ.get("MQTT_HOST", "mqtt-broker")
_MQTT_PORT        = int(os.environ.get("MQTT_PORT", "1883"))
_MQTT_BATCH_TOPIC = os.environ.get("MQTT_BATCH_TOPIC", "apm/batch-complete")


def publish_batch_complete(event: dict) -> None:
    """Publish a batch-complete event describing the outcome of a detection run.

    Expected ``event`` shape::

        {
            "run_id": "...",
            "status": "completed" | "error",
            "device": "CPU" | "GPU" | "NPU",
            "video_filename": "sample.mp4" | None,
            "start_id": int,           # detection watermark before this run
            "end_id": int | None,      # detection watermark after this run (None on error)
            "pipeline_status": {...},  # raw DL Streamer terminal status (completed only)
            "error": "..." | None,     # failure reason (error only)
        }

    Publishing failures are logged but never raised — a dropped notification
    should not crash the detection run itself; the agent-service's `/agents/run`
    endpoint remains available as a manual fallback trigger.
    """
    try:
        publish.single(
            _MQTT_BATCH_TOPIC,
            payload=json.dumps(event),
            hostname=_MQTT_HOST,
            port=_MQTT_PORT,
        )
        log.info("Published batch-complete event for run %s (status=%s) to %s",
                  event.get("run_id"), event.get("status"), _MQTT_BATCH_TOPIC)
    except Exception as exc:
        log.error("Failed to publish batch-complete event for run %s: %s", event.get("run_id"), exc)
