# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
from pathlib import Path


def _read_non_negative_int(var_name: str, default: int) -> int:
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return default

APP_PORT = int(os.environ.get("DASHBOARD_PORT", "4173"))
PEER_ID = os.environ.get("WEBRTC_PEER_ID", "genai_pipeline")
SIGNALING_URL = os.environ.get("SIGNALING_URL", "http://localhost:8889")
WEBRTC_BITRATE = int(os.environ.get("WEBRTC_BITRATE", "2048"))
ALERT_MODE = os.environ.get("ALERT_MODE", "false").lower() in ("true", "1", "yes")
DEFAULT_RTSP_URL = os.environ.get("DEFAULT_RTSP_URL", "")
ENABLE_DETECTION_PIPELINE = os.environ.get(
    "ENABLE_DETECTION_PIPELINE", "false"
).lower() in ("true", "1", "yes")
CAPTION_HISTORY = _read_non_negative_int("CAPTION_HISTORY", 3)

# Metrics Service Configuration
METRICS_SERVICE_PORT = os.environ.get("METRICS_SERVICE_PORT", "9090")

# MQTT Configuration
MQTT_BROKER_HOST = os.environ.get("MQTT_BROKER_HOST", "mqtt-broker")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_BROKER_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.environ.get("MQTT_TOPIC_PREFIX", "live-video-captioning")

PIPELINE_SERVER_URL = os.environ.get(
    "PIPELINE_SERVER_URL", "http://dlstreamer-pipeline-server:8080"
)
PIPELINE_NAME = os.environ.get("PIPELINE_NAME", "genai_pipeline")
# How often (in seconds) to poll the pipeline server for run health. 0 disables polling.
# Keep this low (≤10 s) so the UI reflects a crashed pipeline server quickly.
PIPELINE_POLL_INTERVAL = _read_non_negative_int("PIPELINE_POLL_INTERVAL", 8)

BASE_DIR = Path(__file__).parent.parent
MODELS_DIR = Path(os.environ.get("MODELS_DIR", str(BASE_DIR / "ov_models")))
DETECTION_MODELS_DIR = Path(
    os.environ.get("DETECTION_MODELS_DIR", str(BASE_DIR / "ov_detection_models"))
)
UI_DIR = BASE_DIR / "ui"
